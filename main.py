import telebot
from telebot import types
import sqlite3
import requests
import os
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"
CRYPTO_TOKEN = "ТВОЙ_ТОКЕН_CRYPTOBOT"
ADMIN_ID = 123456789 # Твой Telegram ID
# ================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('database.sqlite')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, username TEXT, amount INTEGER, ref_user TEXT, ref_count INTEGER, ref_donate INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (Id INTEGER PRIMARY KEY, karta TEXT, qiwi TEXT, bitcoin TEXT, crypto_token TEXT)''')
    c.execute("INSERT OR IGNORE INTO config (Id, karta, qiwi, bitcoin, crypto_token) VALUES (1, '2202 2000 0000 0000', 'QIWI', 'BTC', '')")
    conn.commit()
    conn.close()

init_db()

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌿 Выбрать город", callback_data="choose_city"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🆘 Поддержка", url="https://t.me/твой_менеджер")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = str(message.chat.id)
    username = message.from_user.username or "NoUsername"
    
    conn = sqlite3.connect('database.sqlite')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (id, username, amount, ref_user, ref_count, ref_donate) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, username, 0, '', 0, 0))
        conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, 
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "Здесь вы можете выбрать город, товар и оплатить его.\n"
        "Все операции анонимны.", 
        parse_mode="HTML", reply_markup=main_menu())

# --- ГОРОД ---
@bot.callback_query_handler(func=lambda call: call.data == "choose_city")
def choose_city(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Москва", callback_data="city_msk"),
        types.InlineKeyboardButton("СПБ", callback_data="city_spb"),
        types.InlineKeyboardButton("Екатеринбург", callback_data="city_ekb")
    )
    bot.edit_message_text("🏙 <b>Выберите город:</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("city_"))
def city_selected(call):
    city = call.data.replace("city_", "")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("СК (син.крис) {0.3г/900 RUB}", callback_data="item_sk_03"),
        types.InlineKeyboardButton("Гашиш EURO {1г/1100 RUB}", callback_data="item_hash_1"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="choose_city")
    )
    bot.edit_message_text(f"📦 <b>Товары в городе {city.upper()}:</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# --- ВЫБОР ТОВАРА И ОПЛАТА ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("item_"))
def item_selected(call):
    item = call.data
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💎 Оплатить криптой (USDT)", callback_data=f"pay_crypto_{item}"),
        types.InlineKeyboardButton("💳 Оплатить картой", callback_data=f"pay_card_{item}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="choose_city")
    )
    bot.edit_message_text("💳 <b>Выберите способ оплаты:</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# --- ОПЛАТА КРИПТОЙ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_crypto_"))
def pay_crypto(call):
    item = call.data.replace("pay_crypto_", "")
    try:
        headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN, "Content-Type": "application/json"}
        payload = {"asset": "USDT", "amount": "10", "description": f"Оплата товара: {item}", "payload": f"{item}_{call.from_user.id}"}
        r = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers)
        data = r.json()
        if data.get("ok"):
            pay_url = data["result"]["pay_url"]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💸 Перейти к оплате", url=pay_url))
            bot.edit_message_text("✅ <b>Счет создан!</b>\nОплатите и нажмите 'Проверить оплату'.", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Ошибка создания счета")
    except Exception as e:
        bot.answer_callback_query(call.id, "Ошибка соединения")

# --- ОПЛАТА КАРТОЙ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_card_"))
def pay_card(call):
    item = call.data.replace("pay_card_", "")
    bot.edit_message_text("💳 <b>Оплата картой</b>\n\nРеквизиты: 2202 2000 0000 0000\n\nПосле перевода напишите менеджеру.", call.message.chat.id, call.message.message_id, parse_mode="HTML")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
@app.route('/')
def index():
    return "Bot is alive!"

@app.route('/crypto_webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if data.get("update_type") == "invoice_paid":
            payload = data["payload"]["payload"]
            user_id = int(payload.split("_")[-1])
            bot.send_message(user_id, "✅ <b>Оплата подтверждена!</b> Товар будет выдан.", parse_mode="HTML")
        return "OK", 200
    except Exception as e:
        return str(e), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
