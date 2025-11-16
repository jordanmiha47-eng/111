````instructions
# Telegram Bot for Barber Shop - AI Coding Agent Instructions

## Project Overview

This is a **production-ready Telegram salon booking bot** (`salon_bot.py`) with **Telegram Mini App** web interface. Built on `python-telegram-bot` + `APScheduler`, it handles:
- 📱 Telegram bot with inline calendars and keyboard UIs  
- 🎨 Web App (ZAVTRA.live design with purple/lime gradients)
- 👨‍💼 Master scheduling with vacations and smart slot allocation
- 💼 Multi-role admin/master/client panels with analytics
- ⏰ Background reminder system (24h and 2h before appointments)
- 🔄 Auto-restart with health checks in Colab/production
- ⭐ Rating system with automatic review requests
- 💬 Comment/review functionality for appointments

**Reference implementations**: `UltraCalendar` (emoji-rich date picker), `SmartScheduler` (vacation/slot logic), `RealReminderSystem` (APScheduler + Telegram), `AutoRestartBot` (production loop), `MasterDeletionSystem`, `MasterEditingSystem`, `PriceEditingSystem`, `ReviewCommentSystem`, `PhoneValidationSystem`.

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
# Edit CONFIG at top of salon_bot.py BEFORE running:
# - Set CONFIG["token"] from @BotFather
# - Set CONFIG["admin_id"] to your Telegram ID
# - Configure CONFIG["masters"] and CONFIG["services"]
```

### Database Schema (SQLite, auto-created)
```sql
-- Appointments table
CREATE TABLE appointments (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    master TEXT,
    service TEXT,
    appointment_date DATE,
    appointment_time TIME,
    price REAL,
    status TEXT,  -- 'confirmed', 'cancelled', 'completed'
    created_at DATETIME
);

-- Masters table  
CREATE TABLE masters (
    name TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    specialization TEXT,  -- JSON list
    rating REAL,
    working_days TEXT  -- JSON
);

-- Clients table
CREATE TABLE clients (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    phone TEXT,
    created_at DATETIME
);

-- Ratings table
CREATE TABLE ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id TEXT,
    master_name TEXT,
    client_id INTEGER,
    rating INTEGER,  -- 1-5
    comment TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (master_name) REFERENCES masters(name)
);

-- Settings table (for persistence)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT  -- JSON or string value
);
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

### Implementation Pattern for New Features
When adding new functionality, follow this pattern:

1. **Create a System Class** (e.g., `MasterDeletionSystem`, `ReviewCommentSystem`)
   ```python
   class NewFeatureSystem:
       """System description"""
       
       @staticmethod
       async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
           """Main handler"""
           pass
       
       @staticmethod
       async def helper_method(...):
           """Helper method"""
           pass
   ```

2. **Use ConversationHandler for Multi-step Flows**
   ```python
   conv_handler = ConversationHandler(
       entry_points=[CallbackQueryHandler(pattern="^pattern_")],
       states={
           "STATE_NAME": [
               MessageHandler(filters.TEXT & ~filters.COMMAND, handler_method)
           ]
       },
       fallbacks=[CommandHandler("cancel", cancel_handler)]
   )
   application.add_handler(conv_handler)
   ```

3. **Always Save to Database**
   - Get cursor: `cursor = db.conn.cursor()`
   - Execute query with parameters (prevent SQL injection)
   - Commit: `db.conn.commit()`
   - Example: `cursor.execute('UPDATE masters SET X = ? WHERE Y = ?', (value1, value2))`

4. **Send Notifications with Proper Error Handling**
   ```python
   try:
       app = Application.builder().token(CONFIG["token"]).build()
       await app.bot.send_message(chat_id, text, parse_mode="Markdown")
   except Exception as e:
       print(f"❌ Error: {e}")
   ```

### Configuration Structure
```python
CONFIG = {
    "token": "YOUR_TOKEN",
    "admin_id": 5892547881,
    "salon_name": "Чародейка",
    "masters": {
        "Дмитрий": {
            "telegram_id": 5892547881,
            "specialization": ["стрижка", "бритье"]
        }
    },
    "services": {"Женская стрижка": 500, "Мужская стрижка": 400},
    "salon_info": {
        "address": "Азовская улица, 4, 1 этаж...",
        "city": "Москва",
        "working_hours": {
            "start": "08:00",
            "end": "18:00",
            "lunch": ["12:00", "13:00"],
            "closed_days": []
        }
    },
    "payments": ["cash", "card", "online"]
}
```
- Edit CONFIG at top of salon_bot.py before running bot
- Prices in services are integers in rubles (₽)

