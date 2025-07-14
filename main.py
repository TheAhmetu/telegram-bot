import os
import json
import threading
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from datetime import datetime
import pytz
import asyncio

STEP = 11
DATA_FILE = "data.json"
global_lock = threading.Lock()
global_number = 1
sent_messages = []

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_today_date_str():
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(tz)
    return now.strftime("%d.%m.%Y")

def format_numbers(start):
    return f"{start:05d} - {start + STEP - 1:05d}"

def save_data():
    try:
        with global_lock:
            with open(DATA_FILE, "w") as f:
                json.dump({
                    "global_number": global_number,
                    "sent_messages": sent_messages
                }, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Data kaydedilirken hata: {e}")

def load_data():
    global global_number, sent_messages
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                global_number = data.get("global_number", 1)
                sent_messages = data.get("sent_messages", [])
        except Exception as e:
            logger.error(f"Data yüklenirken hata: {e}")

async def al_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    user = update.effective_user.full_name or update.effective_user.first_name
    today = get_today_date_str()
    with global_lock:
        from_num = global_number
        to_num = from_num + STEP - 1
        global_number = to_num + 1
    text = f"{user}\n{today} {format_numbers(from_num)}"
    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    try:
        sent = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard))
        with global_lock:
            sent_messages.append({
                "message_id": sent.message_id,
                "from_num": from_num,
                "to_num": to_num
            })
            save_data()
    except Exception as e:
        with global_lock:
            global_number = from_num
        await update.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"al_command hatası: {e}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    query = update.callback_query
    await query.answer()
    user = query.from_user.full_name or query.from_user.first_name
    today = get_today_date_str()
    with global_lock:
        from_num = global_number
        to_num = from_num + STEP - 1
        global_number = to_num + 1
    text = f"{user}\n{today} {format_numbers(from_num)}"
    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    try:
        sent = await query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard))
        with global_lock:
            sent_messages.append({
                "message_id": sent.message_id,
                "from_num": from_num,
                "to_num": to_num
            })
            save_data()
    except Exception as e:
        with global_lock:
            global_number = from_num
        await query.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"button callback hatası: {e}")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number
    try:
        if context.args and context.args[0].isdigit():
            num = int(context.args[0])
            with global_lock:
                global_number = num
                save_data()
            await update.message.reply_text(
                f"Başlangıç numarası {num:05d} olarak ayarlandı.")
            logger.info(f"Edit komutu: Yeni numara {num}")
        else:
            await update.message.reply_text(
                "Lütfen geçerli bir sayı girin. Örnek: /edit 10002")
    except Exception as e:
        logger.error(f"edit_command hatası: {e}")

async def sil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    try:
        message = update.message
        if not message.reply_to_message:
            await message.reply_text(
                "Lütfen silmek istediğiniz mesajı alıntılayarak /sil yazın.")
            return
        reply_id = message.reply_to_message.message_id
        with global_lock:
            if not sent_messages:
                await message.reply_text("Silinecek mesaj bulunamadı.")
                return
            last_sent = sent_messages[-1]
            if reply_id != last_sent["message_id"]:
                await message.reply_text(
                    "Sadece botun son gönderdiği mesajı silebilirsiniz.")
                return
            temp_messages = sent_messages[:-1]
            temp_global = last_sent["from_num"]
        try:
            await context.bot.delete_message(
                chat_id=message.chat_id,
                message_id=reply_id
            )
            with global_lock:
                sent_messages[:] = temp_messages
                global_number = temp_global
                save_data()
            await message.reply_text("Son mesaj silindi ve numaralar geri alındı.")
            logger.info("Son mesaj silindi")
        except Exception as e:
            await message.reply_text(f"Mesaj silinemedi: {e}")
            logger.error(f"Mesaj silme hatası: {e}")
    except Exception as e:
        logger.error(f"sil_command hatası: {e}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot çalışıyor!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    asyncio.run(app.application.process_update(update))
    return "OK"

async def async_startup(application, webhook_url):
    await application.initialize()
    await application.bot.set_webhook(webhook_url + "/webhook")

def start_bot_and_webhook():
    load_data()
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    if not TOKEN or not WEBHOOK_URL:
        logger.critical("TELEGRAM_BOT_TOKEN veya WEBHOOK_URL ortam değişkeni eksik!")
        exit(1)
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("al", al_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("sil", sil_command))
    application.add_handler(CallbackQueryHandler(button))
    app.application = application
    app.bot = application.bot
    logger.info("Webhook ayarlanıyor...")
    asyncio.run(async_startup(application, WEBHOOK_URL))
    logger.info("Webhook ayarlandı: %s/webhook", WEBHOOK_URL)

if __name__ == "__main__":
    start_bot_and_webhook()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
