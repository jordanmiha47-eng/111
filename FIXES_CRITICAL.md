# 🔧 ИСПРАВЛЕНИЯ КРИТИЧЕСКИХ ОШИБОК | salon_bot.py

## Как использовать этот файл:
```
1. Копируйте блоки кода ниже
2. Добавляйте в salon_bot.py на соответствующие места
3. Удаляйте дублирующиеся функции
4. Регистрируйте новые обработчики в setup_handlers()
```

---

## ✅ ИСПРАВЛЕНИЕ #1: Удалить дублирующиеся обработчики

**НАЙТИ И УДАЛИТЬ:**

```python
# Строки 462-475 (ПЕРВОЕ определение handle_menu - УДАЛИТЬ)
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📋 МЕНЮ САЛОНА"
    keyboard = # ...
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Строки 476-486 (ПЕРВОЕ определение handle_help - УДАЛИТЬ)
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # ...
    await query.edit_message_text(text, parse_mode="Markdown")

# ОСТАВИТЬ только ВТОРЫЕ определения (строки 487+ и 501+)
```

---

## ✅ ИСПРАВЛЕНИЕ #2: Реализовать систему ролей

**ДОБАВИТЬ ПОСЛЕ ИМПОРТОВ (после строки 113):**

```python
# БЛОК: СИСТЕМА РОЛЕЙ
def get_user_role(user_id):
    """
    Определить роль пользователя: admin, master, или client
    
    Args:
        user_id: Telegram ID пользователя
    
    Returns:
        'admin' | 'master' | 'client'
    """
    if user_id == CONFIG['admin_id']:
        return 'admin'
    
    # Проверяем, является ли пользователь мастером
    if user_id in CONFIG['masters'].values():
        return 'master'
    
    return 'client'


async def show_client_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню для клиента"""
    text = f"💈 {CONFIG['salon_name']}\n\nВЫБЕРИТЕ УСЛУГУ:"
    keyboard = [
        [InlineKeyboardButton(f"✂️ {service}", callback_data=f"service_{service}")]
        for service in CONFIG["services"].keys()
    ]
    keyboard.append([InlineKeyboardButton("📱 Web App", web_app=WebAppInfo(url="https://charodeyka-booking.netlify.app"))])
    keyboard.append([InlineKeyboardButton("ℹ️ О САЛОНЕ", callback_data="about")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню для администратора"""
    text = "👑 ПАНЕЛЬ АДМИНИСТРАТОРА\n\nВыберите действие:"
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin")],
        [InlineKeyboardButton("⚙️ Управление мастерами", callback_data="admin_masters")],
        [InlineKeyboardButton("📋 Все записи", callback_data="admin_bookings")],
        [InlineKeyboardButton("🏠 На главную", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_master_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню для мастера"""
    # Находим имя мастера по ID
    master_name = None
    for name, m_id in CONFIG['masters'].items():
        if m_id == update.effective_user.id:
            master_name = name
            break
    
    text = f"👨‍💼 {master_name}\n\nВаше меню:"
    keyboard = [
        [InlineKeyboardButton("📅 Мое расписание", callback_data="master")],
        [InlineKeyboardButton("📊 Статистика", callback_data="master_stats")],
        [InlineKeyboardButton("⏳ Отпуск", callback_data="master_vacation")],
        [InlineKeyboardButton("🏠 На главную", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

print("✅ СИСТЕМА РОЛЕЙ ЗАГРУЖЕНА")
```

---

## ✅ ИСПРАВЛЕНИЕ #3: Добавить валидацию времени

**ДОБАВИТЬ ПОСЛЕ UltraCalendar И SmartScheduler КЛАССОВ (после строки 241):**