### Callback Naming Conventions
```python
# Master management
"delete_master_<name>" → triggers deletion
"edit_master_<name>" → opens edit menu
"edit_spec_<name>" → change specialization
"edit_tgid_<name>" → change Telegram ID

# Settings
"settings_hours" → show hour presets
"hours_<start>_<end>" → set working hours
"settings_prices" → show price editor
"edit_price_<service>" → edit specific price

# Ratings & Reviews
"rate_<1-5>_<appointment_id>" → submit rating
"skip_comment" → skip review comment
"cancel_reason_<type>" → cancel with reason

# Booking Flow
"service_<name>" → select service
"master_<name>" → select master
"date_<YYYY-MM-DD>" → select date
"time_<HH:MM>" → select time
"confirm_yes/no" → confirm/cancel booking
```

### Date/Time Handling
- **Dates**: `"%Y-%m-%d"` format (e.g., "2024-01-15")
- **Times**: `"%H:%M"` format (e.g., "14:30"), 30-min slots only
- **Lunch break**: Always 13:00-14:00 (hardcoded, should be made configurable)
- **Working hours**: Read from `CONFIG["salon_info"]["working_hours"]`

### Master Specialization Management
- Stored as JSON list in database: `["стрижка", "окрашивание", "укладка"]`
- Update via: `MasterEditingSystem.handle_specialization_input()`
- Display: Join with comma: `", ".join(specialization_list)`

### Phone Number Validation
- Use `PhoneValidationSystem.validate_phone_format(phone_str)`
- Returns: `(is_valid: bool, formatted_phone: str)`
- Formats Russian numbers to: `+7XXXXXXXXXX`
- Accepts: `89991234567`, `+79991234567`, `7-999-123-4567`

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

## Status of Stub Implementation

### ✅ COMPLETED STUBS (Implemented)
1. **Master Deletion System** - Full implementation with cascade booking cancellation
2. **Master Specialization Editing** - Dynamic specialization updates with DB sync
3. **Price Editing System** - Interactive price updates with validation
4. **Review Comment System** - Automatic comment collection after ratings
5. **Phone Validation System** - Format validation and automatic normalization

### 🚨 REMAINING STUBS (Priority Order)

#### HIGH PRIORITY (Critical for operations)
1. **Telegram ID Editing** - Missing handler for `edit_tgid_*` callback in admin panel
   - Fix: Implement `MasterEditingSystem.handle_edit_telegram_id()` + ConversationHandler
   - Impact: Cannot update master contact info without bot restart

2. **Settings Hours Configuration** - `settings_hours` callback has no implementation
   - Fix: Implement hour presets (8-18, 9-19, 10-20) with DB persistence
   - Related to: `CompleteSettingsSystem.handle_hours_preset()`

3. **Settings Prices UI** - `settings_prices` callback incomplete
   - Fix: Create interactive price editor showing all services
   - Related to: `CompleteSettingsSystem.show_price_editor()`

4. **Master Approval System** - New bookings don't auto-request master confirmation
   - Fix: Send confirmation request to master before client confirmation
   - Related to: ConversationHandler for booking workflow

5. **Master Cancellation with Reason** - No reason tracking when master cancels
   - Fix: Implement `MasterCancellationCompleteSystem.handle_master_cancellation_with_reason()`
   - Data should go to: New `cancellation_reasons` table

#### MEDIUM PRIORITY (Nice-to-have features)
6. **Automatic Rating Requests** - Not triggered after appointment completion
   - Fix: Implement `AutomatedRatingSystem.auto_request_rating()` via scheduler
   - Timing: Send 1 hour after appointment end time

7. **Master Review Display** - Masters can't see their own reviews
   - Fix: Implement `AutomatedRatingSystem.show_master_reviews()` 
   - Includes: Average rating, comment display, stats

8. **Review Statistics** - No analytics on rating distribution
   - Missing: Breakdown by star count, comment sentiment, trends
   
9. **Booking History Archive** - Old records not archived, impacts performance
   - Fix: Create archival system for appointments > 6 months old
   - Keep in main DB for master analytics

