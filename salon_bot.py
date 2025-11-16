#!/usr/bin/env python3
"""
Telegram Bot for Barber Shop - Salon Booking System
Production-ready implementation with calendar scheduling, master management, and ratings
"""

import logging
import json
import asyncio
import re
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
    """Visual 7-day calendar grid with emoji indicators"""
    
    def __init__(self, master_name: str):
        self.master_name = master_name
        self.lunch_break = (13, 14)  # 13:00-14:00
        
    def create_visual_calendar(self, date_str: str = None) -> str:
        """Create visual calendar representation"""
        if date_str is None:
            date = datetime.now()
        else:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        
        calendar_text = f"📅 *Календарь мастера {self.master_name}*\n"
        calendar_text += f"*{date.strftime('%B %Y')}*\n\n"
        
        # Show 7 days
        for i in range(7):
            current_date = date + timedelta(days=i)
            date_formatted = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%a")
            
            # Check if date is available
            is_available = self.is_date_available(date_formatted)
            emoji = "🟢" if is_available else "🔴"
            
            if current_date.date() == datetime.now().date():
                emoji = "⚪"  # Today
            
            calendar_text += f"{emoji} {day_name} {current_date.strftime('%d.%m')} `{date_formatted}`\n"
        
        return calendar_text
    
    def is_date_available(self, date_str: str) -> bool:
        """Check if date is available for booking"""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Check if weekend
        if date_obj.weekday() >= 5:
            return False
        
        # Check if date is in past
        if date_obj.date() < datetime.now().date():
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
        
        for hour in range(start_hour, end_hour):
            for minute in ["00", "30"]:
                time_str = f"{hour:02d}:{minute}"
                
                # Skip lunch break
                lunch_start = int(lunch[0].split(":")[0])
                lunch_end = int(lunch[1].split(":")[0])
                if lunch_start <= hour < lunch_end:
                    continue
                
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
        [InlineKeyboardButton("⬅️ Назад (выбор роли)", callback_data="show_roles")],
    ]
    
    await query.edit_message_text(
        "👤 *Клиентское меню*\n\n"
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
    """Start booking process"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_sessions[user_id] = {}
    
    # Show services
    keyboard = []
    for service in CONFIG["services"].keys():
        keyboard.append([InlineKeyboardButton(
            f"✂️ {service}",
            callback_data=f"service_{service}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client")])
    
    await query.edit_message_text(
        "🛍️ *Выберите услугу:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    service = query.data.replace("service_", "")
    
    user_sessions[user_id]["service"] = service
    
    # Show masters
    keyboard = []
    for master_name in CONFIG["masters"].keys():
        keyboard.append([InlineKeyboardButton(
            f"👨‍💼 {master_name}",
            callback_data=f"master_{master_name}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    
    await query.edit_message_text(
        f"🎯 *Услуга:* {service}\n\n*Выберите мастера:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle master selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    master = query.data.replace("master_", "")
    
    user_sessions[user_id]["master"] = master
    
    # Show calendar with date buttons
    calendar = UltraCalendar(master)
    
    # Generate date buttons
    keyboard = []
    for i in range(7):
        current_date = datetime.now() + timedelta(days=i)
        date_formatted = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%a")
        
        is_available = calendar.is_date_available(date_formatted)
        
        if is_available:
            button_text = f"📅 {day_name} {current_date.strftime('%d.%m')}"
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"date_{date_formatted}"
            )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    
    calendar_text = calendar.create_visual_calendar()
    
    await query.edit_message_text(
        calendar_text + "\n*Выберите дату:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection from callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    date_str = query.data.replace("date_", "")
    
    user_sessions[user_id]["date"] = date_str
    
    # Show available times
    master = user_sessions[user_id]["master"]
    calendar = UltraCalendar(master)
    available_times = calendar.generate_available_times(date_str)
    
    if not available_times:
        await query.edit_message_text(
            "❌ *На эту дату нет свободных слотов*\n\n"
            "Выберите другую дату.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    keyboard = []
    for time_slot in available_times:
        keyboard.append([InlineKeyboardButton(
            f"🕐 {time_slot}",
            callback_data=f"time_{time_slot}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start_booking")])
    
    await query.edit_message_text(
        f"⏰ *Доступные времена на {date_str}:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    time_str = query.data.replace("time_", "")
    
    user_sessions[user_id]["time"] = time_str
    
    # Show confirmation
    session = user_sessions[user_id]
    service = session["service"]
    master = session["master"]
    date = session["date"]
    time = session["time"]
    price = CONFIG["services"].get(service, 0)
    
    confirmation_text = (
        f"✂️ *Услуга:* {service}\n"
        f"👨‍💼 *Мастер:* {master}\n"
        f"📅 *Дата:* {date}\n"
        f"🕐 *Время:* {time}\n"
        f"💰 *Цена:* {price}₽\n\n"
        f"*Подтвердить запись?*"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="confirm_no")
        ]
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
    
    user_id = update.effective_user.id
    action = query.data.replace("confirm_", "")
    
    if action == "no":
        user_sessions[user_id] = {}
        await query.edit_message_text("❌ Запись отменена")
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
                f"✅ *Новая запись!*\n"
                f"Услуга: {booking['service']}\n"
                f"Мастер: {booking['master']}\n"
                f"Дата: {booking['date']} {booking['time']}\n"
                f"Цена: {booking['price']}₽"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")
    
    await query.edit_message_text(
        f"✅ *Запись успешно создана!*\n\n"
        f"ID: `{booking_id}`\n"
        f"Спасибо за выбор {CONFIG['salon_name']}!",
        parse_mode=ParseMode.MARKDOWN
    )


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's bookings"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    user_bookings = [
        b for b in bookings.values()
        if b["user_id"] == user_id and b["status"] == "confirmed"
    ]
    
    if not user_bookings:
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="start_booking")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client")]
        ]
        await query.edit_message_text(
            "📭 *У вас пока нет записей*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    text = "📋 *Ваши записи:*\n\n"
    for booking in user_bookings[:10]:
        text += (
            f"✂️ {booking['service']}\n"
            f"👨‍💼 {booking['master']}\n"
            f"📅 {booking['date']} {booking['time']}\n"
            f"💰 {booking['price']}₽\n"
            f"─────────\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client")]
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
