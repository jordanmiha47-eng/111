# Telegram Bot for Barber Shop - AI Coding Agent Instructions

## Project Overview

This is a **production-ready Telegram salon booking bot** (`salon_bot.py`) with **Telegram Mini App** web interface. Built on `python-telegram-bot` + `APScheduler`, it handles:
- 📱 Telegram bot with inline calendars and keyboard UIs
- 🎨 Web App (ZAVTRA.live design with purple/lime gradients)
- 👨‍💼 Master scheduling with vacations and smart slot allocation
- 💼 Multi-role admin/master/client panels with analytics
- ⏰ Background reminder system (24h and 2h before appointments)
- 🔄 Auto-restart with health checks in Colab/production

**Reference implementations**: `UltraCalendar` (emoji-rich date picker), `SmartScheduler` (vacation/slot logic), `RealReminderSystem` (APScheduler + Telegram), `AutoRestartBot` (production loop).

---

## Big Picture Architecture

### Core Components (salon_bot.py, 843 lines)

1. **UltraCalendar Class** (lines 116-221)
   - Visual 7-day calendar grid with emoji indicators: 🔴 unavailable, 🟢 available, ⚪ today
   - Month navigation (◀️/▶️), lunch break handling (13:00-14:00 by default)
   - Key methods: `create_visual_calendar()`, `is_date_available()`, `generate_available_times()`
   - Storage: Filters booked appointments from global `bookings` dict

2. **SmartScheduler Class** (lines 225-241)
   - Master vacation management: `set_master_vacation(master, start, end)`
   - Auto-cancels conflicting bookings during vacations
   - Data stored in `master_schedules[master]["vacations"]` list

3. **RealReminderSystem Class** (lines 608-665)
   - Uses `APScheduler` with CronTrigger for background jobs
   - Two-stage reminders: 24h before + 2h before appointments
   - Methods: `schedule_reminders()`, `send_reminder()`, `health_check()`
   - Integrates with Telegram API via `Application.bot.send_message()`

4. **AutoRestartBot Class** (lines 667-735)
   - Wraps bot lifecycle with error recovery
   - Polling mode for Colab compatibility
   - Methods: `setup_handlers()`, `run_bot()`, `run_forever()` (infinite retry loop)
   - Health check via `scheduler.health_check()` every 5 minutes

