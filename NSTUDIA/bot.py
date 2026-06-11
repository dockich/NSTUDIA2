import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WORKS_COUNT = 10
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # абсолютный путь к папке с ботом

# Состояния для диалогов
SERVICE, NAME, CONTACT, DATE, TIME = range(5)
CHOOSING_CANCEL_BOOKING = 10
CHOOSING_SLOT_DATE = 11
CHOOSING_SLOT_TIME = 12

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            name        TEXT NOT NULL,
            phone       TEXT NOT NULL,
            service     TEXT NOT NULL,
            date        TEXT NOT NULL,
            time        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("PRAGMA table_info(clients)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'telegram_id' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN telegram_id INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

# ==================== КЛАВИАТУРЫ ====================
def get_start_reply_keyboard(user_id):
    keyboard = [
        ["📝 Записаться"],
        ["💼 Мои работы"],
        ["💰 Прайс-лист", "ℹ️ О нас", "📞 Контакты"],
        ["📅 Свободные даты", "❌ Отменить запись"],
    ]
    if str(user_id) == ADMIN_ID:
        keyboard.append(["📋 Список записей"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_inline_service_keyboard():
    keyboard = [
        [InlineKeyboardButton("💇‍♀️ Прическа", callback_data="hairstyle")],
        [InlineKeyboardButton("💄 Макияж", callback_data="makeup")],
        [InlineKeyboardButton("✂️ Женская стрижка", callback_data="womens_haircut")],
        [InlineKeyboardButton("💁‍♀️ Наращивание волос", callback_data="hair_extensions")],
        [InlineKeyboardButton("📋 Консультация", callback_data="consultation")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_booking_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_inline_date_keyboard():
    keyboard = []
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d.%m (%a)")
        callback = f"date_{day.strftime('%Y-%m-%d')}"
        keyboard.append([InlineKeyboardButton(date_str, callback_data=callback)])
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="cancel_booking_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_inline_time_keyboard(booked_times=None):
    if booked_times is None:
        booked_times = []
    slots = []
    for hour in range(10, 21):
        time_str = f"{hour:02d}:00"
        if time_str not in booked_times:
            slots.append([InlineKeyboardButton(time_str, callback_data=f"time_{time_str}")])
    if not slots:
        slots = [[InlineKeyboardButton("Нет свободных слотов", callback_data="no_slots")]]
    slots.append([InlineKeyboardButton("🔙 Отмена", callback_data="cancel_booking_menu")])
    return InlineKeyboardMarkup(slots)

def get_contact_reply_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

# ==================== РАБОТА С ФОТО (МОИ РАБОТЫ) ====================
def get_works_media(page):
    """Возвращает InputMediaPhoto или None, если файл не найден."""
    page = max(0, min(page, WORKS_COUNT - 1))
    photo_num = page + 1
    works_dir = os.path.join(BASE_DIR, "works")
    path = os.path.join(works_dir, f"photo{photo_num}.jpg")
    if not os.path.exists(path):
        path_png = os.path.join(works_dir, f"photo{photo_num}.png")
        if not os.path.exists(path_png):
            return None
        path = path_png

    captions = [
        "✨ <b>Мои работы</b> – Стильная стрижка",
        "Прическа на выпускной",
        "Вечерний макияж",
        "Наращивание волос",
        "Креативное окрашивание",
        "Свадебный образ",
        "Мужская стрижка",
        "Детская стрижка",
        "Укладка на длинные волосы",
        "Биозавивка",
    ]
    caption = captions[page] if page < len(captions) else f"Работа #{photo_num}"
    return InputMediaPhoto(open(path, "rb"), caption=caption, parse_mode="HTML")

def get_inline_work_pages_keyboard(page):
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"works_prev_{page}"),
            InlineKeyboardButton(f"{page+1}/{WORKS_COUNT}", callback_data="works_page"),
            InlineKeyboardButton("➡️", callback_data=f"works_next_{page}"),
        ],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def show_main_menu(chat_id, context, user_id, text=None):
    if text is None:
        text = "✨ Добро пожаловать в NSTUDIA! ✨\n\nВыберите действие:"
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=get_start_reply_keyboard(user_id)
    )

# ==================== ОБРАБОТЧИКИ КНОПОК ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id)
    return ConversationHandler.END

async def cancel_booking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.delete()
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id, "Действие отменено.")
    context.user_data.clear()
    return ConversationHandler.END

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id)
    return ConversationHandler.END