```python
# БЛОК 4 - СИСТЕМА ВАЛИДАЦИИ
class ValidationSystem:
    """Валидация всех операций с записями"""
    
    @staticmethod
    def validate_booking_time(date_str, time_str, master_name):
        """
        Полная валидация времени записи
        
        Returns:
            (is_valid: bool, message: str)
        """
        try:
            # 1. Проверка формата даты и времени
            booking_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            booking_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            booking_datetime = datetime.datetime.combine(booking_date, booking_time)
            
            # 2. Проверка: не в прошлом?
            now = datetime.datetime.now()
            if booking_datetime < now:
                return False, "❌ Нельзя записаться на прошедшее время"
            
            # 3. Проверка: в рабочие дни?
            if booking_date.weekday() in CONFIG["salon_info"]["working_hours"].get("closed_days", []):
                return False, "❌ Салон закрыт в этот день"
            
            # 4. Проверка: в рабочие часы?
            start_time = datetime.datetime.strptime(
                CONFIG["salon_info"]["working_hours"]["start"], "%H:%M"
            ).time()
            end_time = datetime.datetime.strptime(
                CONFIG["salon_info"]["working_hours"]["end"], "%H:%M"
            ).time()
            
            if not (start_time <= booking_time < end_time):
                return False, f"❌ Вне рабочих часов ({CONFIG['salon_info']['working_hours']['start']}-{CONFIG['salon_info']['working_hours']['end']})"
            
            # 5. Проверка: не во время обеда?
            lunch_config = CONFIG["salon_info"]["working_hours"]["lunch"]
            if isinstance(lunch_config, str):
                lunch = lunch_config.split("-")
            else:
                lunch = lunch_config
            
            lunch_start = datetime.datetime.strptime(lunch[0], "%H:%M").time()
            lunch_end = datetime.datetime.strptime(lunch[1], "%H:%M").time()
            
            if lunch_start <= booking_time < lunch_end:
                return False, f"❌ Обеденное время ({lunch[0]}-{lunch[1]})"
            
            # 6. Проверка: мастер существует?
            if master_name not in CONFIG['masters']:
                return False, "❌ Такого мастера нет"
            
            # 7. Проверка: мастер не в отпуске?
            for vacation in master_schedules[master_name]["vacations"]:
                if vacation["start"] <= date_str <= vacation["end"]:
                    return False, f"❌ {master_name} в отпуске"
            
            # 8. Проверка: слот не занят?
            is_booked = any(
                b['date'] == date_str and 
                b['time'] == time_str and 
                b['master'] == master_name and 
                b['status'] == 'confirmed'
                for b in bookings.values()
            )
            if is_booked:
                return False, "❌ Это время уже занято"
            
            return True, "✅ Время доступно"
            
        except ValueError as e:
            return False, f"❌ Ошибка формата: {str(e)}"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"


validation = ValidationSystem()
print("✅ СИСТЕМА ВАЛИДАЦИИ ЗАГРУЖЕНА")
```

---

## ✅ ИСПРАВЛЕНИЕ #4: Защита от race condition

**ЗАМЕНИТЬ функцию handle_confirmation (строки 408-450):**

```python
import threading

# Добавить ПОСЛЕ глобальных переменных (после строки 112):
booking_lock = threading.Lock()  # Защита от race condition

# ЗАМЕНИТЬ функцию handle_confirmation:
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение записи с защитой от race condition"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await query.edit_message_text("❌ Сессия устарела. Начните заново.")
        return
    
    # Валидируем время ЕЩЁ РАЗ перед созданием (ЗАЩИТА #1)
    is_valid, message = validation.validate_booking_time(
        session['date'], session['time'], session['master']
    )
    
    if not is_valid:
        await query.edit_message_text(message)
        # Очищаем сессию
        del user_sessions[user_id]
        return
    
    # ЗАЩИТА #2: Блокируем доступ к bookings на время записи
    with booking_lock:
        # Проверяем ЕЩЁ РАЗ (может измениться после валидации)
        is_still_free = not any(
            b['date'] == session['date'] and 
            b['time'] == session['time'] and 
            b['master'] == session['master'] and 
            b['status'] == 'confirmed'
            for b in bookings.values()
        )
        
        if not is_still_free:
            await query.edit_message_text(
                "❌ К сожалению, это время уже заняли другие. Выберите другое время."
            )
            del user_sessions[user_id]
            return
        
        # ТЕПЕРЬ создаём запись безопасно
        booking_id = f"booking_{int(datetime.datetime.now().timestamp())}_{user_id}"
        
        bookings[booking_id] = {
            "id": booking_id,
            "user_id": user_id,
            "user_name": query.from_user.first_name or "Клиент",
            "username": query.from_user.username,
            "service": session['service'],
            "master": session['master'],
            "date": session['date'],
            "time": session['time'],
            "price": CONFIG["services"][session['service']],
            "status": "confirmed",
            "created_at": datetime.datetime.now().isoformat(),
            "reminder_sent_24h": False,
            "reminder_sent_2h": False
        }
        
        # Сохраняем данные клиента
        if user_id not in client_data:
            client_data[user_id] = {
                "name": query.from_user.first_name or "Клиент",
                "username": query.from_user.username,
                "bookings_count": 1
            }
        else:
            client_data[user_id]["bookings_count"] += 1
        
        # Обновляем статистику мастера
        master_stats[session['master']]["bookings"] += 1
        master_stats[session['master']]["revenue"] += CONFIG["services"][session['service']]
        
        # Сохраняем данные
        save_data()
    
    # Очищаем сессию
    del user_sessions[user_id]
    
    # Подтверждение для клиента
    confirm_text = (
        f"✅ *ЗАПИСЬ ПОДТВЕРЖДЕНА*\n\n"
        f"📋 Номер: `{booking_id}`\n"
        f"✂️ Услуга: {session['service']}\n"
        f"👨‍💼 Мастер: {session['master']}\n"
        f"📅 Дата: {session['date']}\n"
        f"⏰ Время: {session['time']}\n"
        f"💰 Стоимость: {CONFIG['services'][session['service']]}₽\n\n"
        f"Вы получите напоминание за 24ч и за 2ч до записи.\n"
        f"Отменить: /mybookings"
    )
    
    await query.edit_message_text(confirm_text, parse_mode="Markdown")
    
    # Уведомляем администратора
    try:
        admin_msg = (
            f"🆕 *НОВАЯ ЗАПИСЬ*\n\n"
            f"👤 {query.from_user.first_name} (@{query.from_user.username})\n"
            f"✂️ {session['service']}\n"
            f"👨‍💼 {session['master']}\n"
            f"📅 {session['date']} ⏰ {session['time']}"
        )
        app = Application.builder().token(CONFIG["token"]).build()
        await app.bot.send_message(
            chat_id=CONFIG['admin_id'],
            text=admin_msg,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при уведомлении админа: {e}")
    
    print(f"✅ Запись создана: {booking_id}")

print("✅ ЗАЩИТА ОТ RACE CONDITION ДОБАВЛЕНА")
```