### Web App Integration (folder `web-app/`)
   - **index.html** - Responsive booking interface
   - **style.css** - Gradient design (purple #A855F7 + lime #BFFF00)
   - **app.js** - Telegram Mini App SDK, `sendData()` callback to bot
   - **Deployment**: Netlify/Vercel/GitHub Pages (see DEPLOYMENT.md)

---

## Configuration & Global State

### CONFIG Dictionary (lines 60-103)
- **token**: Telegram bot token from @BotFather
- **admin_id**: Telegram ID of administrator (5892547881 for Чародейка salon)
- **masters**: Dict mapping master names to Telegram IDs
- **services**: Dict mapping service names to prices (initialized at 0)
- **salon_info**: working_hours (8:00-18:00, lunch 12:00-13:00), address, city
- **payments**: Supported payment methods

### Global State Variables (lines 105-112)
- `bookings = {}` - All appointments (key: booking_id, value: booking dict)
- `client_data = {}` - User profiles (key: user_id, value: client info)
- `user_sessions = {}` - Active booking sessions (key: user_id, value: {service, master, date, time})
- `master_stats = {}` - Per-master metrics (bookings count, revenue, rating)
- `master_schedules = {}` - Vacation periods and working days
- `analytics_data = {}` - Counter for popularity metrics

### Handler Functions (lines 247-664)
- **start_booking()** - Entry point, shows service selection + Web App button
- **handle_service()** - Saves service choice to `user_sessions[user_id]["service"]`
- **handle_master()** - Shows available masters, saves to session
- **handle_calendar()** - Renders UltraCalendar via `ultra_calendar.create_visual_calendar()`
- **handle_time()** - Filters available times via `ultra_calendar.generate_available_times()`
- **handle_confirmation()** - Creates booking object, stores in `bookings` dict
- **my_bookings()** - Lists user's confirmed bookings from `bookings` dict
- **admin_panel()** - Shows global statistics (all bookings, revenue by master)
- **master_panel()** - Shows today/tomorrow bookings for authenticated master

---

## Critical Workflows & Commands

### Building and Running

```bash
# Install dependencies
pip install python-telegram-bot apscheduler pytz

# Start bot (runs with auto-restart loop in AutoRestartBot.run_forever())
python salon_bot.py
# Output: ✅ БОТ УСПЕШНО ЗАПУЩЕН! 📱 КОМАНДЫ: /start, /mybookings, /admin, /master

# In Colab (auto-detects via nest_asyncio)
# Bot will restart on errors with exponential backoff (max 30s wait)
```

### Key Developer Commands

- **Debug booking state**: Print `bookings[booking_id]` to inspect complete appointment
- **Inspect user session**: Print `user_sessions[user_id]` to see current booking progress
- **Check master availability**: Call `ultra_calendar.generate_available_times(date_str, master_name)`
- **View master stats**: Print `master_stats[master_name]` for revenue/booking count
- **Cancel vacation**: Remove from `master_schedules[master]["vacations"]` list
- **Clear test data**: `bookings.clear()` resets all bookings (in-memory only)

---

## Project-Specific Conventions

### Session Management Pattern
- **State machine in memory**: `user_sessions[user_id]` tracks booking progress
- Flow: `{"service": str}` → `{"service", "master"}` → `{"service", "master", "date"}` → `{"service", "master", "date", "time"}`
- On confirmation: Session cleared, booking saved to `bookings` dict (in-memory only)
- **Gotcha**: Sessions lost on restart; no persistence to DB yet

### Configuration Structure
```python
CONFIG = {
    "token": "YOUR_TOKEN",
    "admin_id": 5892547881,
    "salon_name": "Чародейка",
    "masters": {"Дмитрий": 5892547881, "Александр": 5892547881},
    "services": {"Женская стрижка": 0, "Мужская стрижка": 0},
    "salon_info": {
        "address": "Азовская улица, 4, 1 этаж...",
        "working_hours": {
            "start": "08:00",
            "end": "18:00",
            "lunch": ["12:00", "13:00"],
            "closed_days": []
        }
    }
}
```
- Edit CONFIG at top of salon_bot.py before running bot
- Prices in services can be 0 (will display as "₽" with no price)

### Date/Time Handling
- Dates: `"%Y-%m-%d"` strings (e.g., "2024-01-15")
- Times: `"%H:%M"` strings (e.g., "10:30"), 30-min slots
- Lunch break: Always skipped in `generate_available_times()` (lines 205-211)
- Working hours: Read from `CONFIG["salon_info"]["working_hours"]`, 24/7 by default

### Callback Pattern (Inline Buttons)
```python
"service_<name>" → saves service, shows masters
"master_<name>" → saves master, shows calendar  
"date_<YYYY-MM-DD>" → saves date, shows times
"time_<HH:MM>" → saves time, shows confirmation
"confirm_yes/no" → creates booking or resets session
"cancel_booking_<id>" → changes booking status to 'cancelled'
```

### Data Storage Strategy
- **In-memory only**: `bookings`, `client_data`, `user_sessions`, `master_stats`
- No database (unlike reference README that mentions SQLite)
- Data lost on bot restart → Log files in `logs/` dir for audit trail
- **Recommendation**: Add JSON persistence or SQLite for production

---

## Integration Points & Dependencies

### External APIs
- **Telegram Bot API**: Via `python-telegram-bot` Application (polling mode)
- **APScheduler**: Background job scheduling for reminders (CronTrigger)
- No external AI/NLP integration in current version

### Internal Message Communication
- Notifications sent directly: `await app.bot.send_message(chat_id, text)`
- Admin alerts on new bookings: Send to `CONFIG['admin_id']` immediately after confirmation
- Master reminders: `RealReminderSystem.schedule_reminders()` queries bookings dict, schedules via APScheduler

### Web App Integration (Telegram Mini App)
- **URL in bot**: Lines 255-260, `WebAppInfo(url="https://charodeyka-booking.netlify.app")`
- **sendData from Web App**: `Telegram.WebApp.sendData(JSON)` → `/web_app_data` callback (lines 724-728)
- **Data sync**: Web app sends `{service, master, date, time, user_id}`, bot validates and creates booking
- **Deployment**: See DEPLOYMENT.md for Netlify/Vercel setup

### Reminder System (Real Integration)
```python
# RealReminderSystem (lines 608-665):
scheduler.add_job(schedule_reminders, 'cron', hour='*')  # Every hour
schedule_reminders() checks each booking, schedules send_reminder() via asyncio
send_reminder() uses await app.bot.send_message() for actual notification
```

---

## Known Issues & Limitations

1. **Session Persistence**: Sessions lost on bot restart (Colab timeout)
   - Fix: Save incomplete sessions to DB with TTL
   - Reference: `BookingManagement.restore_session(user_id)`

2. **Reminder Timing**: Uses `APScheduler` with CronTrigger (works but can miss narrow windows)
   - Fix: Add persistent job store (SQLAlchemy backend) for missed reminders
   - Current: Reminders sent only if bot is running at trigger time

3. **No Web App Integration**: WebAppInfo button added but no `/web_app_data` callback handler
   - **CRITICAL FIX NEEDED**: Add handler at lines 724-728 in salon_bot.py
   - Missing: Validation of web app data, sync with bot bookings

4. **Duplicate Handlers**: `handle_menu()` and `handle_help()` defined twice (lines 462 + 487, 476 + 501)
   - **FIX**: Remove duplicate definitions
   - Result: Only last definition is registered, causing ignored entries

5. **Date Validation Missing**: No check for booking in past or overbooking same slot
   - **FIX NEEDED**: Add `ValidationSystem.validate_booking_time()` before confirmation
   - Current: Any date/time accepted if not explicitly in `bookings` dict

6. **Concurrency**: In-memory `bookings` dict not thread-safe under concurrent requests
   - **FIX**: Add `threading.Lock()` around critical sections or migrate to DB

7. **Role Selection Missing**: No `/start` handler shows role choice (admin/master/client)
   - **FIX NEEDED**: Add `RoleSystem.show_role_selection()` at bot startup
   - Current: All users see same menu regardless of role

8. **Mini-App Untested**: Web App exists but no functional testing or error handling
   - **FIX**: Add callback handler for `/web_app_data` with proper validation

---

## Code Examples for Common Tasks

### Adding a New Service
```python
CONFIG['services']['новая услуга'] = 1000  # price
# Update in: get_service_keyboard() method, then test via /start
```

### Creating Appointment Programmatically
```python
booking = {
    "id": f"booking_{int(time.time())}",
    "user_id": user_id,
    "service": "стрижка",
    "master": "Анна",
    "date": "2024-01-20",
    "time": "14:30",
    "price": 500,
    "status": "confirmed"
}
db.save_appointment(booking)
bookings[booking['id']] = booking
```

### Query Bookings by Master
```python
master_bookings = [b for b in bookings.values() 
                   if b['master'] == 'Анна' and b['status'] == 'confirmed']
```

### Send Bulk Notification
```python
async def notify_all_clients(text):
    app = Application.builder().token(CONFIG["token"]).build()
    cursor = db.conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM appointments")
    for (user_id,) in cursor.fetchall():
        await app.bot.send_message(user_id, text)
```

---

## Testing Strategy

- **Booking flow**: Test all 5 steps (service → master → date → time → confirm) with dummy user
- **Role routing**: Verify `/start` shows correct menu for admin, master, client
- **Error handling**: Check `error_log.txt` entries, test invalid dates/times
- **DB operations**: Run `SELECT COUNT(*)` before/after new bookings
- **Reminders**: Monitor scheduled tasks, check delivery success

### Test Cases to Add
1. Overbooking same slot: prevent via `available_times` check
2. Booking in past: reject via `datetime < now()` comparison
3. Master unavailability: show empty times, prompt reschedule
4. Concurrent users: simulate 5+ users booking simultaneously

---

## Recommendations for Enhancement

1. **Upgrade to PostgreSQL** + async driver (asyncpg) for scale
2. **Add Web Dashboard**: React/Vue frontend for analytics export
3. **Implement QR codes** for check-in at salon
4. **WhatsApp integration**: Replicate Telegram flows to WhatsApp Business API
5. **Payment gateway**: Stripe/YooKassa pre-booking deposit
6. **Machine learning**: Recommend masters/times based on client history
7. **Multi-language support**: Add i18n translations for Russian/English
8. **Rate limiting**: Prevent booking bot spam (max 3 bookings/day per user)

---

## File Structure Reference

- `barber_bot.py` - Main application (Blocks 1-15)
- `barber.db` - SQLite database (auto-created)
- `error_log.txt` - Error tracking (auto-created)
- `CONFIG` dict - Configuration (top of barber_bot.py)

---

*Last updated: 2024-01 | For AI agents: Focus on role-based access control, calendar logic, and DB schema when adding features.*
