import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)
import json
from datetime import datetime
import pytz

# Log ayarları
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

STEP = 11
DATA_FILE = "data.json"
global_number = 1
sent_messages = []

def get_today_date_str():
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(tz)
    return now.strftime("%d.%m.%Y")

def format_numbers(start):
    return f"{start:05d} - {start + STEP - 1:05d}"

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(
                {
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
                logger.info(f"Data yüklendi: Başlangıç numarası: {global_number}, Mesaj sayısı: {len(sent_messages)}")
        except Exception as e:
            logger.error(f"Data yüklenirken hata: {e}")

async def al_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    user = update.effective_user.full_name or update.effective_user.first_name
    today = get_today_date_str()
    from_num = global_number
    to_num = from_num + STEP - 1
    global_number = to_num + 1
    text = f"{user}\n{today} {format_numbers(from_num)}"
    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    try:
        sent = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard))
        sent_messages.append({
            "message_id": sent.message_id,
            "from_num": from_num,
            "to_num": to_num
        })
        save_data()
    except Exception as e:
        global_number = from_num  # revert
        await update.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"al_command hatası: {e}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    query = update.callback_query
    await query.answer()
    user = query.from_user.full_name or query.from_user.first_name
    today = get_today_date_str()
    from_num = global_number
    to_num = from_num + STEP - 1
    global_number = to_num + 1
    text = f"{user}\n{today} {format_numbers(from_num)}"
    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    try:
        sent = await query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard))
        sent_messages.append({
            "message_id": sent.message_id,
            "from_num": from_num,
            "to_num": to_num
        })
        save_data()
    except Exception as e:
        global_number = from_num  # revert
        await query.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"button callback hatası: {e}")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number
    try:
        if context.args and context.args[0].isdigit():
            num = int(context.args[0])
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
            sent_messages = temp_messages
            global_number = temp_global
            save_data()
            await message.reply_text("Son mesaj silindi ve numaralar geri alındı.")
            logger.info("Son mesaj silindi")
        except Exception as e:
            await message.reply_text(f"Mesaj silinemedi: {e}")
            logger.error(f"Mesaj silme hatası: {e}")
    except Exception as e:
        logger.error(f"sil_command hatası: {e}")

def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://telegram-bot-3rda.onrender.com
    if not TOKEN or not WEBHOOK_URL:
        print("TOKEN ve/veya WEBHOOK_URL ortam değişkenleri ayarlanmamış!")
        exit(1)
    load_data()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("al", al_command))
    app.add_handler(CommandHandler("edit", edit_command))
    app.add_handler(CommandHandler("sil", sil_command))
    app.add_handler(CallbackQueryHandler(button))
    # Webhook'u başlat
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 10000)),
        webhook_url=f"{WEBHOOK_URL}/webhook",
        webhook_path="/webhook"
    )

if __name__ == "__main__":
    main()