---

## ✅ ИСПРАВЛЕНИЕ #5: Web App обработчик

**ДОБАВИТЬ в блок 3 (после handle_confirmation, перед my_bookings):**

```python
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка данных из Telegram Mini App (Web App)
    
    Web App отправляет JSON с полями:
    {service, master, date, time, user_id}
    """
    try:
        # Парсим данные из Web App
        data = json.loads(update.effective_message.web_app_data.data)
        user_id = update.effective_user.id
        
        logger.info(f"Web App data from {user_id}: {data}")
        
        # Проверяем обязательные поля
        required_fields = ['service', 'master', 'date', 'time']
        if not all(field in data for field in required_fields):
            await update.message.reply_text(
                "❌ Неполные данные из Web App. Попробуйте еще раз."
            )
            return
        
        # Валидируем время
        is_valid, message = validation.validate_booking_time(
            data['date'], data['time'], data['master']
        )
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ Ошибка при бронировании:\n{message}"
            )
            return
        
        # Защита от race condition
        with booking_lock:
            # Проверяем ещё раз перед созданием
            is_still_free = not any(
                b['date'] == data['date'] and 
                b['time'] == data['time'] and 
                b['master'] == data['master'] and 
                b['status'] == 'confirmed'
                for b in bookings.values()
            )
            
            if not is_still_free:
                await update.message.reply_text(
                    "❌ К сожалению, это время уже заняли другие."
                )
                return
            
            # Создаём запись
            booking_id = f"booking_web_{int(datetime.datetime.now().timestamp())}_{user_id}"
            
            bookings[booking_id] = {
                "id": booking_id,
                "user_id": user_id,
                "user_name": update.effective_user.first_name or "Клиент",
                "username": update.effective_user.username,
                "service": data['service'],
                "master": data['master'],
                "date": data['date'],
                "time": data['time'],
                "price": CONFIG["services"].get(data['service'], 0),
                "status": "confirmed",
                "source": "web_app",  # Отмечаем, что через Web App
                "created_at": datetime.datetime.now().isoformat(),
                "reminder_sent_24h": False,
                "reminder_sent_2h": False
            }
            
            # Сохраняем клиента
            if user_id not in client_data:
                client_data[user_id] = {
                    "name": update.effective_user.first_name or "Клиент",
                    "username": update.effective_user.username,
                    "bookings_count": 1
                }
            else:
                client_data[user_id]["bookings_count"] += 1
            
            # Обновляем статистику
            master_stats[data['master']]["bookings"] += 1
            master_stats[data['master']]["revenue"] += CONFIG["services"].get(data['service'], 0)
            
            # Сохраняем
            save_data()
        
        # Подтверждение
        confirm_text = (
            f"✅ *ЗАПИСЬ ПОДТВЕРЖДЕНА*\n\n"
            f"📋 Номер: `{booking_id}`\n"
            f"✂️ Услуга: {data['service']}\n"
            f"👨‍💼 Мастер: {data['master']}\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n\n"
            f"Вы получите напоминание за 24ч и за 2ч до записи."
        )
        
        await update.message.reply_text(confirm_text, parse_mode="Markdown")
        
        logger.info(f"Web App booking created: {booking_id}")
        
    except json.JSONDecodeError:
        logger.error("Не удалось распарсить JSON из Web App")
        await update.message.reply_text("❌ Ошибка обработки данных")
    except Exception as e:
        logger.error(f"Ошибка Web App handler: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

print("✅ WEB APP ОБРАБОТЧИК ДОБАВЛЕН")
```

