import os, logging, sqlite3, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5191323229"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()  # e.g. @YourChannel or -1001234567890
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
REFS_REQUIRED = int(os.getenv("REFS_REQUIRED", "5"))
KEY_API_URL = os.getenv("KEY_API_URL", "").strip()
KEY_API_TOKEN = os.getenv("KEY_API_TOKEN", "").strip()
DB = os.getenv("DB_PATH", "referral.db")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("referral-bot")

def db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, coins INTEGER DEFAULT 0,
        referrer INTEGER, joined INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS keys(
        id INTEGER PRIMARY KEY AUTOINCREMENT, key_text TEXT UNIQUE, used_by INTEGER,
        used_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS claims(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, key_text TEXT,
        claimed_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS credited_referrals(
        referee INTEGER PRIMARY KEY, referrer INTEGER)""")
    c.commit()
    return c

def user_row(uid):
    c=db(); row=c.execute("SELECT user_id,username,coins,referrer,joined FROM users WHERE user_id=?",(uid,)).fetchone(); c.close(); return row

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Refer", callback_data="refer"), InlineKeyboardButton("🔑 Get Key", callback_data="getkey")],
        [InlineKeyboardButton("✅ Verify Channel", callback_data="verify"), InlineKeyboardButton("👤 Profile", callback_data="profile")]
    ])

async def is_member(bot, uid):
    if not CHANNEL_ID: return False
    try:
        m=await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ("member","administrator","creator")
    except TelegramError:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user
    c=db()
    old=c.execute("SELECT user_id FROM users WHERE user_id=?",(u.id,)).fetchone()
    ref=None
    if context.args and context.args[0].startswith("ref_"):
        try: ref=int(context.args[0][4:])
        except ValueError: ref=None
    if not old:
        if ref==u.id or (ref and not c.execute("SELECT 1 FROM users WHERE user_id=?",(ref,)).fetchone()):
            ref=None
        c.execute("INSERT INTO users(user_id,username,referrer) VALUES(?,?,?)",(u.id,u.username or "",ref))
    else:
        c.execute("UPDATE users SET username=? WHERE user_id=?",(u.username or "",u.id))
    c.commit(); c.close()
    msg=("👋 Welcome to Referral Key Bot!\n\n"
         "💰 Earn 1 coin for every genuine referral.\n"
         f"🔑 Get 1 key for {REFS_REQUIRED} verified referrals.\n\n"
         "👇 Select an option:")
    await update.message.reply_text(msg, reply_markup=menu())

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    uid=q.from_user.id
    row=user_row(uid)
    if not row:
        await q.message.reply_text("Please send /start first."); return
    _, username, coins, referrer, joined=row
    if q.data=="refer":
        me=await context.bot.get_me()
        link=f"https://t.me/{me.username}?start=ref_{uid}"
        await q.message.reply_text(
            "🔗 Your Referral Link\n\n"
            f"👤 Username: @{username or 'not_set'}\n"
            f"💰 Balance: {coins} coins\n"
            f"👥 Total Refers: {coins}\n\n"
            f"{link}\n\n"
            "💡 Share this link. You get 1 coin per referral!\n"
            "⚠️ Referral counts only after channel verification.",
            reply_markup=menu(), disable_web_page_preview=True)
    elif q.data=="verify":
        if not await is_member(context.bot, uid):
            join=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK or "https://t.me/")],
                                       [InlineKeyboardButton("🔄 Verify Again", callback_data="verify")]])
            await q.message.reply_text("❌ Channel membership not detected. Join first, then verify.",reply_markup=join)
            return
        c=db()
        c.execute("UPDATE users SET joined=1 WHERE user_id=?",(uid,))
        # Credit referrer exactly once: only when this newly joined user verifies.
        if referrer:
            already=c.execute("SELECT 1 FROM users WHERE user_id=? AND joined=1",(uid,)).fetchone()
            # joined was set above; use unique referral ledger for idempotency.
            exists=c.execute("SELECT 1 FROM credited_referrals WHERE referee=?",(uid,)).fetchone()
            if not exists:
                c.execute("UPDATE users SET coins=coins+1 WHERE user_id=?",(referrer,))
                c.execute("INSERT INTO credited_referrals(referee,referrer) VALUES(?,?)",(uid,referrer))
        c.commit(); c.close()
        await q.message.reply_text("✅ Channel verified! Your referral has been credited if you joined through a referral link.",reply_markup=menu())
    elif q.data=="profile":
        c=db(); total=c.execute("SELECT COUNT(*) FROM credited_referrals WHERE referrer=?",(uid,)).fetchone()[0]; c.close()
        await q.message.reply_text(f"📊 Your Profile\n\n💰 Balance: {coins} coins\n👥 Verified Referrals: {total}\n🔑 Required: {REFS_REQUIRED} coins",reply_markup=menu())
    elif q.data=="getkey":
        if coins < REFS_REQUIRED:
            await q.message.reply_text(f"❌ Not enough coins.\n\nYour balance: {coins}/{REFS_REQUIRED}\nRefer {REFS_REQUIRED-coins} more user(s).",reply_markup=menu()); return
        c=db()
        keyrow=c.execute("SELECT id,key_text FROM keys WHERE used_by IS NULL ORDER BY id LIMIT 1").fetchone()
        if keyrow:
            kid,key=keyrow
            c.execute("UPDATE keys SET used_by=?,used_at=CURRENT_TIMESTAMP WHERE id=?",(uid,kid))
            c.execute("UPDATE users SET coins=coins-? WHERE user_id=?",(REFS_REQUIRED,uid))
            c.execute("INSERT INTO claims(user_id,key_text) VALUES(?,?)",(uid,key))
            c.commit(); c.close()
            await q.message.reply_text("🎉 Congratulations! Your FREE KEY:\n\n`"+key+"`",parse_mode="Markdown",reply_markup=menu())
            return
        c.close()
        if KEY_API_URL:
            await q.message.reply_text("⚠️ API mode is configured, but provider-specific request format must be added before live key generation. Please contact admin.")
        else:
            await q.message.reply_text("⚠️ Keys are currently out of stock. Please try later.",reply_markup=menu())

async def addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /addkey KEY1 KEY2 KEY3\nOr send one key after /addkey."); return
    c=db(); added=0
    for k in context.args:
        try: c.execute("INSERT INTO keys(key_text) VALUES(?)",(k,)); added+=1
        except sqlite3.IntegrityError: pass
    c.commit(); c.close()
    await update.message.reply_text(f"✅ Added {added} key(s).")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    c=db()
    users=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    refs=c.execute("SELECT COUNT(*) FROM credited_referrals").fetchone()[0]
    stock=c.execute("SELECT COUNT(*) FROM keys WHERE used_by IS NULL").fetchone()[0]
    used=c.execute("SELECT COUNT(*) FROM keys WHERE used_by IS NOT NULL").fetchone()[0]
    c.close()
    await update.message.reply_text(f"📊 Stats\nUsers: {users}\nVerified referrals: {refs}\nKeys in stock: {stock}\nKeys delivered: {used}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commands:\n/start - Open menu\nAdmin: /addkey KEY1 KEY2\n/admin stats: /stats")

def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Add it in TeleBotHost environment variables.")
    if not CHANNEL_ID:
        log.warning("CHANNEL_ID is empty: referral verification will not work until configured.")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("addkey",addkey))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    log.info("Referral bot is starting...")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
