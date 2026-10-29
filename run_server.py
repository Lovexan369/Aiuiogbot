
import os, asyncio, json, sqlite3, datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
load_dotenv()
TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=int(os.getenv("ADMIN_ID","8230488853"))
DB_PATH=os.getenv("DB_PATH","data/family.db")
AUD_PATH=Path("data/audience.json")
DOMAIN=os.getenv("DOMAIN_WHITELIST","xankongcocaking.duckdns.org")
app=FastAPI(title="AIUIOG v5 ULTIMATE", version="5.0.0")

def load_audience():
    if AUD_PATH.exists():
        try: return json.loads(AUD_PATH.read_text())
        except: return {"users":[]}
    return {"users":[]}
def save_audience(db):
    AUD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUD_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/health")
def health():
    return {"status":"ok","version":"5.0.0","domain":DOMAIN,"time":datetime.datetime.now().isoformat(),"audience":len(load_audience().get("users",[]))}

@app.get("/audience")
def audience(): return load_audience()

@app.get("/")
async def root():
    p=Path("web/index.html")
    if p.exists(): return HTMLResponse(p.read_text(encoding="utf-8"))
    return {"message":"AIUIOG v5 LIVE","docs":"/docs"}

@app.post("/broadcast")
async def api_broadcast(req: Request):
    data=await req.json()
    return {"queued": len(load_audience().get("users",[])), "text": data.get("text","")[:100]}

@app.post("/chat")
async def chat_api(req: Request):
    data=await req.json()
    q=data.get("question","")
    return {"answer": f"[Julio] Принял: {q}. Добавлено в план семьи Коваль. (07:30/21:00 cron активен)", "tg_id":0}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=load_audience(); uid=update.effective_user.id; args=context.args[0] if context.args else "direct"
    if uid not in db["users"]:
        db["users"].append(uid); save_audience(db)
    await update.message.reply_text(f"Бот в облаке! База: {len(db['users'])} чел.\nИсточник: {args}\nДом: https://{DOMAIN}")

async def parse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример: /parse @mychat"); return
    raw=context.args[0].replace("https://t.me/","@").replace("t.me/","@")
    if "/+" in raw or "joinchat" in raw:
        await update.message.reply_text("Приватная ссылка. Добавь бота админом и перешли сообщение из чата"); return
    try:
        chat=await context.bot.get_chat(raw if raw.startswith("@") else "@"+raw)
        cnt=await context.bot.get_chat_member_count(chat.id)
        botname=(await context.bot.get_me()).username
        link=f"https://t.me/{botname}?start=from_{str(chat.id).replace('-100','')}"
        await update.message.reply_text(f"Чат '{chat.title}' ({cnt} чел)\nСсылка:\n{link}")
    except Exception as e: await update.message.reply_text(f"Chat not found: {e}")

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fwd=update.message.forward_from_chat
    if not fwd: return
    botname=(await context.bot.get_me()).username
    link=f"https://t.me/{botname}?start=from_{str(fwd.id).replace('-100','')}"
    await update.message.reply_text(f"Приватный чат сохранен! Ссылка:\n{link}")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    txt=update.message.text.strip()
    ids=[int(p) for p in txt.replace("\n"," ").split() if p.isdigit()]
    if ids and len(txt)<5000 and context.user_data.get("mode")!="broadcast":
        db=load_audience(); db["users"]=list(set(db["users"]+ids)); save_audience(db)
        await update.message.reply_text(f"Залито {len(ids)} ID. Всего: {len(db['users'])}"); return
    if context.user_data.get("mode")=="broadcast":
        db=load_audience(); sent=0
        for uid in db["users"]:
            try: await context.bot.send_message(uid,txt); sent+=1; await asyncio.sleep(0.05)
            except: pass
        context.user_data["mode"]=None
        await update.message.reply_text(f"Готово {sent}/{len(db['users'])}"); return
    if txt=="📤 Рассылка":
        context.user_data["mode"]="broadcast"; await update.message.reply_text("Пришли текст для рассылки"); return
    db=load_audience(); await update.message.reply_text(f"База: {len(db['users'])} юзеров\nКоманды: /parse @chat, 📤 Рассылка")

async def run_bot():
    if not TOKEN: print("BOT_TOKEN not set"); return
    req=HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    app_bot=ApplicationBuilder().token(TOKEN).request(req).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("parse", parse_cmd))
    app_bot.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("🤖 Telegram bot polling...")
    await app_bot.initialize(); await app_bot.start(); await app_bot.updater.start_polling(); await asyncio.Event().wait()

if __name__=="__main__":
    import uvicorn, threading
    Path("data").mkdir(exist_ok=True)
    if not Path(DB_PATH).exists():
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn=sqlite3.connect(DB_PATH)
        conn.executescript(open("db/schema.sql").read()); conn.commit()
    def start_bot(): asyncio.run(run_bot())
    threading.Thread(target=start_bot, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8000")))
