#!/usr/bin/env python3
"""
Telegram Bot for Barber Shop - Salon Booking System
Production-ready implementation with calendar scheduling, master management, and ratings
"""

import logging
import json
import asyncio
import re
import calendar as cal_module
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================
# CONFIGURATION
# ========================

CONFIG = {
    "token": "8281147294:AAEzOek15AiCN0ayZ79KAJjHYlScO-u5NhU",
    "admin_id": 5892547881,
    "salon_name": "Чародейка",
    "masters": {
        "Дмитрий": {
            "telegram_id": 5892547881,
            "specialization": ["стрижка", "бритье", "окрашивание"]
        },
        "Александр": {
            "telegram_id": 5892547881,
            "specialization": ["стрижка", "укладка"]
        }
    },
    "services": {
        "Женская стрижка": 500,
        "Мужская стрижка": 400,
        "Окрашивание": 1500,
        "Бритье": 300,
        "Укладка": 600
    },
    "salon_info": {
        "address": "Азовская улица, 4, 1 этаж",
        "city": "Москва",
        "phone": "+7 (999) 123-45-67",
        "working_hours": {
            "start": "08:00",
            "end": "18:00",
            "lunch": ["12:00", "13:00"],
            "closed_days": [6, 7]  # Saturday, Sunday
        }
    },
    "payments": ["cash", "card", "online"],
    "web_app_url": "https://charodeyka-booking.netlify.app"  # Mini App URL
}

# ========================
# GLOBAL STATE
# ========================

bookings: Dict = {}
client_data: Dict = {}
user_sessions: Dict = {}
master_stats: Dict = {}
master_schedules: Dict = {}
analytics_data: Dict = {}
user_roles: Dict = {}  # Track user role: 'client', 'master', 'admin'

# ========================
# ULTRACALENDAR CLASS
# ========================

class UltraCalendar:
    """Visual calendar grid with emoji indicators"""
    
    def __init__(self, master_name: str):
        self.master_name = master_name
        self.lunch_break = (13, 14)  # 13:00-14:00
        self.tz = pytz.timezone('Europe/Moscow')
        
    def create_visual_calendar(self, date_str: str = None, offset_days: int = 0) -> str:
        """Create visual calendar grid (14 days in 2 rows of 7)"""
        if date_str is None:
            date = datetime.now(self.tz).date()
        else:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Add offset
        date = date + timedelta(days=offset_days)
        
        calendar_text = f"📅 *{date.strftime('%B %Y')}*\n"
        calendar_text += "─" * 35 + "\n"
        
        # Days of week header
        days_header = "ПН  ВТ  СР  ЧТ  ПТ  СБ  ВС\n"
        calendar_text += days_header
        calendar_text += "─" * 35 + "\n"
        
        # Calculate first day of month
        first_day_of_month = date.replace(day=1)
        start_weekday = first_day_of_month.weekday()  # 0=Monday
        
        # Days in month
        days_in_month = cal_module.monthrange(date.year, date.month)[1]
        
        # Build calendar grid
        day = 1
        for week in range(6):
            week_str = ""
            for weekday in range(7):
                cell_pos = week * 7 + weekday
                
                if cell_pos < start_weekday or day > days_in_month:
                    week_str += "    "  # Empty cell
                else:
                    current_date_obj = date.replace(day=day)
                    is_available = self.is_date_available(current_date_obj.strftime("%Y-%m-%d"))
                    
                    if current_date_obj == datetime.now(self.tz).date():
                        emoji = "🔵"  # Today
                    elif is_available:
                        emoji = "🟢"  # Available
                    else:
                        emoji = "🔴"  # Not available
                    
                    week_str += f"{emoji}{day:2d} "
                    day += 1
            
            calendar_text += week_str.rstrip() + "\n"
        
        calendar_text += "─" * 35 + "\n"
        calendar_text += "🟢 свободно | 🔵 сегодня | 🔴 занято"
        
        return calendar_text
    
    def create_time_grid(self, date_str: str) -> tuple:
        """Create time slots in grid format (3 columns, 5 rows)"""
        available_times = self.generate_available_times(date_str)
        
        if not available_times:
            return None, "❌ На эту дату нет свободных слотов"
        
        # Create grid text
        time_text = f"⏰ *Доступные времена на {date_str}*\n"
        time_text += "─" * 25 + "\n"
        
        # Format times in grid (3 columns)
        for i in range(0, len(available_times), 3):
            row = available_times[i:i+3]
            row_text = "  ".join([f"{t:>5}" for t in row])
            time_text += row_text + "\n"
        
        time_text += "─" * 25
        
        return available_times, time_text
    
    def is_date_available(self, date_str: str) -> bool:
        """Check if date is available for booking"""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Check if weekend
        if date_obj.weekday() >= 5:
            return False
        
        # Check if date is in past
        if date_obj.date() < datetime.now(self.tz).date():
            return False
        
        # Check if master has vacation
        if self.master_name in master_schedules:
            vacations = master_schedules[self.master_name].get("vacations", [])
            for vacation in vacations:
                v_start = datetime.strptime(vacation["start"], "%Y-%m-%d").date()
                v_end = datetime.strptime(vacation["end"], "%Y-%m-%d").date()
                if v_start <= date_obj.date() <= v_end:
                    return False
        
        return True
    
    def generate_available_times(self, date_str: str) -> List[str]:
        """Generate available time slots for date"""
        if not self.is_date_available(date_str):
            return []
        
        times = []
        working_hours = CONFIG["salon_info"]["working_hours"]
        lunch = CONFIG["salon_info"]["working_hours"]["lunch"]
        
        start_hour = int(working_hours["start"].split(":")[0])
        end_hour = int(working_hours["end"].split(":")[0])
        lunch_start = int(lunch[0].split(":")[0])
        lunch_end = int(lunch[1].split(":")[0])
        
        for hour in range(start_hour, end_hour):
            for minute in ["00", "30"]:
                # Skip lunch break
                if lunch_start <= hour < lunch_end:
                    continue
                
                time_str = f"{hour:02d}:{minute}"
                
                # Check if slot is booked
                is_booked = any(
                    b["master"] == self.master_name and
                    b["date"] == date_str and
                    b["time"] == time_str and
                    b["status"] == "confirmed"
                    for b in bookings.values()
                )
                
                if not is_booked:
                    times.append(time_str)
        
        return times


