import os
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = "7947997632:AAGhg9kbOW4lLRt-tOjt9D-wQKg03CcF_TE"
ADMIN_ID = 6393036027
DB = "users.db"

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            status TEXT DEFAULT 'unknown',
            reason TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS votes (
            voter_id INTEGER,
            target TEXT,
            vote INTEGER,
            PRIMARY KEY (voter_id, target)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            username TEXT,
            reason TEXT
        )''')

def get_user(username):
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("SELECT * FROM users WHERE username=?", (username,))
        return cur.fetchone()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет, добро пожаловать в официальную базу!\n\n"
        "📌 Чтобы проверить пользователя: /check @username\n"
        "⚠️ Чтобы добавить мошенника: /add @username причина\n"
        "📨 Чтобы пожаловаться: /report @username причина\n"
        "🔝 Чтобы увидеть топ гарантов: /top\n"
        "💼 Панель админа: /admin"
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /check @username")
        return
    username = context.args[0].lstrip('@')
    with sqlite3.connect(DB) as conn:
        conn.execute("UPDATE users SET views = views + 1 WHERE username=?", (username,))
        cur = conn.execute("SELECT * FROM users WHERE username=?", (username,))
        row = cur.fetchone()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍", callback_data=f"like:{username}"),
         InlineKeyboardButton("👎", callback_data=f"dislike:{username}")],
        [InlineKeyboardButton("📨 Пожаловаться", callback_data=f"report:{username}")],
        [InlineKeyboardButton("🔍 Проверить другого", switch_inline_query_current_chat="/check @")]
    ])
    if row:
        status = row[2]
        message = f"🔎 @{username}\nПросмотров: {row[4]}\n👍 {row[5]} 👎 {row[6]}\n\n"
        if status == "scammer":
            message = "🚫 МОШЕННИК ❗️\n" + message + "Идите только к проверенным гарантам!\n📤 В ЧС!"
            image_path = "images/scammer.jpg"
        elif status == "guarant":
            message = (
                f"🛡 ТОП ГАРАНТ: @{username}\n"
                f"Топ сделка: 10.000$\nКомиссия: 2% / 300 руб\n\n"
                f"Данный пользователь является проверенным ✅\n"
                f"Рекомендовано для проведения сделок ✔\n"
                f"Просмотров: {row[4]}\n👍 {row[5]} 👎 {row[6]}"
            )
            image_path = "images/guarant.jpg"
        else:
            message = "❔ Пользователь не замечен в базе мошенников.\n" + \
                      "Не доверяйте непроверенным. Проверяйте через /check\n\n" + message
            image_path = "images/unknown.jpg"
        await update.message.reply_photo(photo=InputFile(image_path), caption=message, reply_markup=keyboard)
    else:
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
        await update.message.reply_text(f"Пользователь @{username} добавлен как неизвестный. Повторите /check")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /add @user причина")
        return
    username = context.args[0].lstrip('@')
    reason = " ".join(context.args[1:])
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
        conn.execute("UPDATE users SET status='scammer', reason=? WHERE username=?", (reason, username))
    await update.message.reply_text(f"🚫 Пользователь @{username} добавлен как мошенник.")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /report @user причина")
        return
    username = context.args[0].lstrip('@')
    reason = " ".join(context.args[1:])
    user_id = update.effective_user.id
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO reports (reporter_id, username, reason) VALUES (?, ?, ?)", (user_id, username, reason))
    await update.message.reply_text("📨 Жалоба отправлена администратору.")
    await context.bot.send_message(ADMIN_ID, f"⚠️ Жалоба от @{update.effective_user.username or user_id} на @{username}:\n{reason}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, username = query.data.split(':')
    user_id = query.from_user.id
    with sqlite3.connect(DB) as conn:
        if action == "like":
            conn.execute("INSERT OR IGNORE INTO votes (voter_id, target, vote) VALUES (?, ?, 1)", (user_id, username))
            conn.execute("UPDATE users SET likes = likes + 1 WHERE username=?", (username,))
            await query.edit_message_caption(caption="👍 Лайк засчитан.")
        elif action == "dislike":
            conn.execute("INSERT OR IGNORE INTO votes (voter_id, target, vote) VALUES (?, ?, -1)", (user_id, username))
            conn.execute("UPDATE users SET dislikes = dislikes + 1 WHERE username=?", (username,))
            await query.edit_message_caption(caption="👎 Дизлайк засчитан.")
        elif action == "report":
            await query.message.reply_text(f"Для жалобы используй:\n/report @{username} причина")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для администратора.")
        return
    with sqlite3.connect(DB) as conn:
        scammers = conn.execute("SELECT username, reason FROM users WHERE status='scammer'").fetchall()
        reports = conn.execute("SELECT username, reason FROM reports").fetchall()
    message = "🔐 Админ-панель:\n"
    message += f"Мошенники:\n" + "\n".join([f"- @{u} ({r})" for u, r in scammers]) + "\n\n"
    message += f"Жалобы:\n" + "\n".join([f"- @{u} ({r})" for u, r in reports]) + "\n"
    await update.message.reply_text(message or "Нет данных.")

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
