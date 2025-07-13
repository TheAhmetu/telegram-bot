from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, request
import threading
import os
import logging
from datetime import datetime
import pytz
import json

# Log ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

STEP = 11
DATA_FILE = "data.json"

# Global durum değişkenleri ve thread güvenliği için kilit
global_lock = threading.Lock()
global_number = 1
sent_messages = []  # [{'message_id': int, 'from_num': int, 'to_num': int}]

# Flask web sunucusu
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot çalışıyor!"

@app.route('/health')
def health_check():
    return "OK", 200

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
            global_number = from_num  # Revert if failed
        await update.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"al_command hatası: {e}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            global_number = from_num  # Revert if failed
        await query.message.reply_text(f"Hata oluştu: {e}")
        logger.error(f"button callback hatası: {e}")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            # Geçici olarak durumu geri al
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

def run_bot():
    try:
        TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN ortam değişkeni ayarlanmamış!")
            return

        logger.info("Bot başlatılıyor...")
        app_bot = ApplicationBuilder().token(TOKEN).build()
        app_bot.add_handler(CommandHandler("al", al_command))
        app_bot.add_handler(CommandHandler("edit", edit_command))
        app_bot.add_handler(CommandHandler("sil", sil_command))
        app_bot.add_handler(CallbackQueryHandler(button))
        
        app_bot.run_polling()
        logger.info("Bot çalışmaya başladı")
    except Exception as e:
        logger.critical(f"Bot başlatılırken kritik hata: {e}")

def run_flask():
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Flask sunucusu {port} portunda başlatılıyor...")
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.critical(f"Flask başlatılırken kritik hata: {e}")

if __name__ == "__main__":
    load_data()
    
    # Flask'ı ayrı thread'de başlat
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Botu ana thread'de başlat
    run_bot()
