import os
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Set these in your hosting provider's Environment Variables.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8824603452"))
DB_PATH = os.getenv("DB_PATH", "onekey_store.db")
QR_IMAGE = os.getenv("QR_IMAGE", "aba_qr.png")

# Store products and prices (USD).
PLANS = {
    "1h": ("1 ម៉ោង", 0.25),
    "3h": ("3 ម៉ោង", 0.65),
    "1d": ("1 ថ្ងៃ", 1.00),
}
CATEGORIES = {"ios": "🍎 iOS MODS", "android": "🤖 Android MODS"}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                plan TEXT NOT NULL,
                license_key TEXT NOT NULL UNIQUE,
                sold INTEGER NOT NULL DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                category TEXT NOT NULL,
                plan TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'awaiting_receipt',
                receipt_file_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)


def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ទិញ iOS MODS", callback_data="cat:ios")],
        [InlineKeyboardButton("🛒 ទិញ Android MODS", callback_data="cat:android")],
        [InlineKeyboardButton("📦 ស្តុកទំនិញ", callback_data="stock")],
        [InlineKeyboardButton("📞 ទាក់ទង Admin", url="https://t.me/OneKeyStore_bot")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"សួស្តី {user.first_name or 'អតិថិជន'}! 👋\n\n"
        "សូមស្វាគមន៍មកកាន់ OneKey Store 🇰🇭\n"
        "ជ្រើសរើសប្រភេទ MODS ខាងក្រោម៖"
    )
    await update.message.reply_text(msg, reply_markup=main_menu())


async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    with connect() as con:
        rows = con.execute("""
            SELECT category, plan, COUNT(*) AS qty
            FROM stock WHERE sold=0 GROUP BY category, plan
        """).fetchall()
    lines = ["📦 ស្តុក Key ដែលនៅសល់៖"]
    for cat, cat_name in CATEGORIES.items():
        lines.append(f"\n{cat_name}")
        for plan, (label, price) in PLANS.items():
            qty = next((r["qty"] for r in rows
                        if r["category"] == cat and r["plan"] == plan), 0)
            lines.append(f"• {label}: {qty} Key")
    await q.message.reply_text("\n".join(lines), reply_markup=main_menu())


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data.startswith("cat:"):
        category = data.split(":", 1)[1]
        if category not in CATEGORIES:
            return
        buttons = []
        for plan, (label, price) in PLANS.items():
            buttons.append([InlineKeyboardButton(
                f"{label} — ${price:.2f}",
                callback_data=f"buy:{category}:{plan}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ ត្រឡប់", callback_data="home")])
        await q.message.reply_text(
            f"{CATEGORIES[category]}\nសូមជ្រើសរើសរយៈពេល៖",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "home":
        await q.message.reply_text("🏠 ម៉ឺនុយដើម", reply_markup=main_menu())

    elif data == "stock":
        await show_stock(update, context)

    elif data.startswith("buy:"):
        _, category, plan = data.split(":")
        if category not in CATEGORIES or plan not in PLANS:
            return
        with connect() as con:
            stock_count = con.execute(
                "SELECT COUNT(*) FROM stock WHERE category=? AND plan=? AND sold=0",
                (category, plan)
            ).fetchone()[0]
        if stock_count < 1:
            await q.message.reply_text("សូមអភ័យទោស! Key ប្រភេទនេះអស់ស្តុកហើយ។")
            return
        label, price = PLANS[plan]
        with connect() as con:
            cur = con.execute("""
                INSERT INTO orders
                (user_id, username, category, plan, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'awaiting_receipt', ?)
            """, (
                q.from_user.id, q.from_user.username or "",
                category, plan, price, datetime.now(timezone.utc).isoformat()
            ))
            order_id = cur.lastrowid

        context.user_data["pending_order"] = order_id
        caption = (
            f"🧾 ការបញ្ជាទិញ #{order_id}\n"
            f"ប្រភេទ៖ {CATEGORIES[category]}\n"
            f"រយៈពេល៖ {label}\n"
            f"តម្លៃ៖ ${price:.2f}\n\n"
            "សូមស្កេន ABA KHQR ដើម្បីបង់ប្រាក់។\n"
            "បន្ទាប់មកផ្ញើរូប Screenshot បង្កាន់ដៃមកទីនេះ។"
        )
        if os.path.exists(QR_IMAGE):
            with open(QR_IMAGE, "rb") as photo:
                await q.message.reply_photo(photo=photo, caption=caption)
        else:
            await q.message.reply_text(
                caption + "\n\n(Admin ត្រូវដាក់រូប QR ជា aba_qr.png ក្នុង project)"
            )


async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order_id = context.user_data.get("pending_order")
    if not order_id:
        await update.message.reply_text("សូមចុច /start ហើយជ្រើសរើសទំនិញជាមុន។")
        return

    photo = update.message.photo
    if not photo:
        await update.message.reply_text("សូមផ្ញើរូប Screenshot បង្កាន់ដៃជារូបភាព។")
        return
    file_id = photo[-1].file_id
    with connect() as con:
        row = con.execute("SELECT * FROM orders WHERE id=? AND user_id=?",
                          (order_id, user.id)).fetchone()
        if not row or row["status"] != "awaiting_receipt":
            await update.message.reply_text("ការបញ្ជាទិញនេះមិនអាចទទួលបង្កាន់ដៃបានទេ។")
            return
        con.execute(
            "UPDATE orders SET receipt_file_id=?, status='pending_admin' WHERE id=?",
            (file_id, order_id)
        )

    label, _ = PLANS[row["plan"]]
    admin_caption = (
        f"🔔 បង្កាន់ដៃថ្មី — Order #{order_id}\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username or 'មិនមាន'}\n"
        f"ទំនិញ: {CATEGORIES[row['category']]}\n"
        f"រយៈពេល: {label}\n"
        f"តម្លៃ: ${row['amount']:.2f}\n\n"
        "ពិនិត្យការទូទាត់ក្នុង ABA មុនចុចអនុម័ត។"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ បញ្ជាក់ និងផ្ញើ Key", callback_data=f"approve:{order_id}"),
        InlineKeyboardButton("❌ បដិសេធ", callback_data=f"reject:{order_id}")
    ]])
    await context.bot.send_photo(
        chat_id=OWNER_ID, photo=file_id, caption=admin_caption,
        reply_markup=keyboard
    )
    context.user_data.pop("pending_order", None)
    await update.message.reply_text(
        "ទទួលបានបង្កាន់ដៃហើយ! ✅\n"
        "សូមរង់ចាំ Admin ពិនិត្យ និងបញ្ជាក់ការទូទាត់។"
    )