async def works_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    if action.startswith("works_next_"):
        page = int(action.split("_")[-1]) + 1
        if page >= WORKS_COUNT:
            page = 0
    elif action.startswith("works_prev_"):
        page = int(action.split("_")[-1]) - 1
        if page < 0:
            page = WORKS_COUNT - 1
    else:
        return
    media = get_works_media(page)
    if media:
        await query.edit_message_media(media=media, reply_markup=get_inline_work_pages_keyboard(page))
    else:
        await query.edit_message_text(
            "Фото не найдено. Убедитесь, что в папке `works` есть photo1.jpg ... photo10.jpg",
            reply_markup=get_inline_work_pages_keyboard(page)
        )

async def get_bookings_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_ID:
        await update.message.reply_text("Доступ запрещён.")
        return
    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT name, phone, service, date, time, telegram_id
        FROM clients
        WHERE date >= ?
        ORDER BY date, time
    """, (today,))
    bookings = cursor.fetchall()
    conn.close()
    if not bookings:
        await update.message.reply_text("Нет предстоящих записей.")
        return
    message = "📋 <b>Список записей:</b>\n\n"
    service_map = {
        "hairstyle": "Прическа",
        "makeup": "Макияж",
        "womens_haircut": "Женская стрижка",
        "hair_extensions": "Наращивание волос",
        "consultation": "Консультация"
    }
    for name, phone, service, date, time, tg_id in bookings:
        service_display = service_map.get(service, service)
        message += f"👤 {name}\n📞 {phone}\n💇 {service_display}\n📅 {date} {time}\n<a href=\"tg://user?id={tg_id}\">✉️ Написать</a>\n\n"
    await update.message.reply_text(message, parse_mode="HTML")

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "📝 Записаться":
        await update.message.reply_text("Выберите услугу:", reply_markup=get_inline_service_keyboard())
        return SERVICE
    elif text == "💼 Мои работы":
        media = get_works_media(0)
        if media:
            await update.message.reply_photo(
                photo=media.media,
                caption=media.caption,
                parse_mode="HTML",
                reply_markup=get_inline_work_pages_keyboard(0)
            )
        else:
            await update.message.reply_text(
                "📁 Фотографии временно недоступны.\n"
                "Пожалуйста, загрузите фото в папку `works` на сервере."
            )
        return ConversationHandler.END
    elif text == "💰 Прайс-лист":
        msg = "📋 <b>Прайс-лист:</b>\n\n💇‍♀️ Прическа — от 2000₽\n💄 Макияж — от 2500₽\n✂️ Женская стрижка — от 500₽\n💁‍♀️ Наращивание волос — от 5000₽\н📋 Консультация — бесплатно"
        await update.message.reply_text(msg, parse_mode="HTML")
        await show_main_menu(update.effective_chat.id, context, user_id)
        return ConversationHandler.END
    elif text == "ℹ️ О нас":
        msg = "ℹ️ <b>О нас:</b>\n\nNSTUDIA — студия красоты с профессиональными мастерами.\nМы работаем с 2019 года и знаем всё о красоте!\n\n✨ Только качественные материалы\n✨ Индивидуальный подход\n✨ Уютная атмосфера"
        await update.message.reply_text(msg, parse_mode="HTML")
        await show_main_menu(update.effective_chat.id, context, user_id)
        return ConversationHandler.END
    elif text == "📞 Контакты":
        msg = ("📞 <b>Контакты:</b>\n\n📍 Дальнереченск, Ул 50 лет октября 54, (База жми дави 2 этаж)\n"
               "📱 Телефон: +7 (924) 130-32-31\n📧 Email: botnaruc78@mail.ru\n🕐 Режим работы: 10:00 - 20:00")
        await update.message.reply_text(msg, parse_mode="HTML")
        await show_main_menu(update.effective_chat.id, context, user_id)
        return ConversationHandler.END
    elif text == "📅 Свободные даты":
        await update.message.reply_text("📅 Выберите дату:", reply_markup=get_inline_date_keyboard())
        return CHOOSING_SLOT_DATE
    elif text == "❌ Отменить запись":
        conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT id, service, date, time FROM clients WHERE telegram_id = ? ORDER BY date, time", (user_id,))
        bookings = cursor.fetchall()
        conn.close()
        if not bookings:
            await update.message.reply_text("❌ У вас нет активных записей.")
            await show_main_menu(update.effective_chat.id, context, user_id)
            return ConversationHandler.END
        keyboard = []
        service_map = {"hairstyle": "Прическа", "makeup": "Макияж", "womens_haircut": "Стрижка",
                       "hair_extensions": "Наращивание", "consultation": "Консультация"}
        for bid, service, date, time in bookings:
            service_name = service_map.get(service, service)
            btn_text = f"{service_name} - {date} {time}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_cancel_{bid}")])
        keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="cancel_booking_menu")])
        await update.message.reply_text("Выберите запись для отмены:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_CANCEL_BOOKING
    else:
        await show_main_menu(update.effective_chat.id, context, user_id, "Пожалуйста, используйте кнопки меню:")
        return ConversationHandler.END


# ==================== ДИАЛОГ ЗАПИСИ ====================
async def service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service = query.data
    service_names = {
        "hairstyle": "Прическа",
        "makeup": "Макияж",
        "womens_haircut": "Женская стрижка",
        "hair_extensions": "Наращивание волос",
        "consultation": "Консультация"
    }
    context.user_data["service"] = service
    await query.edit_message_text(f"✅ Выбрана услуга: {service_names[service]}\n\n✍️ Введите ваше имя:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "📱 Пожалуйста, поделитесь своим номером телефона:",
        reply_markup=get_contact_reply_keyboard()
    )
    return CONTACT

async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        context.user_data["phone"] = contact.phone_number
        await update.message.reply_text(
            f"✅ Номер {contact.phone_number} сохранён.\n\n📅 Теперь выберите дату:",
            reply_markup=get_inline_date_keyboard()
        )
        return DATE
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, используйте кнопку «Поделиться номером телефона».",
            reply_markup=get_contact_reply_keyboard()
        )
        return CONTACT

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_")[1]
    context.user_data["date"] = date_str
    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM clients WHERE date = ?", (date_str,))
    booked = [row[0] for row in cursor.fetchall()]
    conn.close()
    await query.edit_message_text(
        f"📅 {date_str}\n⏰ Выберите время:",
        reply_markup=get_inline_time_keyboard(booked)
    )
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_slot = query.data.split("_")[1]
    user_id = update.effective_user.id
    name = context.user_data["name"]
    phone = context.user_data["phone"]
    service = context.user_data["service"]
    date = context.user_data["date"]

    service_names = {
        "hairstyle": "Прическа",
        "makeup": "Макияж",
        "womens_haircut": "Женская стрижка",
        "hair_extensions": "Наращивание волос",
        "consultation": "Консультация"
    }
    service_display = service_names.get(service, service)

    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clients (telegram_id, name, phone, service, date, time) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, phone, service, date, time_slot)
    )
    conn.commit()
    conn.close()

    await query.edit_message_text(
        f"✅ Запись оформлена!\n\n"
        f"Услуга: {service_display}\nИмя: {name}\nТелефон: {phone}\nДата: {date}\nВремя: {time_slot}\n\n"
        f"Мы свяжемся с вами для подтверждения."
    )
    await show_main_menu(update.effective_chat.id, context, user_id, "Запись создана. Выберите действие:")

    admin_text = (
        f"🆕 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
        f"Услуга: {service_display}\nИмя: {name}\n"
        f"Телефон: <a href=\"tel:{phone}\">{phone}</a>\nДата: {date}\nВремя: {time_slot}\n"
        f"<a href=\"tg://user?id={user_id}\">👤 Профиль клиента</a>"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка уведомления: {e}")

    context.user_data.clear()
    return ConversationHandler.END

# ==================== СВОБОДНЫЕ СЛОТЫ ====================
async def slot_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split("_")[1]
    context.user_data["slot_date"] = selected_date
    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM clients WHERE date = ?", (selected_date,))
    booked = [row[0] for row in cursor.fetchall()]
    conn.close()
    await query.edit_message_text(f"📅 {selected_date}\nСвободное время:", reply_markup=get_inline_time_keyboard(booked))
    return CHOOSING_SLOT_TIME

async def slot_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_slot = query.data.split("_")[1]
    date_slot = context.user_data.get("slot_date")
    await query.edit_message_text(
        f"✅ Слот {date_slot} {time_slot} свободен!\n"
        f"Чтобы записаться, нажмите «📝 Записаться» в главном меню."
    )
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id)
    return ConversationHandler.END

# ==================== ОТМЕНА ЗАПИСИ ====================
async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split("_")[-1])
    conn = sqlite3.connect(os.path.join(BASE_DIR, "barbershop.db"))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    await query.edit_message_text("✅ Запись отменена.")
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id, "Запись удалена.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await show_main_menu(update.effective_chat.id, context, user_id, "Диалог отменён.")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ЗАПУСК ====================
def main():
    init_db()
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден. Установите переменную окружения BOT_TOKEN")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для записи
    booking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Записаться$"), handle_main_menu)],
        states={
            SERVICE: [CallbackQueryHandler(service_selection, pattern="^(hairstyle|makeup|womens_haircut|hair_extensions|consultation)$")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CONTACT: [MessageHandler(filters.CONTACT, get_contact)],
            DATE: [CallbackQueryHandler(get_date, pattern="^date_")],
            TIME: [CallbackQueryHandler(get_time, pattern="^time_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_booking_menu, pattern="^cancel_booking_menu$")],
        name="booking",
        allow_reentry=True,
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    # ConversationHandler для свободных слотов
    slots_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Свободные даты$"), handle_main_menu)],
        states={
            CHOOSING_SLOT_DATE: [CallbackQueryHandler(slot_date, pattern="^date_")],
            CHOOSING_SLOT_TIME: [CallbackQueryHandler(slot_time, pattern="^time_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_booking_menu, pattern="^cancel_booking_menu$")],
        name="slots",
        allow_reentry=True,
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    # ConversationHandler для отмены записи
    cancel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^❌ Отменить запись$"), handle_main_menu)],
        states={CHOOSING_CANCEL_BOOKING: [CallbackQueryHandler(confirm_cancel, pattern="^confirm_cancel_")]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_booking_menu, pattern="^cancel_booking_menu$")],
        name="cancel",
        allow_reentry=True,
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    # Обработчики
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(works_navigation, pattern="^works_(next|prev)_"))
    app.add_handler(MessageHandler(filters.Regex("^📋 Список записей$"), get_bookings_list))
    app.add_handler(MessageHandler(filters.Regex("^(💼 Мои работы|💰 Прайс-лист|ℹ️ О нас|📞 Контакты)$"), handle_main_menu))
    app.add_handler(CommandHandler("start", start))

    app.add_handler(booking_conv)
    app.add_handler(slots_conv)
    app.add_handler(cancel_conv)

    print("✅ Бот запущен. Администратор видит кнопку «📋 Список записей».")
    app.run_polling()

if __name__ == "__main__":
    main()
