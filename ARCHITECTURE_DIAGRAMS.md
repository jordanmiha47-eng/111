# 🗺️ АРХИТЕКТУРНАЯ ДИАГРАММА И FLOW CHARTS

## 1. Текущая архитектура (с проблемами)

```
┌─────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT (salon_bot.py)                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
           ┌────▼─────┐   ┌─────▼────┐   ┌─────▼────┐
           │ /start    │   │ /mybookings│  │ /admin   │
           │ /master   │   │ /cancel    │  │ /master  │
           └────┬─────┘   └─────┬────┘   └─────┬────┘
                │               │              │
     ❌ ПРОБЛЕМА: Нет проверки    │              │
        ролей (admin/master/client)│              │
                │               │              │
           ┌────▼─────────────────▼──────────────▼────┐
           │     User Sessions (in-memory dict)       │
           │  {user_id: {service, master, date, time}}│
           └────┬─────────────────────────────────────┘
                │
      ❌ ПОТЕРЯ при перезапуске!
                │
           ┌────▼─────────────────────────┐
           │    UltraCalendar             │
           │ ├─ create_visual_calendar()  │
           │ ├─ is_date_available()       │
           │ └─ generate_available_times()│
           └────┬────────────────────────┘
                │
      ✅ Есть проверка обеда
      ✅ Есть проверка отпуска
      ❌ НЕ проверяет: прошлая дата?
      ❌ НЕ проверяет: слот занят?
                │
           ┌────▼──────────────────────┐
           │   Bookings (in-memory)     │
           │   {booking_id: {...}}      │
           └────┬──────────────────────┘
                │
    ❌ Race Condition!
    ❌ БЕЗ threading.Lock()
    ❌ Потеря при перезапуске
                │
           ┌────▼────────────────────┐
           │ Admin Notifications      │
           │ (send to CONFIG['admin'])│
           └────┬────────────────────┘
                │
           ┌────▼─────────────────┐
           │  RealReminderSystem   │
           │  (APScheduler)        │
           └─────────────────────┘
                ⚠️  Может пропустить
```

---

## 2. Flow: Процесс записи (ТЕКУЩИЙ - С ОШИБКАМИ)

```
USER START (/start)
    │
    ├─ [BUG #1] Нет проверки роли!
    │  Админ видит меню клиента ❌
    │
    ▼
SELECT SERVICE
    │
    ├─ Сохранить в user_sessions
    │
    ▼
SELECT MASTER
    │
    ├─ Сохранить в user_sessions
    │
    ▼
SELECT DATE (UltraCalendar)
    │
    ├─ Проверка доступности
    │  ├─ [OK] Проверка отпуска
    │  └─ [BUG #2] НЕ проверяет: прошлая дата?
    │
    ▼
SELECT TIME
    │
    ├─ Проверка доступности
    │  ├─ [OK] Пропускает обед
    │  ├─ [OK] Пропускает вне рабочих часов
    │  └─ [BUG #3] Проверка неполная!
    │
    ▼
CONFIRM
    │
    ├─ [BUG #4] БЕЗ ВАЛИДАЦИИ!
    │  ├─ Дата может быть в прошлом
    │  ├─ Слот может быть занят (race condition)
    │  └─ Времени может быть вне часов
    │
    ├─ [BUG #5] RACE CONDITION!
    │  Два пользователя одновременно:
    │  ├─ Пользователь A: Проверяет - СВОБОДНО
    │  ├─ Пользователь B: Проверяет - СВОБОДНО
    │  ├─ Пользователь A: Создаёт запись ✓
    │  └─ Пользователь B: Создаёт запись ✓ ← ДВОЙНАЯ БРОНЬ!
    │
    ▼
CREATE BOOKING
    │
    ├─ booking_id = "booking_<timestamp>"
    ├─ Сохранить в bookings dict
    ├─ [OK] Notify admin
    └─ [BUG #6] Потеря при перезапуске (только in-memory)
    │
    ▼
CLEAR SESSION
    │
    ├─ Del user_sessions[user_id]
    ▼
END
```

---

## 3. Flow: Выбор роли (ТРЕБУЕМЫЙ - НОВЫЙ)

