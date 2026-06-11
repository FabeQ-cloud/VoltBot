import sqlite3
import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "volt.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            duration_days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by_user_id TEXT,
            expires_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_license_key(key: str, days: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO licenses (license_key, duration_days) VALUES (?, ?)", (key, days))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def redeem_license_key(key: str, user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT duration_days, is_used FROM licenses WHERE license_key = ?", (key,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return "invalid"
    duration_days, is_used = result
    if is_used == 1:
        conn.close()
        return "used"
    
    expiration_date = (datetime.datetime.now() + datetime.timedelta(days=duration_days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE licenses SET is_used = 1, used_by_user_id = ?, expires_at = ? WHERE license_key = ?", (user_id, expiration_date, key))
    conn.commit()
    conn.close()
    return "success"

def check_user_license(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT expires_at FROM licenses WHERE used_by_user_id = ? AND is_used = 1", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None
    
init_db()