async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("⛔ មុខងារនេះសម្រាប់ Admin ប៉ុណ្ណោះ។")
        return

    action, order_text = q.data.split(":")
    order_id = int(order_text)

    with connect() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order or order["status"] != "pending_admin":
            await q.message.reply_text("Order មិនមាន ឬត្រូវបានដំណើរការរួចហើយ។")
            return

        if action == "reject":
            con.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
            await context.bot.send_message(
                order["user_id"],
                f"ការទូទាត់ Order #{order_id} ត្រូវបានបដិសេធ។ សូមទាក់ទង Admin។"
            )
            await q.edit_message_caption((q.message.caption or "") + "\n\n❌ Rejected")
            return

        key_row = con.execute("""
            SELECT id, license_key FROM stock
            WHERE category=? AND plan=? AND sold=0
            ORDER BY id LIMIT 1
        """, (order["category"], order["plan"])).fetchone()

        if not key_row:
            await q.message.reply_text(
                "អស់ស្តុក Key! សូមបន្ថែម Key មុនអនុម័ត Order នេះ។"
            )
            return

        con.execute("UPDATE stock SET sold=1 WHERE id=?", (key_row["id"],))
        con.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))

    try:
        await context.bot.send_message(
            order["user_id"],
            f"ការទូទាត់ Order #{order_id} ត្រូវបានបញ្ជាក់ហើយ! ✅\n\n"
            f"🔑 MODS Key របស់អ្នក៖\n`{key_row['license_key']}`\n\n"
            "សូមរក្សា Key នេះឱ្យមានសុវត្ថិភាព។",
            parse_mode="Markdown"
        )
        await q.edit_message_caption((q.message.caption or "") + "\n\n✅ Approved — Key sent")
    except Exception:
        await q.message.reply_text(
            "បានអនុម័ត និងកាត់ស្តុកហើយ ប៉ុន្តែ Bot មិនអាចផ្ញើសារទៅអតិថិជនបាន។"
        )


async def addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    # Usage: /addkey ios 1h LICENSE-KEY
    if len(context.args) < 3:
        await update.message.reply_text(
            "របៀបប្រើ៖\n/addkey ios 1h YOUR-KEY\n"
            "ឬ /addkey android 3h YOUR-KEY\n\n"
            "ប្រភេទ: ios / android\nរយៈពេល: 1h / 3h / 1d"
        )
        return
    category, plan = context.args[0].lower(), context.args[1].lower()
    license_key = " ".join(context.args[2:]).strip()
    if category not in CATEGORIES or plan not in PLANS:
        await update.message.reply_text("ប្រភេទ ឬរយៈពេលមិនត្រឹមត្រូវទេ។")
        return
    try:
        with connect() as con:
            con.execute(
                "INSERT INTO stock(category, plan, license_key) VALUES (?, ?, ?)",
                (category, plan, license_key)
            )
        await update.message.reply_text("បានបន្ថែម Key ទៅក្នុងស្តុកហើយ! ✅")
    except sqlite3.IntegrityError:
        await update.message.reply_text("Key នេះមានក្នុងស្តុករួចហើយ។")


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ មុខងារនេះសម្រាប់ Admin ប៉ុណ្ណោះ។")
        return
    await update.message.reply_text(
        "🛠️ Admin Commands\n\n"
        "/addkey ios 1h YOUR-KEY\n"
        "/addkey ios 3h YOUR-KEY\n"
        "/addkey ios 1d YOUR-KEY\n"
        "/addkey android 1h YOUR-KEY\n"
        "/addkey android 3h YOUR-KEY\n"
        "/addkey android 1d YOUR-KEY\n\n"
        "ប្រើ /addkey ដើម្បីបន្ថែម Key ទៅស្តុក។"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled bot error", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN environment variable.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CommandHandler("addkey", addkey))
    app.add_handler(CallbackQueryHandler(admin_actions, pattern=r"^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, receipt_handler))
    app.add_error_handler(error_handler)
    log.info("OneKey Store Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