10. **Data Export (CSV)** - No admin export functionality
    - Fix: Implement CSV generation for bookings, client list, master performance

11. **Database Backup** - No automatic backup system
    - Fix: Add daily backup scheduler to CloudStorage (AWS S3, Google Drive)
    - Related: APScheduler integration in `RealReminderSystem`

12. **Appointment Confirmation Flow** - Master must manually approve each booking
    - Missing: Automatic confirmation if enabled, optional flag in CONFIG

---

## Known Issues & Limitations (Updated)

1. **Session Persistence**: Sessions lost on bot restart (Colab timeout)
   - **Severity**: HIGH - Data loss risk during production use
   - Fix: Save incomplete sessions to DB with TTL
   - Reference: `BookingManagement.restore_session(user_id)`
   - Current behavior: Sessions stored in memory only via `user_sessions = {}`

2. **Reminder Timing**: Uses `APScheduler` with CronTrigger (works but can miss narrow windows)
   - **Severity**: MEDIUM - Some reminders may be lost
   - Fix: Add persistent job store (SQLAlchemy backend) for missed reminders
   - Current: Reminders sent only if bot is running at trigger time
   - Workaround: Don't stop bot during reminder windows (2h-24h before appointments)

3. **No Web App Integration**: WebAppInfo button added but no `/web_app_data` callback handler
   - **Severity**: CRITICAL - Feature completely non-functional
   - FIX NEEDED: Add handler at lines 724-728 in salon_bot.py
   - Missing: Validation of web app data, sync with bot bookings
   - Impact: Booking button leads to dead link, users can't book from Mini App

4. **Duplicate Handlers**: `handle_menu()` and `handle_help()` defined twice
   - **Severity**: MEDIUM - Only last definition is registered
   - FIX: Remove first duplicate definitions
   - Result: Some callback patterns may be ignored, use grep to find duplicates

5. **Date Validation Missing**: No check for booking in past or overbooking same slot
   - **Severity**: HIGH - Data integrity risk
   - FIX NEEDED: Add `ValidationSystem.validate_booking_time()` before confirmation
   - Current: Any date/time accepted if not explicitly in `bookings` dict
   - Risk: Bookings created for dates in the past, same slot double-booked

6. **Concurrency**: In-memory `bookings` dict not thread-safe under concurrent requests
   - **Severity**: CRITICAL (if scaling) - Race condition possible
   - FIX: Add `threading.Lock()` around critical sections or migrate to SQLite
   - Current: Works fine with polling mode (single process), breaks with webhook

7. **Role Selection Missing**: No `/start` handler shows role choice (admin/master/client)
   - **Severity**: MEDIUM - UX issue, all users see same menu
   - FIX NEEDED: Add `RoleSystem.show_role_selection()` at bot startup
   - Current: All users see client booking flow regardless of role
   - Workaround: Users must manually use `/admin` or `/master` commands

8. **Mini-App Untested**: Web App exists but no functional testing or error handling
   - **Severity**: MEDIUM - Deployment risk
   - FIX: Add callback handler for `/web_app_data` with proper error handling
   - Missing: Connection validation, data sanitization, error logging

9. **No Email Notifications**: Only Telegram messages sent, no email backup
   - **Severity**: LOW - Nice-to-have for email preferences
   - Current: All notifications via Telegram only
   - Fix: Add optional email channel via SendGrid/SMTP

10. **Lunch Break Hardcoded**: Lunch break always 13:00-14:00, not configurable
    - **Severity**: LOW - Can be changed in code but not via UI
    - Fix: Add lunch configuration to settings panel
    - Current: Lines 205-211 in UltraCalendar have hardcoded times

11. **Analytics Missing**: No dashboard for master/service performance
    - **Severity**: LOW - Metrics collected but not displayed
    - Data exists: `master_stats`, `analytics_data` globals
    - Fix: Add `/analytics` command with monthly/weekly stats breakdown

12. **No Rate Limiting**: Spam protection for high volume requests
    - **Severity**: MEDIUM - DDoS potential
    - Fix: Add rate limiting per user (e.g., max 5 bookings/day)
    - Related: ConversationHandler timeout, request throttling

---

## Code Examples for Common Tasks