```
USER START (/start)
    │
    ▼
GET USER ID
    │
    ├─ get_user_role(user_id)
    │  ├─ if user_id == CONFIG['admin_id']
    │  │  └─ role = 'admin'
    │  ├─ if user_id in CONFIG['masters'].values()
    │  │  └─ role = 'master'
    │  └─ else
    │     └─ role = 'client'
    │
    ▼
ROUTE BY ROLE
    │
    ├─ ADMIN:
    │  ├─ Show: "👑 ПАНЕЛЬ АДМИНИСТРАТОРА"
    │  ├─ Buttons: [Статистика] [Управление] [Все записи]
    │  └─ Access: /admin, /master_manage, /bookings_list
    │
    ├─ MASTER:
    │  ├─ Show: "👨‍💼 [Имя мастера]"
    │  ├─ Buttons: [Расписание] [Статистика] [Отпуск]
    │  └─ Access: /master, /master_stats, /master_vacation
    │
    └─ CLIENT:
       ├─ Show: "💈 Чародейка - ВЫБЕРИТЕ УСЛУГУ"
       ├─ Buttons: [Услуги...] [Web App] [О салоне]
       └─ Access: /start (booking), /mybookings, /cancel
    │
    ▼
END
```

---

## 4. Система валидации (ТРЕБУЕМАЯ)

```
VALIDATE_BOOKING_TIME(date_str, time_str, master_name)
    │
    ├─ [CHECK 1] Формат даты: "%Y-%m-%d" ✓
    │  └─ Если ошибка → "❌ Ошибка формата"
    │
    ├─ [CHECK 2] Формат времени: "%H:%M" ✓
    │  └─ Если ошибка → "❌ Ошибка формата"
    │
    ├─ [CHECK 3] Дата >= сегодня ✓
    │  └─ Если прошлое → "❌ Прошедшее время"
    │
    ├─ [CHECK 4] Рабочий день (не в closed_days)
    │  └─ Если закрыто → "❌ Салон закрыт"
    │
    ├─ [CHECK 5] Время в working_hours ✓
    │  └─ Если вне часов → "❌ Вне рабочих часов"
    │
    ├─ [CHECK 6] Время НЕ в обеде ✓
    │  └─ Если обед → "❌ Обеденное время"
    │
    ├─ [CHECK 7] Мастер существует ✓
    │  └─ Если нет → "❌ Такого мастера нет"
    │
    ├─ [CHECK 8] Мастер НЕ в отпуске ✓
    │  └─ Если отпуск → "❌ Мастер в отпуске"
    │
    └─ [CHECK 9] Слот НЕ занят ✓
       └─ Если занят → "❌ Время занято"
    │
    ▼
    return (is_valid=True, message="✅ Время доступно")
```

---

## 5. Защита от Race Condition (ТРЕБУЕМАЯ)

```
HANDLE_CONFIRMATION (user_id, session)
    │
    ├─ [STEP 1] Валидация перед блокировкой
    │  ├─ is_valid, message = validate_booking_time(...)
    │  └─ if not is_valid → return error
    │
    ├─ [STEP 2] ACQUIRE LOCK
    │  └─ with booking_lock:  ◄─ threading.Lock()
    │     │
    │     ├─ [CHECK AGAIN] Проверяем ЕЩЁ РАЗ!
    │     │  └─ Может измениться после валидации?
    │     │
    │     ├─ if is_still_free:
    │     │  │
    │     │  ├─ [SAFE] Создаём запись
    │     │  ├─ bookings[booking_id] = {...}
    │     │  ├─ save_data()
    │     │  │
    │     │  └─ [SAFE] Только одна запись на время!
    │     │
    │     └─ else:
    │        └─ return "❌ Время уже занято"
    │
    ├─ [STEP 3] RELEASE LOCK
    │  └─ (автоматически при выходе из with)
    │
    ▼
    return success
```

**Результат**: Защита от двойных записей ✓

---

## 6. Web App Integration (ТРЕБУЕМАЯ)

