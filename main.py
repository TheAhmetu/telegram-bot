from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading
import os
from datetime import datetime
import pytz
import json
import asyncio

STEP = 11
DATA_FILE = "data.json"

global_number = 1
sent_messages = []

app = Flask('')

@app.route('/')
def home():
    return "Bot çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def get_today_date_str():
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(tz)
    return now.strftime("%d.%m.%Y")

def format_numbers(start):
    return f"{start:05d} - {start + STEP - 1:05d}"

def save_data():
    global global_number, sent_messages
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "global_number": global_number,
                "sent_messages": sent_messages
            }, f)
    except Exception as e:
        print(f"Data kaydedilirken hata: {e}")

def load_data():
    global global_number, sent_messages
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                global_number = data.get("global_number", 1)
                sent_messages = data.get("sent_messages", [])
        except Exception as e:
            print(f"Data yüklenirken hata: {e}")

async def al_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    user = update.effective_user.full_name or update.effective_user.first_name
    today = get_today_date_str()
    from_num = global_number
    to_num = from_num + STEP - 1
    text = f"{user}\n{today} {format_numbers(from_num)}"

    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    sent = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    sent_messages.append({
        "message_id": sent.message_id,
        "from_num": from_num,
        "to_num": to_num
    })

    global_number = to_num + 1
    save_data()

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    query = update.callback_query
    await query.answer()

    user = query.from_user.full_name or query.from_user.first_name
    today = get_today_date_str()
    from_num = global_number
    to_num = from_num + STEP - 1
    text = f"{user}\n{today} {format_numbers(from_num)}"

    keyboard = [[InlineKeyboardButton("Sonraki", callback_data="next")]]
    sent = await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    sent_messages.append({
        "message_id": sent.message_id,
        "from_num": from_num,
        "to_num": to_num
    })

    global_number = to_num + 1
    save_data()

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number
    if context.args and context.args[0].isdigit():
        num = int(context.args[0])
        global_number = num
        save_data()
        await update.message.reply_text(f"Başlangıç numarası {num:05d} olarak ayarlandı.")
    else:
        await update.message.reply_text("Lütfen geçerli bir sayı girin. Örnek: /edit 10002")

async def sil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_number, sent_messages
    message = update.message

    if not message.reply_to_message:
        await message.reply_text("Lütfen silmek istediğiniz mesajı alıntılayarak /sil yazın.")
        return

    reply_id = message.reply_to_message.message_id

    if not sent_messages:
        await message.reply_text("Silinecek mesaj bulunamadı.")
        return

    last_sent = sent_messages[-1]

    if reply_id != last_sent["message_id"]:
        await message.reply_text("Sadece botun son gönderdiği mesajı silebilirsiniz.")
        return

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=reply_id)
        silinen = sent_messages.pop()
        global_number = silinen["from_num"]
        save_data()
        await message.reply_text("Son mesaj silindi ve numaralar geri alındı.")
    except Exception as e:
        await message.reply_text(f"Mesaj silinemedi: {e}")

def run_bot():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Lütfen TELEGRAM_BOT_TOKEN ortam değişkenini ayarlayın.")
        exit(1)

    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("al", al_command))
    app_bot.add_handler(CommandHandler("edit", edit_command))
    app_bot.add_handler(CommandHandler("sil", sil_command))
    app_bot.add_handler(CallbackQueryHandler(button))

    print("Bot başlatılıyor...")
    app_bot.run_polling()

if __name__ == "__main__":
    print("Veriler yükleniyor...")
    load_data()

    print("Flask sunucusu başlatılıyor...")
    keep_alive()  # Flask thread'de çalışsın

    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Lütfen TELEGRAM_BOT_TOKEN ortam değişkenini ayarlayın.")
        exit(1)

    print("Bot başlatılıyor...")
    from telegram.ext import ApplicationBuilder

    import asyncio

    async def main():
        app_bot = ApplicationBuilder().token(TOKEN).build()
        app_bot.add_handler(CommandHandler("al", al_command))
        app_bot.add_handler(CommandHandler("edit", edit_command))
        app_bot.add_handler(CommandHandler("sil", sil_command))
        app_bot.add_handler(CallbackQueryHandler(button))

        await app_bot.run_polling()

    asyncio.run(main())