---

## ✅ ИСПРАВЛЕНИЕ #6: Обновить start_booking с системой ролей

**ЗАМЕНИТЬ функцию start_booking (строки 247-265):**

```python
async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню в зависимости от роли пользователя"""
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    
    if role == 'admin':
        await show_admin_menu(update, context)
    elif role == 'master':
        await show_master_menu(update, context)
    else:
        await show_client_menu(update, context)

print("✅ START_BOOKING ОБНОВЛЕНА ДЛЯ РОЛЕЙ")
```

---

## ✅ ИСПРАВЛЕНИЕ #7: Добавить функции сохранения данных

**ЗАМЕНИТЬ функции load_data() и save_data() (строки 762+):**

```python
def load_data():
    """Загрузить данные из JSON файлов"""
    global bookings, client_data, master_stats
    
    try:
        if os.path.exists('data/bookings.json'):
            with open('data/bookings.json', 'r', encoding='utf-8') as f:
                bookings = json.load(f)
            print(f"✅ Загружено {len(bookings)} записей")
    except Exception as e:
        logger.error(f"Ошибка при загрузке bookings: {e}")
    
    try:
        if os.path.exists('data/client_data.json'):
            with open('data/client_data.json', 'r', encoding='utf-8') as f:
                client_data = json.load(f)
            print(f"✅ Загружено {len(client_data)} клиентов")
    except Exception as e:
        logger.error(f"Ошибка при загрузке client_data: {e}")
    
    try:
        if os.path.exists('data/master_stats.json'):
            with open('data/master_stats.json', 'r', encoding='utf-8') as f:
                master_stats = json.load(f)
            print(f"✅ Загружена статистика мастеров")
    except Exception as e:
        logger.error(f"Ошибка при загрузке master_stats: {e}")


def save_data():
    """Сохранить данные в JSON файлы"""
    try:
        os.makedirs('data', exist_ok=True)
        
        with open('data/bookings.json', 'w', encoding='utf-8') as f:
            json.dump(bookings, f, indent=2, ensure_ascii=False)
        
        with open('data/client_data.json', 'w', encoding='utf-8') as f:
            json.dump(client_data, f, indent=2, ensure_ascii=False)
        
        with open('data/master_stats.json', 'w', encoding='utf-8') as f:
            json.dump(master_stats, f, indent=2, ensure_ascii=False)
        
        logger.info("✅ Данные сохранены")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")

print("✅ ФУНКЦИИ СОХРАНЕНИЯ ЗАГРУЖЕНЫ")
```

---

## ✅ ИСПРАВЛЕНИЕ #8: Добавить периодическое сохранение

**ДОБАВИТЬ в класс AutoRestartBot, метод setup_handlers():**

```python
# В методе setup_handlers после регистрации остальных обработчиков:

# Добавить обработчик Web App
from telegram.ext import MessageHandler, filters
app.add_handler(MessageHandler(filters.web_app_data, handle_web_app_data))

# Периодическое сохранение данных каждые 5 минут
scheduler.add_job(save_data, 'interval', minutes=5, id='auto_save')

# Периодическая проверка напоминаний
scheduler.add_job(reminder_system.schedule_reminders, 'interval', minutes=30, id='reminders')

logger.info("✅ Периодические задачи зарегистрированы")
```

---

## ✅ ИСПРАВЛЕНИЕ #9: Обновить setup_handlers для новых обработчиков

**В AutoRestartBot.setup_handlers(), добавить регистрацию новых обработчиков:**

```python
# Добавить перед app.add_handler(CommandHandler(...)):

# Обработка Web App данных
from telegram.ext import MessageHandler, filters
app.add_handler(MessageHandler(filters.web_app_data, handle_web_app_data))

# ... остальные обработчики ...
```

---

## 📋 ЧЕКЛИСТ ИЗМЕНЕНИЙ

- [ ] Удалить дублирующиеся обработчики (handle_menu, handle_help)
- [ ] Добавить функции ролей (get_user_role, show_*_menu)
- [ ] Добавить ValidationSystem класс
- [ ] Добавить threading.Lock для защиты от race condition
- [ ] Заменить handle_confirmation с защитой
- [ ] Добавить handle_web_app_data обработчик
- [ ] Обновить start_booking для использования ролей
- [ ] Заменить/обновить load_data() и save_data()
- [ ] Добавить регистрацию Web App обработчика
- [ ] Добавить периодическое сохранение в scheduler
- [ ] Протестировать все функции
- [ ] Запустить в Colab и проверить логи

---

**Статус**: Все исправления готовы к применению