```
┌─────────────────────────────────────┐
│  Telegram Bot (salon_bot.py)        │
└──────────────┬──────────────────────┘
               │
        ┌──────▼────────┐
        │  /start       │
        │  [Web App BTN]│ ◄─ WebAppInfo(url="...")
        └──────┬────────┘
               │
               ▼
        ┌─────────────────────────────┐
        │  https://netlify.app/...    │ ◄─ Web App (HTML/CSS/JS)
        │  (Telegram Mini App)        │
        └────────┬────────────────────┘
                 │
        ┌────────▼────────────┐
        │ User selects:       │
        │ - Service           │
        │ - Master            │
        │ - Date              │
        │ - Time              │
        └────────┬────────────┘
                 │
        ┌────────▼──────────────────────┐
        │ Telegram.WebApp.sendData({    │
        │   service, master, date, time │
        │ })                            │
        └────────┬──────────────────────┘
                 │
                 ▼
        ┌─────────────────────────────────┐
        │  Telegram Bot (salon_bot.py)    │
        │                                 │
        │  handler = MessageHandler(      │
        │    filters.web_app_data,        │
        │    handle_web_app_data          │ ◄─ [ТРЕБУЕТСЯ ДОБАВИТЬ!]
        │  )                              │
        └────────┬──────────────────────┘
                 │
        ┌────────▼─────────────────┐
        │ Validate & Create Booking│
        │ (с защитой от race cond) │
        └────────┬─────────────────┘
                 │
        ┌────────▼──────────────────┐
        │ Send Confirmation Message │
        │ to Telegram Chat          │
        └──────────────────────────┘
```

---

## 7. Таблица маршрутизации по ролям (ТРЕБУЕМАЯ)

| Роль | ID | Команды | Кнопки | Видит | Может |
|------|----|---------| -------|-------|------|
| **ADMIN** | `CONFIG['admin_id']` | `/admin`, `/master_manage` | Статистика, Управление | Все записи, Все мастера | Смотреть всё, Управлять |
| **MASTER** | `CONFIG['masters'].values()` | `/master`, `/master_stats`, `/master_vacation` | Расписание, Статистика, Отпуск | Свои записи, Свой доход | Видеть расписание, Установить отпуск |
| **CLIENT** | Другие | `/start`, `/mybookings`, `/cancel` | Услуги, Web App, О салоне | Свои записи | Записаться, Отменить, Перенести |

---

## 8. Диаграмма данных (Data Model)

```
┌────────────────────┐
│  CONFIG (dict)     │ ◄─ Конфигурация (hardcoded)
│ ├─ token           │
│ ├─ admin_id        │
│ ├─ masters {name→id}
│ ├─ services {name→price}
│ └─ salon_info      │
└────────────────────┘

┌────────────────────────┐
│  user_sessions (dict)  │ ◄─ [BUG] Потеря при перезапуске
│ {user_id: {           │
│   service: str        │
│   master: str         │
│   date: YYYY-MM-DD    │
│   time: HH:MM         │
│ }}                    │
└────────────────────────┘

┌──────────────────────────────┐
│  bookings (dict)             │ ◄─ [BUG] Race condition
│ {booking_id: {              │    [BUG] Потеря при перезапуске
│   id: str                   │
│   user_id: int              │
│   service: str              │
│   master: str               │
│   date: YYYY-MM-DD          │
│   time: HH:MM               │
│   status: confirmed|cancelled
│   created_at: ISO datetime  │
│   reminder_sent_24h: bool   │
│   reminder_sent_2h: bool    │
│ }}                          │
└──────────────────────────────┘

┌──────────────────────┐
│  client_data (dict)  │ ◄─ [BUG] Потеря при перезапуске
│ {user_id: {         │
│   name: str         │
│   username: str     │
│   bookings_count: int
│ }}                  │
└──────────────────────┘
```

---

## 9. Граф проблем и зависимостей

```
RACE CONDITION (#5)
    │
    ├─ Зависит от: [ОТСУТСТВИЕ ВАЛИДАЦИИ #4]
    ├─ Зависит от: [ОТСУТСТВИЕ LOCK]
    └─ Приводит к: [ДВОЙНЫЕ ЗАПИСИ]

ОТСУТСТВИЕ ВАЛИДАЦИИ (#4)
    │
    ├─ Проверка прошлых дат
    ├─ Проверка занятости слота
    └─ Приводит к: [RACE CONDITION, НЕПРАВИЛЬНЫЕ ЗАПИСИ]

NO WEB APP HANDLER (#2)
    │
    ├─ Зависит от: [ОТСУТСТВИЕ ВАЛИДАЦИИ]
    ├─ Зависит от: [ОТСУТСТВИЕ RACE CONDITION ЗАЩИТЫ]
    └─ Приводит к: [ПОТЕРЯ ДАННЫХ ИЗ WEB APP]

NO ROLES (#3)
    │
    ├─ Приводит к: [НЕСАНКЦИОНИРОВАННЫЙ ДОСТУП]
    ├─ Приводит к: [НЕПРА