### Adding a New Service
```python
CONFIG['services']['новая услуга'] = 1000  # price in rubles
# Update in: get_service_keyboard() method, then test via /start
# Also add to database if using persistence
cursor.execute('INSERT OR REPLACE INTO services (name, price) VALUES (?, ?)', 
               ('новая услуга', 1000))
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
cursor = db.conn.cursor()
cursor.execute('''
    INSERT INTO appointments 
    (id, user_id, master, service, appointment_date, appointment_time, price, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', (booking["id"], booking["user_id"], booking["master"], booking["service"],
      booking["date"], booking["time"], booking["price"], booking["status"]))
db.conn.commit()
bookings[booking['id']] = booking
```

### Query Bookings by Master
```python
cursor = db.conn.cursor()
cursor.execute('''
    SELECT * FROM appointments 
    WHERE master = ? AND status = 'confirmed' AND appointment_date >= DATE('now')
    ORDER BY appointment_date, appointment_time
''', ('Анна',))
master_bookings = cursor.fetchall()
```

### Send Bulk Notification
```python
async def notify_all_clients(text):
    app = Application.builder().token(CONFIG["token"]).build()
    cursor = db.conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM appointments")
    for (user_id,) in cursor.fetchall():
        try:
            await app.bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to notify {user_id}: {e}")
```

### Implement Master Deletion (Example Stub Fix)
```python
class MasterDeletionSystem:
    @staticmethod
    async def handle_master_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        master_name = query.data.replace("delete_master_", "")
        
        if master_name not in CONFIG["masters"]:
            await query.edit_message_text("❌ Мастер не найден")
            return
        
        # Delete from config
        del CONFIG["masters"][master_name]
        
        # Delete from database
        cursor = db.conn.cursor()
        cursor.execute('DELETE FROM masters WHERE name = ?', (master_name,))
        
        # Cancel future appointments
        cursor.execute('''
            UPDATE appointments SET status = 'cancelled' 
            WHERE master = ? AND appointment_date >= DATE('now')
        ''', (master_name,))
        
        db.conn.commit()
        
        await query.edit_message_text(
            f"✅ Мастер *{master_name}* удален. Все его будущие записи отменены.",
            parse_mode="Markdown"
        )
```

### Implement Rating with Comments (Example Stub Fix)
```python
class ReviewCommentSystem:
    @staticmethod
    async def handle_rating_with_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data.replace("rate_", "").split("_")
        rating = int(data[0])
        appointment_id = data[1]
        
        context.user_data['current_rating'] = rating
        context.user_data['rating_appointment'] = appointment_id
        
        # Get master name
        cursor = db.conn.cursor()
        cursor.execute('SELECT master FROM appointments WHERE id = ?', (appointment_id,))
        master_name = cursor.fetchone()[0]
        context.user_data['rating_master'] = master_name
        
        await query.edit_message_text(
            f"⭐ Спасибо за оценку {rating}!\\n\\n"
            f"Хотите оставить комментарий о работе мастера *{master_name}*?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_comment")
            ]])
        )
        
        return "WAITING_COMMENT"
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
5. Phone number validation: test various formats (89991234567, +79991234567, 7-999-123-4567)
6. Stub implementations: verify rating requests, master deletion, pricing changes work
7. Master notification: ensure masters receive rating notifications and approval requests

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

## Key Developer Commands

- **Debug booking state**: Print `bookings[booking_id]` to inspect complete appointment
- **Inspect user session**: Print `user_sessions[user_id]` to see current booking progress
- **Check master availability**: Call `ultra_calendar.generate_available_times(date_str, master_name)`
- **View master stats**: Print `master_stats[master_name]` for revenue/booking count
- **Cancel vacation**: Remove from `master_schedules[master]["vacations"]` list
- **Clear test data**: `bookings.clear()` resets all bookings (in-memory only)

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

- `salon_bot.py` - Main application (843 lines with all core systems)
- `salon.db` - SQLite database (auto-created on first run)
- `error_log.txt` - Error tracking (auto-created)
- `CONFIG` dict - Configuration (top of salon_bot.py, lines 60-103)
- `web-app/` - Telegram Mini App files (index.html, style.css, app.js)

---

*Last updated: 2024-11 | For AI agents: Focus on completing the 12 remaining stubs in priority order. Always follow the Implementation Pattern for new features. When implementing database operations, use parameterized queries to prevent SQL injection. Use ConversationHandler for multi-step user flows.*
````
