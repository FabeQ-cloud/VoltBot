from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import sqlite3
import asyncio
import contextlib
from dotenv import load_dotenv

# Zmienione na 'main', ponieważ plik bota nazywa się teraz main.py
from main import bot  

@contextlib.asynccontextmanager
async def lifespan(app_instance):
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("[❌] Error: DISCORD_TOKEN not found in environment variables!")
    else:
        print("[🤖] Initializing Discord bot from www.py...")
        loop = asyncio.get_running_loop()
        loop.create_task(bot.start(TOKEN))
        
        await asyncio.sleep(4) 
        print("[✅] VoltBot background task started successfully.")
        
    yield 
    
    print("[💤] Shutting down VoltBot...")
    await bot.close()

app = FastAPI(lifespan=lifespan)

import www
www.bot_instance = bot

base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)
DB_PATH = os.path.join(base_dir, "volt.db")

@app.get("/")
async def root():
    return RedirectResponse(url="/shop")

@app.get("/shop", response_class=HTMLResponse)
async def read_shop(request: Request):
    guild_count = len(bot.guilds) if bot else 0
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={"request": request, "guild_count": guild_count, "user_data": None}
    )

@app.post("/shop", response_class=HTMLResponse)
async def check_profile(request: Request, user_id: str = Form(...)):
    guild_count = len(bot.guilds) if bot else 0
    
    username = f"User {user_id}"
    balance = 0
    is_premium = False

    if bot:
        try:
            user = await bot.fetch_user(int(user_id))
            if user:
                username = user.name
        except Exception:
            pass

    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT balance, is_premium FROM users WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
            if row:
                balance = row[0]
                is_premium = bool(row[1])
            conn.close()
        except Exception as e:
            print(f"Database error: {e}")

    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "request": request, 
            "guild_count": guild_count, 
            "user_data": {
                "id": user_id, 
                "username": username, 
                "balance": balance, 
                "premium": is_premium
            }
        }
    )
