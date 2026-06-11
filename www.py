from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import sqlite3
import asyncio
import contextlib
from dotenv import load_dotenv

# Importujemy obiekt bota z Twojego pliku VoltBot.py
from VoltBot import bot  

# Tworzymy funkcję lifespan bezpośrednio tutaj
@contextlib.asynccontextmanager
async def lifespan(app_instance):
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("[❌] Brak DISCORD_TOKEN w www.py!")
    else:
        print("[🤖] Inicjalizacja bota z poziomu www.py...")
        # Odpalamy bota w tle tego samego procesu Uvicorna
        loop = asyncio.get_running_loop()
        loop.create_task(bot.start(TOKEN))
        
        await asyncio.sleep(5) 
        print("[✅] Bot powinien być już online (www.py).")
        
    yield 
    
    print("[💤] Zamykanie bota...")
    await bot.close()

# Przekazujemy lifespan do FastAPI
app = FastAPI(lifespan=lifespan)

# Przekazujemy referencję do bota, żeby widoki /shop mogły z niego korzystać
import www
www.bot_instance = bot

# Definicje ścieżek
base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)
DB_PATH = os.path.join(base_dir, "volt.db")


# 1. Przekierowanie ze strony głównej do sklepu
@app.get("/")
async def root():
    return RedirectResponse(url="/shop")

# 2. Wyświetlanie sklepu pod adresem /shop
@app.get("/shop", response_class=HTMLResponse)
async def read_shop(request: Request):
    guild_count = len(bot.guilds) if bot else 0
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={"request": request, "guild_count": guild_count, "user_data": None}
    )

# 3. Obsługa formularza (szukanie profilu) pod adresem /shop
@app.post("/shop", response_class=HTMLResponse)
async def check_profile(request: Request, user_id: str = Form(...)):
    guild_count = len(bot.guilds) if bot else 0
    
    username = f"User {user_id}"
    coins = 0
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
            cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
            if row:
                coins = row[0]
            conn.close()
        except Exception as e:
            print(f"Błąd bazy danych: {e}")

    if user_id == "1490030330084720892": 
        is_premium = True

    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "request": request, 
            "guild_count": guild_count, 
            "user_data": {"id": user_id, "username": username, "coins": coins, "premium": is_premium}
        }
    )
