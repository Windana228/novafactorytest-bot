import asyncio
import logging
import os
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
SHEET_KEY = "1tqz3hfCDhLlMRQNOCAkfQQAgL1223zi4IjHZexkKDsg"
SHEET_NAME = "Responses"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SHEET_KEY).worksheet(SHEET_NAME)

# Constants
PRICES = {
    "Кількість топів (Рубчик)": 60,
    "Кількість шортів(Рубчик)": 50,
    "Кількість Ліфи(Кулір)": 95,
    "Кількість трусиків (Стріги та Сліпи Кулір)": 30,
    "Кількість сорочок (Смужка)": 250,
    "Кількість штанів (Смужка)": 100,
    "Кількість шортів (смужка)": 75,
    "Кількість футболок (Soft)": 45,
    "Кількість шортів (Soft)": 45
}

SEWERS = [
    "Світлана Дорофєєва",
    "Світлана Казакевич",
    "Дана Руда",
    "Надія Козирська"
]

# States
(CHOOSING_NAME, CHOOSING_DATE_TYPE, ENTERING_DATE, ENTERING_ITEM_QUANTITIES, CONFIRMATION, MODIFY_FIELD) = range(6)

REGISTERED_USERS = []
BOT_TOKEN = "7686030914:AAGIE5IoO-roTln4nd_MUSKndPa4qxZuilc"

def generate_motivation(salary):
    for amount, msg in [
        (500, "😴 Легка розминка сьогодні! Завтра — серйозна швейна атака!"),
        (700, "🐢 Плавний темп — але ми ж не черепаха! Завтра — швейний спринт!"),
        (900, "🔧 Добре! Але ти ж не тільки голку тримаєш, а й мотивацію!"),
        (1100, "💼 Все серйозно! Уже швачка-профі, ідемо до ТОПу!"),
        (1300, "🚀 Ого, ти вже на швейній орбіті! Ще трохи — і полетиш у бонуси!"),
        (1500, "🌟 Твої руки — це швейна зброя! Браво, ще 1 день — і рекорд!"),
        (1700, "🧵 Залишилось тільки дим з-під машинки! Супер темп!"),
        (1900, "🔥 Гарячий день! Ти як праска — безупинно продуктивна!"),
        (2100, "🎯 Ти пробила 2000 — це як виграти швейну Олімпіаду!"),
        (2300, "🏆 Золота голка! Ще пару днів — і буде Rolls Royce!"),
        (2500, "💸 Може вже час відкривати власний бренд? 🤩"),
        (2700, "🧨 Ти не шиєш — ти летиш! Turbo-режим активовано!"),
        (2900, "🐎 Машинка плавиться, начальство в шоці, зарплата росте!"),
        (3000, "👑 Це вже швейний трон! Королева голки сьогодні!")
    ]:
        if salary < amount:
            return msg
    return "🤑 Все! Завтра не працюй — вже можна в Карпати відпочивати!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in SEWERS]
    await update.message.reply_text(
        "Привіт! Оберіть своє ім’я:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return CHOOSING_NAME

async def choose_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name not in SEWERS:
        await update.message.reply_text("Будь ласка, виберіть ім’я з клавіатури.")
        return CHOOSING_NAME
    context.user_data['name'] = name
    await update.message.reply_text(
        "За який день вводимо дані?",
        reply_markup=ReplyKeyboardMarkup([["Сьогодні"], ["Інша дата"]], resize_keyboard=True, one_time_keyboard=True)
    )
    return CHOOSING_DATE_TYPE

async def choose_date_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Сьогодні":
        context.user_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        context.user_data['quantities'] = {}
        context.user_data['current_index'] = 0
        item = list(PRICES.keys())[0]
        await update.message.reply_text(item, reply_markup=ReplyKeyboardRemove())
        return ENTERING_ITEM_QUANTITIES
    elif choice == "Інша дата":
        await update.message.reply_text("Введіть дату у форматі ДД.ММ.РРРР", reply_markup=ReplyKeyboardRemove())
        return ENTERING_DATE
    else:
        await update.message.reply_text("Будь ласка, виберіть одну з кнопок.")
        return CHOOSING_DATE_TYPE

async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y")
        context.user_data['date'] = date.strftime("%Y-%m-%d 00:00")
        context.user_data['quantities'] = {}
        context.user_data['current_index'] = 0
        item = list(PRICES.keys())[0]
        await update.message.reply_text(item, reply_markup=ReplyKeyboardRemove())
        return ENTERING_ITEM_QUANTITIES
    except ValueError:
        await update.message.reply_text("Невірний формат. Спробуйте ще раз у форматі ДД.ММ.РРРР")
        return ENTERING_DATE

async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().lower() == "/stop":
        await update.message.reply_text("⛔️ Введення скасовано.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        quantity = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть число.")
        return ENTERING_ITEM_QUANTITIES

    if 'modify_target' in context.user_data:
        field = context.user_data.pop('modify_target')
        context.user_data['quantities'][field] = quantity
        return await confirm(update, context)

    item = list(PRICES.keys())[context.user_data['current_index']]
    context.user_data['quantities'][item] = quantity
    context.user_data['current_index'] += 1

    if context.user_data['current_index'] < len(PRICES):
        next_item = list(PRICES.keys())[context.user_data['current_index']]
        await update.message.reply_text(next_item)
        return ENTERING_ITEM_QUANTITIES
    else:
        return await confirm(update, context)

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = "Ось що ви ввели:\n"
    for k, v in context.user_data['quantities'].items():
        summary += f"{k}: {v}\n"
    keyboard = [["✅ Так"], ["✏️ Хочу змінити"]]
    await update.message.reply_text(summary + "\nВсе правильно?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return CONFIRMATION

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text.strip()
    if response == "✅ Так":
        return await finalize_entry(update, context)
    elif response == "✏️ Хочу змінити":
        items = [[item] for item in PRICES.keys()]
        await update.message.reply_text("Що саме змінити?", reply_markup=ReplyKeyboardMarkup(items, resize_keyboard=True, one_time_keyboard=True))
        return MODIFY_FIELD
    else:
        await update.message.reply_text("Будь ласка, виберіть одну з кнопок.")
        return CONFIRMATION

async def modify_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text.strip()
    if field not in PRICES:
        await update.message.reply_text("Будь ласка, виберіть правильне поле зі списку.")
        return MODIFY_FIELD
    context.user_data['modify_target'] = field
    await update.message.reply_text(f"Введіть нове значення для: {field}", reply_markup=ReplyKeyboardRemove())
    return ENTERING_ITEM_QUANTITIES

async def finalize_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data['name']
    date = context.user_data['date']
    quantities = context.user_data['quantities']
    total = sum(PRICES[k] * quantities.get(k, 0) for k in PRICES)
    row = [date, name] + [quantities.get(k, 0) for k in PRICES] + [total]
    sheet.append_row(row)
    motivation = generate_motivation(total)
    await update.message.reply_text(f"Дякуємо, {name}! Загальна сума: {total} грн.\n{motivation}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def send_reminders():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        bot = app.bot
        for uid in REGISTERED_USERS:
            bot.send_message(chat_id=uid, text="🔔 Нагадування! Ви ще не заповнили дані за сьогодні. Це був робочий день?")
    except Exception as e:
        logger.error(f"Reminder error: {e}")

async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_name)],
            CHOOSING_DATE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date_type)],
            ENTERING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            ENTERING_ITEM_QUANTITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data)],
            MODIFY_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_field)],
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: send_reminders(), 'cron', hour=18, timezone='Europe/Kyiv')
    scheduler.start()
    logger.info("Bot started.")
    await application.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
