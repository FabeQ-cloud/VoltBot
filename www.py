from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import sqlite3

app = FastAPI()

# Ustawienia ścieżek
base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Używamy ścieżki względnej, żeby działało na serwerze
DB_PATH = os.path.join(base_dir, "volt.db")
bot_instance = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Obsługa wyświetlenia strony sklepu."""
    guild_count = len(bot_instance.guilds) if bot_instance else 0
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={"request": request, "guild_count": guild_count, "user_data": None}
    )

@app.post("/", response_class=HTMLResponse)
async def check_profile(request: Request, user_id: str = Form(...)):
    """Obsługa wysłania formularza (Check Player Profile)."""
    guild_count = len(bot_instance.guilds) if bot_instance else 0
    
    username = f"User {user_id}"
    coins = 0
    is_premium = False

    # Próba pobrania nazwy użytkownika z bota
    if bot_instance:
        try:
            user = await bot_instance.fetch_user(int(user_id))
            if user:
                username = user.name
        except Exception:
            pass

    # Odczyt z bazy danych
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

    # Sprawdzenie premium (możesz tu dodać logikę z bazy danych)
    if user_id == "1490030330084720892": 
        is_premium = True

    user_data = {
        "id": user_id,
        "username": username,
        "coins": coins,
        "premium": is_premium
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={"request": request, "guild_count": guild_count, "user_data": user_data}
    )