from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import sqlite3

app = FastAPI()

base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)
DB_PATH = os.path.join(base_dir, "volt.db")

DB_PATH = "/home/fabian-zielenkiewicz/DiscordBot/venv/volt.db"
bot_instance = None

@app.post("/", response_class=HTMLResponse)
async def check_profile(request: Request, user_id: str = Form(...)):
    guild_count = len(bot_instance.guilds) if bot_instance else 0
    
    username = f"User {user_id}"
    coins = 0
    is_premium = False

    if bot_instance:
        try:
            user = await bot_instance.fetch_user(int(user_id))
            if user:
                username = user.name
        except Exception:
            pass

    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT balance FROM economy WHERE user_id = ?",
                (int(user_id),)
            )
            row = cursobase_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)
DB_PATH = os.path.join(base_dir, "volt.db")r.fetchone()

            if row:
                coins = row[0]
                print(f"[SUKCES] Znaleziono użytkownika! Monety: {coins}") # Zobaczysz to w terminalu
            else:
                print(f"[INFO] Brak użytkownika o ID {user_id} w tabeli economy.")

            conn.close()
        except Exception as e:
            print(f"Błąd bazy danych: {e}")
    else:
        print(f"Nie znaleziono pliku bazy danych pod ścieżką: {DB_PATH}")

    
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
        context={"guild_count": guild_count, "user_data": user_data}
    )