# ========================
# ROLE SELECTION
# ========================

async def show_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show role selection menu at start"""
    user = update.effective_user
    user_id = user.id
    
    # Initialize client data
    if user_id not in client_data:
        client_data[user_id] = {
            "user_id": user_id,
            "first_name": user.first_name,
            "phone": None
        }
    
    keyboard = [
        [InlineKeyboardButton("👤 Клиент (записаться)", callback_data="role_client")],
        [InlineKeyboardButton("👨‍💼 Мастер", callback_data="role_master")],
        [InlineKeyboardButton("👨‍💼 Администратор", callback_data="role_admin")],
    ]
    
    await update.message.reply_text(
        f"👋 *Добро пожаловать в {CONFIG['salon_name']}!*\n\n"
        f"Выберите вашу роль:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle role selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    role = query.data.replace("role_", "")
    
    user_roles[user_id] = role
    
    if role == "admin":
        if user_id == CONFIG["admin_id"]:
            await admin_panel(update, context)
        else:
            await query.edit_message_text(
                "❌ *Доступ запрещен. Вы не администратор.*",
                parse_mode=ParseMode.MARKDOWN
            )
    elif role == "master":
        # Check if user is registered as master
        is_master = any(
            info["telegram_id"] == user_id 
            for info in CONFIG["masters"].values()
        )
        if is_master:
            await master_panel(update, context)
        else:
            await query.edit_message_text(
                "❌ *Вы не зарегистрированы как мастер.*",
                parse_mode=ParseMode.MARKDOWN
            )
    else:  # client
        await show_client_menu(update, context)


async def show_client_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show client menu"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("🌐 Веб-приложение", callback_data="open_webapp")],
        [InlineKeyboardButton("⬅️ Изменить роль", callback_data="show_roles")],
    ]
    
    await query.edit_message_text(
        "👤 *КЛИЕНТСКОЕ МЕНЮ*\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


# ========================
# HANDLER FUNCTIONS
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await show_role_selection(update, context)


async def show_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show role selection again"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("👤 Клиент (записаться)", callback_data="role_client")],
        [InlineKeyboardButton("👨‍💼 Мастер", callback_data="role_master")],
        [InlineKeyboardButton("👨‍💼 Администратор", callback_data="role_admin")],
    ]
    
    await query.edit_message_text(
        f"👋 *Выберите вашу роль:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start booking process - show services"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_sessions[user_id] = {}
    
    # Show services with prices
    keyboard = []
    for service, price in CONFIG["services"].items():
        keyboard.append([InlineKeyboardButton(
            f"✂️ {service} — {price}₽",
            callback_data=f"service_{service}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client")])
    keyboard.append([InlineKeyboardButton("☰ Меню", callback_data="back_to_client")])
    
    await query.edit_message_text(
        "🛍️ *ВЫБЕРИТЕ УСЛУГУ:*\n\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection and show masters"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = query.data.replace("service_", "")
    price = CONFIG["services"].get(service, 0)
    
    user_sessions[user_id]["service"] = service
    
    # Show masters with specializations
    keyboard = []
    for master_name, master_info in CONFIG["masters"].items():
        spec = ", ".join(master_info["specialization"])
        keyboard.append([InlineKeyboardButton(
            f"👨‍💼 {master_name}\n   {spec}",
            callback_data=f"master_{master_name}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    keyboard.append([InlineKeyboardButton("☰ Меню", callback_data="back_to_client")])
    
    await query.edit_message_text(
        f"✂️ *УСЛУГА:* {service} ({price}₽)\n\n"
        f"*ВЫБЕРИТЕ МАСТЕРА:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle master selection and show date selector"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    master = query.data.replace("master_", "")
    
    user_sessions[user_id]["master"] = master
    
    # Show calendar with date buttons
    calendar = UltraCalendar(master)
    calendar_text = calendar.create_visual_calendar()
    
    # Generate date buttons (2 columns, next 14 days)
    keyboard = []
    for i in range(14):
        current_date = datetime.now() + timedelta(days=i)
        date_formatted = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%a")
        
        is_available = calendar.is_date_available(date_formatted)
        
        if is_available:
            button_text = f"{day_name} {current_date.strftime('%d.%m')}"
            if i == 0:
                button_text += " (сегодня)"
            keyboard.append(InlineKeyboardButton(
                f"🟢 {button_text}",
                callback_data=f"date_{date_formatted}"
            ))
    
    # Arrange in rows of 2
    keyboard_rows = [keyboard[i:i+2] for i in range(0, len(keyboard), 2)]
    keyboard_rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    keyboard_rows.append([InlineKeyboardButton("☰ Меню", callback_data="back_to_client")])
    
    await query.edit_message_text(
        calendar_text + f"\n👨‍💼 *Мастер: {master}*\n\n*Выберите дату:*",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection and show available times"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    date_str = query.data.replace("date_", "")
    
    user_sessions[user_id]["date"] = date_str
    
    # Show available times
    master = user_sessions[user_id]["master"]
    calendar = UltraCalendar(master)
    available_times, time_text = calendar.create_time_grid(date_str)
    
    if available_times is None:
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")],
            [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
        ]
        await query.edit_message_text(
            time_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Create time buttons (3 columns)
    keyboard = []
    for time_slot in available_times:
        keyboard.append(InlineKeyboardButton(
            f"🕐 {time_slot}",
            callback_data=f"time_{time_slot}"
        ))
    
    # Arrange in rows of 3
    time_rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
    time_rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    time_rows.append([InlineKeyboardButton("☰ Меню", callback_data="back_to_client")])
    
    date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y (%a)")
    
    await query.edit_message_text(
        f"⏰ *Выберите время на {date_formatted}*\n\n"
        f"👨‍💼 *Мастер:* {master}\n"
        f"✂️ *Услуга:* {user_sessions[user_id]['service']}\n\n"
        + time_text,
        reply_markup=InlineKeyboardMarkup(time_rows),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time selection and show confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    time_str = query.data.replace("time_", "")
    
    user_sessions[user_id]["time"] = time_str
    
    # Show confirmation
    session = user_sessions[user_id]
    service = session["service"]
    master = session["master"]
    date = session["date"]
    time = session["time"]
    price = CONFIG["services"].get(service, 0)
    
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    date_formatted = date_obj.strftime("%d.%m.%Y (%A)")
    
    confirmation_text = (
        f"📋 *Проверьте ваши данные:*\n\n"
        f"✂️ *Услуга:*\n   {service}\n\n"
        f"👨‍💼 *Мастер:*\n   {master}\n\n"
        f"📅 *Дата:*\n   {date_formatted}\n\n"
        f"⏰ *Время:*\n   {time}\n\n"
        f"💰 *Стоимость:*\n   {price}₽\n\n"
        f"Подтвердить запись?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="confirm_no")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")],
        [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
    ]
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle booking confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data.replace("confirm_", "")
    
    if action == "no":
        user_sessions[user_id] = {}
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="start_booking")],
            [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
        ]
        await query.edit_message_text(
            "❌ *Запись отменена*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    session = user_sessions[user_id]
    
    # Create booking
    booking_id = f"booking_{int(datetime.now().timestamp())}"
    booking = {
        "id": booking_id,
        "user_id": user_id,
        "service": session["service"],
        "master": session["master"],
        "date": session["date"],
        "time": session["time"],
        "price": CONFIG["services"].get(session["service"], 0),
        "status": "confirmed",
        "created_at": datetime.now().isoformat()
    }
    
    bookings[booking_id] = booking
    
    # Update stats
    if session["master"] not in master_stats:
        master_stats[session["master"]] = {"bookings": 0, "revenue": 0}
    
    master_stats[session["master"]]["bookings"] += 1
    master_stats[session["master"]]["revenue"] += booking["price"]
    
    # Clear session
    user_sessions[user_id] = {}
    
    # Notify admin
    try:
        app = Application.builder().token(CONFIG["token"]).build()
        await app.bot.send_message(
            chat_id=CONFIG["admin_id"],
            text=(
                f"✅ *Новая запись!*\n\n"
                f"✂️ Услуга: {booking['service']}\n"
                f"👨‍💼 Мастер: {booking['master']}\n"
                f"📅 Дата: {booking['date']}\n"
                f"⏰ Время: {booking['time']}\n"
                f"💰 Цена: {booking['price']}₽\n"
                f"👤 Клиент ID: {booking['user_id']}"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться ещё", callback_data="start_booking")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
    ]
    
    date_obj = datetime.strptime(booking["date"], "%Y-%m-%d")
    
    await query.edit_message_text(
        f"✅ *Запись успешно создана!*\n\n"
        f"ID: `{booking_id}`\n"
        f"✂️ {booking['service']}\n"
        f"👨‍💼 {booking['master']}\n"
        f"📅 {date_obj.strftime('%d.%m.%Y (%A)')}\n"
        f"⏰ {booking['time']}\n"
        f"💰 {booking['price']}₽\n\n"
        f"Спасибо за выбор *{CONFIG['salon_name']}*!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's bookings"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    user_bookings = [
        b for b in bookings.values()
        if b["user_id"] == user_id and b["status"] == "confirmed"
    ]
    
    if not user_bookings:
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="start_booking")],
            [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
        ]
        await query.edit_message_text(
            "📭 *У ВАС ПОКА НЕ ТОО ЗАПИСЕЙ*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    text = "📋 *МОИ ЗАПИСИ:*\n\n"
    for i, booking in enumerate(user_bookings[:10], 1):
        date_obj = datetime.strptime(booking['date'], "%Y-%m-%d")
        text += (
            f"{i}. ✂️ {booking['service']}\n"
            f"   👨‍💼 Мастер: {booking['master']}\n"
            f"   📅 {date_obj.strftime('%d.%m.%Y')}\n"
            f"   ⏰ {booking['time']}\n"
            f"   💰 {booking['price']}₽\n"
            f"   ID: `{booking['id']}`\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться ещё", callback_data="start_booking")],
        [InlineKeyboardButton("☰ Меню", callback_data="back_to_client")]
    ]
    
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def open_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open mini app web application"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🌐 Открыть приложение", 
                             web_app=WebAppInfo(url=CONFIG["web_app_url"]))],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client")]
    ]
    
    await query.edit_message_text(
        "🌐 *Веб-приложение для бронирования*\n\n"
        "Нажмите кнопку ниже, чтобы открыть удобное приложение для записи:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != CONFIG["admin_id"]:
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    total_bookings = len([b for b in bookings.values() if b["status"] == "confirmed"])
    total_revenue = sum(b["price"] for b in bookings.values() if b["status"] == "confirmed")
    
    stats_text = (
        f"👨‍💼 *Админ панель {CONFIG['salon_name']}*\n\n"
        f"📊 *Статистика:*\n"
        f"• Всего записей: {total_bookings}\n"
        f"• Общий доход: {total_revenue}₽\n\n"
        f"*Управление:*"
    )
    
    keyboard = [
        [InlineKeyboardButton("👨‍💼 Управление мастерами", callback_data="admin_masters")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("📈 Аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="show_roles")]
    ]
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin masters management"""
    query = update.callback_query
    await query.answer()
    
    masters_text = "👨‍💼 *Управление мастерами*\n\n"
    for master_name, master_info in CONFIG["masters"].items():
        spec = ", ".join(master_info["specialization"])
        masters_text += f"• {master_name}\n  Специализация: {spec}\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить мастера", callback_data="add_master")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]
    ]
    
    await query.edit_message_text(
        masters_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin settings"""
    query = update.callback_query
    await query.answer()
    
    settings_text = (
        "⚙️ *Настройки салона*\n\n"
        f"📍 Адрес: {CONFIG['salon_info']['address']}\n"
        f"📞 Телефон: {CONFIG['salon_info']['phone']}\n"
        f"🕒 Начало работы: {CONFIG['salon_info']['working_hours']['start']}\n"
        f"🕕 Конец работы: {CONFIG['salon_info']['working_hours']['end']}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить настройки", callback_data="edit_settings")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]
    ]
    
    await query.edit_message_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin analytics"""
    query = update.callback_query
    await query.answer()
    
    # Calculate statistics
    total_bookings = len([b for b in bookings.values() if b["status"] == "confirmed"])
    total_revenue = sum(b["price"] for b in bookings.values() if b["status"] == "confirmed")
    
    analytics_text = (
        "📈 *Аналитика*\n\n"
        f"📊 Всего записей: {total_bookings}\n"
        f"💰 Общий доход: {total_revenue}₽\n\n"
        f"*По мастерам:*\n"
    )
    
    for master_name, stats in master_stats.items():
        analytics_text += f"• {master_name}: {stats['bookings']} записей, {stats['revenue']}₽\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]
    ]
    
    await query.edit_message_text(
        analytics_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def master_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master panel"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Find master name
    master_name = None
    for name, info in CONFIG["masters"].items():
        if info["telegram_id"] == user_id:
            master_name = name
            break
    
    if not master_name:
        await query.edit_message_text("❌ Вы не зарегистрированы как мастер")
        return
    
    # Get today's and tomorrow's bookings
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    today_bookings = [
        b for b in bookings.values()
        if b["master"] == master_name and b["date"] == str(today) and b["status"] == "confirmed"
    ]
    
    tomorrow_bookings = [
        b for b in bookings.values()
        if b["master"] == master_name and b["date"] == str(tomorrow) and b["status"] == "confirmed"
    ]
    
    panel_text = f"👨‍💼 *Панель мастера {master_name}*\n\n"
    panel_text += f"📅 *Сегодня ({today}):* {len(today_bookings)} запис(и)\n"
    panel_text += f"📅 *Завтра ({tomorrow}):* {len(tomorrow_bookings)} запис(и)\n\n"
    
    if today_bookings:
        panel_text += "*Записи на сегодня:*\n"
        for booking in today_bookings:
            panel_text += f"  • {booking['time']} - {booking['service']} ({booking['price']}₽)\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="show_roles")]
    ]
    
    await query.edit_message_text(
        panel_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def back_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to client menu"""
    query = update.callback_query
    await query.answer()
    await show_client_menu(update, context)


async def stub_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stub callbacks"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⚙️ *Эта функция находится в разработке*",
        parse_mode=ParseMode.MARKDOWN
    )


# ========================
# MAIN FUNCTION
# ========================

def main():
    """Start the bot"""
    
    # Create the Application
    application = Application.builder().token(CONFIG["token"]).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    
    # Role selection
    application.add_handler(CallbackQueryHandler(handle_role_selection, pattern="^role_"))
    application.add_handler(CallbackQueryHandler(show_roles, pattern="^show_roles$"))
    
    # Client handlers
    application.add_handler(CallbackQueryHandler(show_client_menu, pattern="^back_to_client$"))
    application.add_handler(CallbackQueryHandler(start_booking, pattern="^start_booking$"))
    application.add_handler(CallbackQueryHandler(handle_service, pattern="^service_"))
    application.add_handler(CallbackQueryHandler(handle_master, pattern="^master_"))
    application.add_handler(CallbackQueryHandler(handle_calendar, pattern="^date_"))
    application.add_handler(CallbackQueryHandler(handle_time, pattern="^time_"))
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^confirm_"))
    application.add_handler(CallbackQueryHandler(my_bookings, pattern="^my_bookings$"))
    application.add_handler(CallbackQueryHandler(open_webapp, pattern="^open_webapp$"))
    
    # Admin handlers
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(admin_masters, pattern="^admin_masters$"))
    application.add_handler(CallbackQueryHandler(admin_settings, pattern="^admin_settings$"))
    application.add_handler(CallbackQueryHandler(admin_analytics, pattern="^admin_analytics$"))
    
    # Master handlers
    application.add_handler(CallbackQueryHandler(master_panel, pattern="^master_panel$"))
    
    # Stub handlers
    application.add_handler(CallbackQueryHandler(stub_handler, pattern="^(add_master|edit_settings)$"))
    
    # Error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("✅ БОТ УСПЕШНО ЗАПУЩЕН! 📱")
    logger.info("КОМАНДЫ: /start")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
