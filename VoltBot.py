from email import message
from collections import defaultdict
import time
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import uvicorn
from datetime import timedelta
import sqlite3
import random 
from typing import Optional
import datetime
from functools import wraps
import database # type: ignore
import secrets
import os
from dotenv import load_dotenv
import contextlib
from fastapi import FastAPI
import collections

user_last_vote = {}  # format: {user_id: datetime_object}


class VoteCommand(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        
async def setup(bot):
    await bot.add_cog(VoteCommand(bot))

class VoltBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # To jest najlepsze miejsce na synchronizację
        synced = await self.tree.sync()
        print(f"[✅] Zsynchronizowano {len(synced)} komend!")

    async def on_ready(self):
        print(f"[🚀] Zalogowano jako {self.user}!")
        print(f"[🔍] Bot widzi {len(self.tree.get_commands())} komend.")

bot = VoltBot()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TOKEN = "MTUxMjAwMDUxNjg2MTg1Nzk4Mg.G1RCbd.7LKKyjHe3--zMMFj82PGxLCvA6m48rJJ99HmUc"

user_message_times = defaultdict(list)
user_recent_messages = defaultdict(list)

user_last_messages = defaultdict(list)

warnings = {}

COMMANDS = [
    ("/ping", "Check bot latency"),
    ("/help", "Show all commands"),
    ("/clear", "Delete messages"),
    ("/kick", "Kick a user"),
    ("/ban", "Ban a user"),
    ("/ticket", "Open support ticket"),
]

conn = sqlite3.connect("volt.db")
cursor = conn.cursor()



cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER,
    warns INTEGER DEFAULT 0
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    last_daily REAL DEFAULT 0,
    last_work REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    last_message REAL DEFAULT 0
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER
)
""")

conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS welcome_config (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel INTEGER,
    leave_channel INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS temp_bans (
    user_id INTEGER,
    guild_id INTEGER,
    unban_time INTEGER
)
""")
conn.commit()

conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS level_rewards (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS licenses (
    guild_id INTEGER PRIMARY KEY,
    plan TEXT,
    expires INTEGER
)
""")
conn.commit()

conn.commit()

try:
    cursor.execute("ALTER TABLE economy ADD COLUMN last_work REAL DEFAULT 0")
except sqlite3.OperationalError:
    pass

conn.commit()

conn.commit()

conn.commit()

def init_db():
    # Wymuszamy absolutną ścieżkę, żeby bot zawsze widział ten sam plik
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Usuwamy stare, niedopasowane tabele (skoro i tak są puste)
    cursor.execute("DROP TABLE IF EXISTS subscriptions;")
    cursor.execute("DROP TABLE IF EXISTS license_keys;")
    cursor.execute("DROP TABLE IF EXISTS warnings;") # Resetujemy też stare warnings pod serwery
    
    # 2. Tabela: Wygenerowane i używane licencje (Premium na serwer pod /ticket)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            duration_days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by_user_id TEXT,  -- Tutaj ląduje guild_id (ID serwera)
            expires_at INTEGER
        )
    """)
    
    # 3. Tabela: Ostrzeżenia (Wersja bezpieczna, wieloserwerowa)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp INTEGER
        )
    """)
    
    # 4. Tabela: Ekonomia (Dbamy o to, żeby była, jeśli jej używasz)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS economy (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_daily REAL DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    print("✨ [DATABASE] Wszystkie tabele w volt.db zostały pomyślnie zsynchronizowane z kodem!")

# Uruchamiamy tworzenie i aktualizację tabel przy starcie
init_db()

def init_subs_db():
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    # Tabela przechowuje ID użytkownika oraz czas (Timestamp Unix), do kiedy ważne jest Premium
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            premium_until INTEGER
        )
    """)
    conn.commit()
    conn.close()

# Wywołaj tę funkcję przy starcie bota:
init_subs_db()

def check_premium_db(guild_id: int) -> bool:
    """Sprawdza bezpiecznie w bazie danych, czy serwer ma aktywną i niewygasłą licencję Premium."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    current_time = int(time.time())

    try:
        # Pobieramy czas wygaśnięcia dla serwera z poprawnej kolumny used_by_user_id
        cursor.execute(
            "SELECT expires_at FROM licenses WHERE used_by_user_id = ? AND is_used = 1",
            (str(guild_id),),
        )
        row = cursor.fetchone()

        # Jeśli licencja istnieje i jej czas wygaśnięcia jest większy niż obecny czas
        if row and row[0] is not None:
            if int(row[0]) > current_time:
                return True
                
    except Exception as e:
        print(f"❌ [DB ERROR] check_premium_db error: {e}")
        
    finally:
        # Blok finally wykona się ZAWSZE, gwarantując bezpieczne zamknięcie bazy
        conn.close()

    return False
    
def redeem_key_logic(user_id, input_key):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Szukamy klucza (czyszcząc spacje)
    clean_key = input_key.strip()
    cursor.execute("SELECT days FROM license_keys WHERE key_code = ?", (clean_key,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"status": "invalid"}
        
    days_to_add = row[0]
    seconds_to_add = days_to_add * 24 * 60 * 60
    now = int(time.time())
    user_id_int = int(user_id)
    
    # Sprawdzamy, czy użytkownik ma już aktywne Premium
    cursor.execute("SELECT premium_until FROM subscriptions WHERE user_id = ?", (user_id_int,))
    sub_row = cursor.fetchone()
    
    if sub_row and sub_row[0] > now:
        new_expiry = sub_row[0] + seconds_to_add  # Przedłużamy obecne premium
    else:
        new_expiry = now + seconds_to_add         # Premium leci od teraz
        
    # Zapisujemy subskrypcję
    cursor.execute("""
        INSERT OR REPLACE INTO subscriptions (user_id, premium_until)
        VALUES (?, ?)
    """, (user_id_int, new_expiry))
    
    # Usuwamy zużyty klucz
    cursor.execute("DELETE FROM license_keys WHERE key_code = ?", (clean_key,))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "days": days_to_add}

def is_premium(user_id: int) -> bool:
    # Zamieniamy ID na string, bo tak zapisujemy w bazie
    uid_str = str(user_id)
    expiration = database.check_user_license(uid_str)
    
    if expiration:
        return True
    return False

app = FastAPI()

def premium_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("❌ This command cannot be used in DMs.", ephemeral=True)
            return False

        # Sprawdzamy stan licencji w osobnym wątku
        has_premium = await asyncio.to_thread(check_premium_db, guild_id)
        
        if not has_premium:
            await interaction.response.send_message(
                "❌ **This feature requires Volt Premium!**\n"
                "Please enter a valid license key using `/license_redeem` or visit our store.",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

def grant_premium(user_id, days=30):
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    
   
    seconds_to_add = days * 24 * 60 * 60
    
   
    cursor.execute("SELECT premium_until FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    now = int(time.time())
    if row and row[0] > now:
        
        new_expiry = row[0] + seconds_to_add
    else:
       
        new_expiry = now + seconds_to_add
        
    cursor.execute("""
        INSERT OR REPLACE INTO subscriptions (user_id, premium_until)
        VALUES (?, ?)
    """, (user_id, new_expiry))
    
    conn.commit()
    conn.close()
    print(f"💎 Granted premium to {user_id} for {days} days (Expires at Unix: {new_expiry})")

def init_new_features():
    # Podmień na taką nazwę pliku, jakiej używasz na Renderze
    conn = sqlite3.connect("volt.db") 
    cursor = conn.cursor()
    
    # 1. Tworzymy tabelę dla rynku kryptowalut
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_market (
        crypto_name TEXT PRIMARY KEY,
        current_price REAL
    );
    """)
    
    # 2. Bezpiecznie dodajemy kolumny vtc_owned i byt_owned do tabeli users
    # Używamy try/except, bo jeśli kolumny już istnieją, sqlite wywali błąd
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN vtc_owned REAL DEFAULT 0.0;")
        print("Dodano kolumnę vtc_owned do bazy danych.")
    except sqlite3.OperationalError:
        pass # Kolumna już istnieje, nic nie robimy

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN byt_owned REAL DEFAULT 0.0;")
        print("Dodano kolumnę byt_owned do bazy danych.")
    except sqlite3.OperationalError:
        pass # Kolumna już istnieje, nic nie robimy
        
    # 3. Wrzucamy początkowe ceny krypto, jeśli jeszcze ich nie ma
    cursor.execute("INSERT OR IGNORE INTO crypto_market (crypto_name, current_price) VALUES ('VoltCoin', 100.0);")
    cursor.execute("INSERT OR IGNORE INTO crypto_market (crypto_name, current_price) VALUES ('ByteCoin', 50.0);")
    
    conn.commit()
    conn.close()
    print("🤖 [VoltBot DB] Nowe tabele i kolumny ekonomii zostały sprawdzone/dodane!")
    
def ensure_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO economy (user_id, balance, last_daily) VALUES (?, 0, 0)",
        (user_id,)
    )
    conn.commit

def is_licensed(guild_id: int):
    cursor.execute(
        "SELECT expires FROM licenses WHERE guild_id = ?",
        (guild_id,)
    )

    row = cursor.fetchone()

    if not row:
        return False

    expires = row[0]

    if expires == 0:  # lifetime
        return True

    return time.time() < expires
        
# Upewnij się, że słowniki są zainicjalizowane na początku pliku:
user_message_times = collections.defaultdict(list)
user_recent_messages = collections.defaultdict(list)


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    user_id = message.author.id
    current_time = time.time()

    user_message_times[user_id].append(current_time)
    user_message_times[user_id] = [
        t for t in user_message_times[user_id] if current_time - t < 5
    ]

    user_recent_messages[user_id].append(message)
    user_recent_messages[user_id] = user_recent_messages[user_id][-20:]

    if len(user_message_times[user_id]) >= 6:

        last_spam_content = message.content if message.content else "[Brak tekstu / Obrazek]"
        spam_channel = message.channel
        spam_author = message.author

        for msg in user_recent_messages[user_id]:
            try:
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        user_message_times[user_id].clear()
        user_recent_messages[user_id].clear()

        warning = await spam_channel.send(
            f"{spam_author.mention} Stop spamming!"
        )

        log_channel = discord.utils.get(
            spam_author.guild.text_channels, name="voltbot-logs"
        )
        if not log_channel:
            log_channel = discord.utils.get(
                spam_author.guild.text_channels, name="mod-logs"
            )

        if log_channel:
            embed = discord.Embed(
                title="Anti-Spam Triggered",
                description=f"VoltBot successfully intercepted spam from {spam_author.mention}.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),  # Automatyczna data i godzina logu
            )
            embed.set_thumbnail(url=spam_author.display_avatar.url)
            embed.add_field(name="User", value=f"{spam_author} (ID: {spam_author.id})", inline=True)
            embed.add_field(name="Channel", value=spam_channel.mention, inline=True)
            embed.add_field(
                name="Last Message Caught",
                value=f"```\n{last_spam_content}\n```",
                inline=False,
            )
            embed.set_footer(text="VoltBot Security Systems")

            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                print(f"Brak uprawnień do wysłania logów na kanale {log_channel.name}")

        await asyncio.sleep(3)
        try:
            await warning.delete()
        except discord.NotFound:
            pass

        return

    await bot.process_commands(message)

def fix_economy_table():
    import os
    import sqlite3

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE economy ADD COLUMN streak INTEGER DEFAULT 0")
        print("✅ Added 'streak' column to economy table.")
    except sqlite3.OperationalError:
        print("🔸 'streak' column already exists or table issue.")

    # Dodajemy kolumnę last_daily, jeśli jej nie ma
    try:
        cursor.execute("ALTER TABLE economy ADD COLUMN last_daily INTEGER DEFAULT 0")
        print("✅ Added 'last_daily' column to economy table.")
    except sqlite3.OperationalError:
        print("🔸 'last_daily' column already exists.")

    conn.commit()
    conn.close()


# Wywołaj to raz przy starcie bota, a jak zadziała, to zakomentuj:
fix_economy_table()

user_msg_times = collections.defaultdict(list)

MSG_LIMIT = 5
TIME_WINDOW = 3

@bot.tree.command(name="ping", description="Check the bot's current latency and status")
async def ping(interaction: discord.Interaction):
    # Obliczamy opóźnienie w milisekundach
    latency = round(bot.latency * 1000)
    
    if latency < 100:
        status_color = discord.Color.from_rgb(0, 255, 240)
        status_text = "🟢 Excellent (Good connection)"
    elif latency < 250:
        status_color = discord.Color.gold()
        status_text = "🟡 Average (Slight delay)"
    else:
        status_color = discord.Color.red()
        status_text = "🔴 Poor (High latency)"

    embed = discord.Embed(
        title="⚡ VoltBot Latency Status",
        color=status_color
    )
    embed.add_field(name="📶 Connection Speed", value=f"`{latency} ms`", inline=True)
    embed.add_field(name="📊 Bot Status", value=status_text, inline=True)
    embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="help", description="Show all commands")
async def help(interaction: discord.Interaction):

    embed = discord.Embed(
        title="⚡ Volt Help",
        color=0x00ffcc
    )

    embed.add_field(
        name="Moderation",
        value="""
/warn
/warnings
/kick
/ban
/timeout
""",
        inline=False
    )

    embed.add_field(
        name="Economy",
        value="""
/balance
/work
/daily
/pay
/leaderboard
/coinflip
""",
        inline=False
    )

    embed.add_field(
        name="Levels",
        value="""
/rank
/stats
/setlevelreward
""",
        inline=False
    )

    embed.add_field(
        name="Tickets",
        value="""
/ticket
/close
""",
        inline=False
    )

    embed.add_field(
        name="Utility",
        value="""
/help
/ping
/serverinfo
/userinfo
""",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            category = await guild.create_category("Tickets")

        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}".lower(),
            category=category
        )

        await channel.set_permissions(guild.default_role, view_channel=False)
        await channel.set_permissions(user, view_channel=True, send_messages=True)

        await channel.send(f"Ticket created by {user.mention}")

        await interaction.response.send_message(
            f"Ticket created: {channel.mention}",
            ephemeral=True
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled", ephemeral=True)

def progress_bar(current, total, length=10):
    ratio = current / total

    # zabezpieczenie (żeby nie wyszło > 100%)
    if ratio > 1:
        ratio = 1

    filled = int(ratio * length)
    empty = length - filled

    return "🟩" * filled + "⬛" * empty

@bot.event
async def on_message(message):

    if message.author.bot:
        return
    
    user_id = message.author.id
    now = time.time()

    cursor.execute(
        "SELECT xp, level, last_message FROM levels WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO levels (user_id, xp, level, last_message) VALUES (?, 0, 0, 0)",
            (user_id,)
        )
        conn.commit()
        xp = 0
        level = 0
        last_message = 0
    else:
        xp, level, last_message = row

        if now - last_message < 10:
            return
        
        gained = random.randint(5, 15)
        xp += gained

        needed_xp = (level + 1) * 100

        if xp >= needed_xp:
            xp -= needed_xp
            level += 1

            await message.channel.send(
                f"{message.author.mention} leveled up to **Level {level}**!"
            )
        cursor.execute(
            "UPDATE levels SET xp = ?, level = ?, last_message = ? WHERE user_id = ?",
            (xp, level, now, user_id)
        )

        conn.commit()

@bot.event
async def on_member_join(member):

    cursor.execute(
        """
        SELECT welcome_channel
        FROM welcome_config
        WHERE guild_id = ?
        """,
        (member.guild.id,)
    )

    result = cursor.fetchone()

    if not result or result[0] is None:
        return
    
    channel = member.guild.get_channel(result[0])

    if not channel:
        return
    
    embed = discord.Embed(
        title="Welcome!",
        description=f"Welcome {channel.mention}!",
        color=discord.Color.green()

    )

    embed.add_field(
        name="Members",
        value=str(member.guild.member_count),
        inline=True
    )

    embed.add_field(
        name="Account created",
        value=member.created_at.strftime("%d-%m-%Y"),
        inline=True
    )

    embed.set_thumbnail(
        url=member.display.avatar.url
    )

    await channel.send(embed=embed)

async def unban_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        now = int(time.time())

        cursor.execute("""
            SELECT user_id, guild_id FROM temp_bans
            WHERE unban_time <= ?
        """, (now,))

        rows = cursor.fetchall()

        for user_id, guild_id in rows:

            guild = bot.get_guild(guild_id)

            if guild:

                try:
                    user = await bot.fetch_user(user_id)
                    await guild.unban(user, reason="Auto unban after 24h")
                except:
                    pass

            cursor.execute("""
                DELETE FROM temp_bans
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))

            conn.commit()

        await asyncio.sleep(60)  # sprawdzanie co 60 sekund

@bot.event
async def on_member_remove(member):

    cursor.execute(
        """
        SELECT leave_channel
        FROM welcome_config
        WHERE guild_id = ?
        """,
        (member.guild.id,)
    )

    result = cursor.fetchone()

    if not result or result[0] is None:
        return
    
    channel = member.guild.get_channel(result[0])

    if not channel:
        return
    
    embed = discord.Embed(
        title="Goodbye!",
        description=f"{member.name} left the server.",
        color=discord.Color.red()
    )

    embed.add_field(
        name="Members left",
        value=str(member.guild.member_count),
        inline=True
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await channel.send(embed=embed)

async def check_punishment(member: discord.Member, warn_count: int):

    guild = member.guild

    
    if warn_count == 1:

        until = datetime.datetime.utcnow() + datetime.timedelta(hours=6)

        try:
            await member.timeout(until, reason="Auto punish: 1 warn")
            return "Muted for 6 hours"
        except:
            return "Failed to mute (missing permissions)"

    
    elif warn_count == 2:

        try:
            await member.kick(reason="Auto punish: 2 warns")
            return "Kicked from server"
        except:
            return "Failed to kick (missing permissions)"

    
    elif warn_count >= 3:

        unban_time = int(time.time()) + 86400 

        await guild.ban(member, reason="Auto ban 24h")

        cursor.execute("""
            INSERT INTO temp_bans (user_id, guild_id, unban_time)
            VALUES (?, ?, ?)
        """, (member.id, guild.id, unban_time))

    conn.commit()

    return "Banned for 24h"

@bot.tree.command(name="ticket", description="Deploy the premium support ticket panel")
@premium_only()
async def ticket(interaction: discord.Interaction):
    # Tworzymy zaawansowany, czysty wizualnie Embed dla wersji Premium
    embed = discord.Embed(
        title="🎫 Support & Assistance Hub",
        description=(
            "Need help? You are in the right place! Click the button below "
            "to open a private support channel with the server administration.\n\n"
            "**⚙️ Before opening a ticket:**\n"
            "• Please be patient, staff will assist you shortly.\n"
            "• Provide as many details about your issue as possible.\n"
            "• Do not ping staff members immediately after opening."
        ),
        color=0x00ffcc # Twój flagowy neonowy błękit
    )
    
    # Dodajemy profesjonalne sekcje informacyjne
    embed.add_field(
        name="🔒 Secure Channel", 
        value="Every ticket creates a private room visible only to you and the support team.", 
        inline=False
    )
    
    # Elegancka stopka systemowa
    embed.set_footer(
        text=f"Powered by VoltBot Premium • {interaction.guild.name}", 
        icon_url=interaction.guild.icon.url if interaction.guild.icon else None
    )

    # Informujemy admina w ukrytej wiadomości, że panel został pomyślnie wysłany
    await interaction.response.send_message(
        "✅ **Success!** Premium Ticket Panel has been deployed successfully.", 
        ephemeral=True
    )

    # Wysyłamy właściwy panel na kanał (bez ephemeral, żeby wszyscy widzieli)
    await interaction.channel.send(
        embed=embed,
        view=TicketView()
    )

@bot.tree.command(name="close", description="Close and delete this ticket channel safely")
async def close(interaction: discord.Interaction):
    channel = interaction.channel

    # Bezpieczeństwo: Sprawdzamy, czy to na pewno kanał ticketowy
    if "ticket-" not in channel.name:
        embed_error = discord.Embed(
            title="❌ Action Denied",
            description="This command can only be executed inside an active ticket channel.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Tworzymy profesjonalny Embed informujący o zamykaniu ticketu
    embed_close = discord.Embed(
        title="🔒 Closing Ticket",
        description=(
            f"This ticket has been marked as completed by **{interaction.user.mention}**.\n"
            "This channel will be permanently deleted in **5 seconds**."
        ),
        color=discord.Color.orange()
    )
    embed_close.set_footer(text="VoltBot Ticket System • Safe Deletion")

    # Wysyłamy informację na kanale (nie jako ephemeral, żeby użytkownik też widział)
    await interaction.response.send_message(embed=embed_close)

    # Odliczanie 5 sekund (daje czas na przeczytanie i ewentualną reakcję)
    await asyncio.sleep(5)

    # Ostateczne usunięcie kanału
    try:
        await channel.delete()
    except discord.Forbidden:
        # Na wypadek, gdyby bot stracił uprawnienia w międzyczasie
        print(f"Error: Missing permissions to delete channel {channel.name}")
    
@bot.tree.command(name="clear", description="Bulk delete a specified amount of messages from this channel")
@app_commands.describe(amount="The number of messages to delete (Maximum: 100)")
async def clear(interaction: discord.Interaction, amount: int):
    # 1. Zabezpieczenie uprawnień użytkownika
    if not interaction.user.guild_permissions.manage_messages:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Manage Messages** permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # 2. Walidacja wprowadzonej liczby (Zabezpieczenie przed crashem)
    if amount < 1 or amount > 100:
        embed_invalid = discord.Embed(
            title="⚠️ Invalid Amount",
            description="You can only delete between **1 and 100** messages at a time.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_invalid, ephemeral=True)
        return

    # Deferujemy odpowiedź jako ukrytą (ephemeral), żeby nie śmiecić na czyszczonym kanale
    await interaction.response.defer(ephemeral=True)

    try:
        # 3. Wykonanie czyszczenia (Bez +1, bo komendy Slash nie tworzą fizycznej wiadomości użytkownika)
        deleted = await interaction.channel.purge(limit=amount)
        
        # 4. Przygotowanie pięknego podsumowania w Embedzie
        embed_success = discord.Embed(
            title="🧹 Channel Cleaned",
            color=0x00fff0 # Twój neonowy błękit VoltBota
        )
        embed_success.add_field(name="💬 Requested", value=f"`{amount}` messages", inline=True)
        embed_success.add_field(name="🗑️ Successfully Deleted", value=f"`{len(deleted)}` messages", inline=True)
        
        # Małe ostrzeżenie, jeśli bot usunął mniej wiadomości niż żądano (np. przez barierę 14 dni)
        if len(deleted) < amount:
            embed_success.set_footer(text="Note: Messages older than 14 days cannot be deleted by Discord bots.")
        else:
            embed_success.set_footer(text=f"Moderator: {interaction.user.name}")

        # Wysyłamy ostateczne potwierdzenie
        await interaction.followup.send(embed=embed_success, ephemeral=True)

    except discord.Forbidden:
        # Obsługa sytuacji, gdy bot nie ma uprawnień na tym konkretnym kanale
        embed_err = discord.Embed(
            title="❌ Bot Error",
            description="I don't have permission to manage messages on this channel. Please check my server roles.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed_err, ephemeral=True)
        
    except Exception as e:
        print(f"❌ [CLEAR ERROR] {e}")
        await interaction.followup.send(f"❌ An unexpected error occurred: `{e}`", ephemeral=True)
        
@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(user="The member to kick", reason="The reason for the kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    # 1. Sprawdzenie uprawnień moderatora
    if not interaction.user.guild_permissions.kick_members:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Kick Members** permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # 2. Zabezpieczenie przed wyrzuceniem samego siebie
    if user.id == interaction.user.id:
        embed_self = discord.Embed(
            title="⚠️ Action Denied",
            description="You cannot kick yourself!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_self, ephemeral=True)
        return

    # 3. Sprawdzenie hierarchii ról (Czy moderator stoi wyżej niż cel)
    if interaction.user.top_role <= user.top_role and interaction.guild.owner_id != interaction.user.id:
        embed_hierarchy = discord.Embed(
            title="⚠️ Hierarchy Error",
            description="You cannot kick this member because they have an equal or higher role than you.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_hierarchy, ephemeral=True)
        return

    # 4. Sprawdzenie czy bot stoi wystarczająco wysoko w rolach, by wyrzucić cel
    bot_member = interaction.guild.me
    if bot_member.top_role <= user.top_role:
        embed_bot_hierarchy = discord.Embed(
            title="⚠️ Bot Hierarchy Error",
            description="I cannot kick this member because my highest role is lower than or equal to their highest role.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=bot_bot_hierarchy, ephemeral=True)
        return

    # Deferujemy odpowiedź, bo wysyłanie DM może chwilę potrwać
    await interaction.response.defer(ephemeral=False)

    # 5. Próba wysłania wiadomości prywatnej (DM) do użytkownika PRZED wyrzuceniem
    try:
        embed_dm = discord.Embed(
            title=f"🚪 You were kicked from {interaction.guild.name}",
            color=discord.Color.red()
        )
        embed_dm.add_field(name="💬 Reason", value=reason, inline=False)
        embed_dm.set_footer(text="If you believe this was a mistake, please contact the server administration.")
        await user.send(embed=embed_dm)
    except discord.Forbidden:
        # Użytkownik może mieć zablokowane DM-y od obcych, ignorujemy ten błąd i lecimy dalej
        pass

    # 6. Właściwa akcja wyrzucenia z serwera
    try:
        await user.kick(reason=f"Kicked by {interaction.user} | Reason: {reason}")
        
        # Piękny Embed potwierdzający akcję na kanale
        embed_success = discord.Embed(
            title="🔨 Member Kicked",
            color=discord.Color.red()
        )
        embed_success.add_field(name="👤 Target", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed_success.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
        embed_success.add_field(name="📝 Reason", value=reason, inline=False)
        embed_success.set_thumbnail(url=user.display_avatar.url)
        embed_success.set_footer(text=f"VoltBot Moderation Suite")
        
        await interaction.followup.send(embed=embed_success)

    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to kick this user. Check my Discord permissions.", ephemeral=True)
    except Exception as e:
        print(f"❌ [KICK ERROR] {e}")
        await interaction.followup.send(f"❌ An error occurred: `{e}`", ephemeral=True)
        
@bot.tree.command(name="ban", description="Permanently ban a member from the server")
@app_commands.describe(
    user="The member to ban", 
    reason="The reason for the ban",
    delete_days="Delete user's message history from the last X days"
)
@app_commands.choices(delete_days=[
    app_commands.Choice(name="Don't delete any", value=0),
    app_commands.Choice(name="Previous 24 hours", value=1),
    app_commands.Choice(name="Previous 7 days", value=7)
])
async def ban(
    interaction: discord.Interaction, 
    user: discord.Member, 
    reason: str = "No reason provided",
    delete_days: int = 0
):
    # 1. Sprawdzenie uprawnień moderatora
    if not interaction.user.guild_permissions.ban_members:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Ban Members** permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # 2. Zabezpieczenie przed zbanowaniem samego siebie
    if user.id == interaction.user.id:
        embed_self = discord.Embed(
            title="⚠️ Action Denied",
            description="You cannot ban yourself!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_self, ephemeral=True)
        return

    # 3. Sprawdzenie hierarchii ról (Czy moderator stoi wyżej niż cel)
    if interaction.user.top_role <= user.top_role and interaction.guild.owner_id != interaction.user.id:
        embed_hierarchy = discord.Embed(
            title="⚠️ Hierarchy Error",
            description="You cannot ban this member because they have an equal or higher role than you.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_hierarchy, ephemeral=True)
        return

    # 4. Sprawdzenie czy bot stoi wystarczająco wysoko w rolach
    bot_member = interaction.guild.me
    if bot_member.top_role <= user.top_role:
        embed_bot_hierarchy = discord.Embed(
            title="⚠️ Bot Hierarchy Error",
            description="I cannot ban this member because my highest role is lower than or equal to their highest role.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_bot_hierarchy, ephemeral=True)
        return

    # Deferujemy, bo wysyłanie DM i czyszczenie wiadomości może zająć botu dłuższą chwilę
    await interaction.response.defer(ephemeral=False)

    # 5. Próba wysłania wiadomości prywatnej (DM) PRZED nałożeniem bana
    try:
        embed_dm = discord.Embed(
            title="🔨 You have been banned",
            description=f"You were permanently banned from **{interaction.guild.name}**.",
            color=discord.Color.from_rgb(150, 0, 0)
        )
        embed_dm.add_field(name="📝 Reason", value=reason, inline=False)
        embed_dm.set_footer(text="This ban is permanent unless appealed by the server administration.")
        await user.send(embed=embed_dm)
    except discord.Forbidden:
        # Ignorujemy błąd, jeśli użytkownik ma zablokowane DM-y
        pass

    # 6. Wykonanie bana wraz z czyszczeniem historii wiadomości
    try:
        # Konwertujemy wybrane dni na sekundy dla parametru delete_message_seconds
        delete_seconds = delete_days * 24 * 60 * 60
        
        await user.ban(
            reason=f"Banned by {interaction.user} | Reason: {reason}",
            delete_message_seconds=delete_seconds
        )
        
        # Piękny Embed potwierdzający banicję na kanale
        embed_success = discord.Embed(
            title="💥 Member Permanently Banned",
            color=discord.Color.from_rgb(180, 0, 0)
        )
        embed_success.add_field(name="👤 Target User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed_success.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
        embed_success.add_field(name="🗑️ History Cleared", value=f"Last {delete_days} days", inline=True)
        embed_success.add_field(name="📝 Reason", value=reason, inline=False)
        embed_success.set_thumbnail(url=user.display_avatar.url)
        embed_success.set_footer(text="VoltBot Moderation Suite • Permanent Punishment")
        
        await interaction.followup.send(embed=embed_success)

    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to ban this user. Verify my permissions in Server Settings.", ephemeral=True)
    except Exception as e:
        print(f"❌ [BAN ERROR] {e}")
        await interaction.followup.send(f"❌ An error occurred: `{e}`", ephemeral=True)

def add_warning_to_db(guild_id: int, user_id: int, reason: str) -> int:
    """Zapisuje warna w parze serwer+użytkownik i zwraca aktualną liczbę ostrzeżeń."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # Zapisujemy warn przypisany do konkretnego serwera (guild_id) i użytkownika (user_id)
        cursor.execute(
            "INSERT INTO warnings (guild_id, user_id, reason) VALUES (?, ?, ?)",
            (str(guild_id), str(user_id), reason)
        )
        conn.commit()
        
        # Pobieramy sumę warnów tego użytkownika TYLKO na tym serwerze
        cursor.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
        warn_count = cursor.fetchone()[0]
        return warn_count
        
    finally:
        conn.close()


# --- KOMENDA SLASH /WARN ---
@bot.tree.command(name="warn", description="Issue a warning to a member")
@app_commands.describe(user="The member to warn", reason="The reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    # 1. Sprawdzenie uprawnień moderatora
    if not interaction.user.guild_permissions.kick_members:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Kick Members** permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # 2. Zabezpieczenie przed warnowaniem botów
    if user.bot:
        embed_bot = discord.Embed(
            title="⚠️ Action Denied",
            description="You cannot issue warnings to bots.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=bot, ephemeral=True)
        return

    # 3. Zabezpieczenie przed warnowaniem samego siebie
    if user.id == interaction.user.id:
        embed_self = discord.Embed(
            title="⚠️ Action Denied",
            description="You cannot warn yourself!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=self, ephemeral=True)
        return

    # 4. Sprawdzenie hierarchii ról (Zabezpieczenie przed warnowaniem adminów)
    if interaction.user.top_role <= user.top_role and interaction.guild.owner_id != interaction.user.id:
        embed_hierarchy = discord.Embed(
            title="⚠️ Hierarchy Error",
            description="You cannot warn this member because they have an equal or higher role than you.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_hierarchy, ephemeral=True)
        return

    # Deferujemy odpowiedź – operacje na bazie i DM mogą chwilę zająć
    await interaction.response.defer(ephemeral=False)

    # 5. Bezpieczne wykonanie operacji na bazie danych w osobnym wątku
    guild_id = interaction.guild_id
    try:
        warn_count = await asyncio.to_thread(add_warning_to_db, guild_id, user.id, reason)
    except sqlite3.OperationalError as db_err:
        # Jeśli w bazie danych nie ma kolumny guild_id, obsłuż błąd
        print(f"❌ [DB WARN ERROR] Może brakować kolumny guild_id w tabeli warnings: {db_err}")
        await interaction.followup.send("❌ Database layout error. Inform bot owner.", ephemeral=True)
        return

    # 6. Wysyłanie ostrzeżenia w wiadomości prywatnej (DM) do użytkownika
    try:
        embed_dm = discord.Embed(
            title=f"⚠️ Warning Received in {interaction.guild.name}",
            description=f"You have been formally warned by the server moderation team.",
            color=discord.Color.orange()
        )
        embed_dm.add_field(name="📝 Reason", value=reason, inline=False)
        embed_dm.add_field(name="📊 Total Warnings on this server", value=f"`{warn_count}`", inline=False)
        embed_dm.set_footer(text="Please respect the server rules to avoid further punishments.")
        await user.send(embed=embed_dm)
    except discord.Forbidden:
        pass # Ignorujemy jeśli użytkownik ma zamknięte DM-y

    # 7. Wyświetlenie pięknego logu na kanale tekstowym
    embed_success = discord.Embed(
        title="⚠️ Member Warned",
        color=discord.Color.orange()
    )
    embed_success.add_field(name="👤 Target", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed_success.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
    embed_success.add_field(name="📝 Reason", value=reason, inline=False)
    embed_success.add_field(name="📊 Total Warnings", value=f"`{warn_count}`", inline=True)
    embed_success.set_thumbnail(url=user.display_avatar.url)
    embed_success.set_footer(text="VoltBot Moderation Suite")

    await interaction.followup.send(embed=embed_success)

@bot.tree.command(name="warnings", description="Check user warnings")
@app_commands.describe(user="User to check")
async def warnings_cmd(
    interaction: discord.Interaction,
    user: discord.Member
):

    cursor.execute(
        "SELECT reason FROM warnings WHERE user_id = ?",
        (user.id,)
    )

    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message(
            "No warnings found."
        )
        return

    text = "\n".join(
        [f"{i+1}. {r[0]}" for i, r in enumerate(rows)]
    )

    await interaction.response.send_message(
        f"Warnings for {user.mention}:\n\n{text}"
    )

@bot.tree.command(name="serverinfo", description="Show information about the server")
async def serverinfo(interaction: discord.Interaction):

    guild = interaction.guild

    embed = discord.Embed(
        title=f"{guild.name}",
        color=0x00ffcc
    )

    embed.add_field(
        name="Owner:",
        value=str(guild.owner),
        inline=False
    )

    embed.add_field(
        name="Members",
        value=str(guild.member_count),
        inline=True
    )

    embed.add_field(
        name="Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
            name="Roles",
            value=str(len(guild.roles)),
            inline=True
        )
    
    embed.add_field(
        name="Created",
        value=guild.created_at.strftime("%d-%m-%Y"),
        inline=False
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="userinfo", description="Show information about a user")
@app_commands.describe(user="Select a user")
async def userinfo(interaction: discord.Interaction, user: discord.Member):
    
    embed= discord.Embed(
        title=f"{user}",
        color=0x00ffcc
    )

    embed.add_field(
        name="User ID",
        value=str(user.id),
        inline=False
    )

    embed.add_field(
        name="Joined Server",
        value=user.joined_at.strftime("%d-%m-%Y"),
        inline=False
    )
    embed.add_field(
        name="Top Role",
        value=user.top_role.mention,
        inline=False
    )

    embed.add_field(
        name="Bot",
        value="Yes" if user.bot else "No",
        inline=False
    )

    embed.set_thumbnail(url=user.display_avatar.url)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="timeout", description="Timeout a user")
@app_commands.describe(
    user="User to timeout",
    minutes="Timeout duration in minutes",
    reason="Reason"
)
async def timeout(
    interaction: discord.Interaction,
    user: discord.Member,
    minutes: int,
    reason: str = "No reason"
):
    
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message(
            "You don't have permission",
            ephemeral=True
        )
        return
    try:
        await user.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        await interaction.response.send_message(
            f"{user.mention} has been timed out for {minutes} minute(s).\nReason: {reason}"

        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I can't timeout this user.",
            ephemeral=True
        )

@bot.tree.command(name="balance", description="Check your balance")
@premium_only()
async def balance(interaction: discord.Interaction):

    user_id = interaction.user.id

    
    cursor.execute(
        "SELECT balance FROM economy WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()
    balance = row[0] if row else 0


    cursor.execute(
        "SELECT COUNT(*) + 1 FROM economy WHERE balance > ?",
        (balance,)
    )

    rank = cursor.fetchone()[0]

    
    embed = discord.Embed(
        title="Volt Wallet",
        color=discord.Color.gold()
    )

    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    embed.add_field(
        name="Balance",
        value=f"**{balance:,}** coins",
        inline=True
    )

    embed.add_field(
        name="Leaderboard Rank",
        value=f"**#{rank}**",
        inline=True
    )

    
    embed.set_footer(
        text=f"Requested by {interaction.user.name}",
        icon_url=interaction.user.display_avatar.url
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward")
@premium_only()
async def daily(interaction: discord.Interaction):
    # Informujemy Discord, że bot przetwarza dane (zapobiega to zacięciu bota)
    await interaction.response.defer()

    user_id = interaction.user.id

    # 💰 TUTAJ DEFINIUJESZ ILOŚĆ MONET DLA UŻYTKOWNIKA
    custom_reward = 100

    # Definiujemy ścieżkę do bazy
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    # Otwieramy połączenie z timeoutem, żeby wątki na siebie nie czekały
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        # Szukamy użytkownika w bazie (sprawdzamy tekst i liczbę dla pewności)
        cursor.execute(
            "SELECT balance, last_daily, streak FROM economy WHERE user_id = ? OR user_id = ?",
            (int(user_id), str(user_id)),
        )
        row = cursor.fetchone()

        now = int(time.time())
        cooldown = 86400  # 24 godziny w sekundach

        if row:
            balance, last_daily, streak = row

            # 1. Sprawdzenie czasu (Cooldown)
            if last_daily and now - last_daily < cooldown:
                remaining = cooldown - (now - last_daily)
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60

                conn.close()  # Zamykamy połączenie przed wyjściem!
                await interaction.followup.send(
                    f"You already claimed daily!\nTry again in **{hours}h {minutes}m**",
                    ephemeral=True,
                )
                return

            # 2. Sprawdzenie streaku (czy minęło mniej niż 48h od ostatniego odebrania)
            if last_daily and now - last_daily <= cooldown * 2:
                streak += 1
            else:
                streak = 1

            reward = custom_reward
            new_balance = balance + reward

            # Aktualizacja danych w bazie
            cursor.execute(
                """
                UPDATE economy
                SET balance = ?, last_daily = ?, streak = ?
                WHERE user_id = ? OR user_id = ?
            """,
                (new_balance, now, streak, int(user_id), str(user_id)),
            )

        else:
            # Nowy użytkownik w systemie ekonomii bota
            streak = 1
            reward = custom_reward
            new_balance = reward

            # Dodanie nowego wpisu
            cursor.execute(
                """
                INSERT INTO economy (user_id, balance, last_daily, streak)
                VALUES (?, ?, ?, ?)
            """,
                (int(user_id), new_balance, now, streak),
            )

        # Zatwierdzamy zmiany w bazie danych
        conn.commit()

        # Wysyłamy piękny embed z nagrodą do użytkownika
        embed = discord.Embed(
            title="Daily Reward",
            description=f"+{reward} coins\nStreak: {streak} 🔥",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Balance", value=f"{new_balance:,} coins", inline=False
        )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        # JEŚLI COŚ SIĘ WYWALI W BAZIE, BOT NIE BĘDZIE WISIAŁ, TYLKO WYPLUJE BŁĄD!
        print(f"🔴 [CRITICAL ERROR IN /DAILY]: {error}")
        await interaction.followup.send(
            f"❌ An error occurred while executing the command: `{error}`",
            ephemeral=True,
        )

    finally:
        # Ten blok wykona się ZAWSZE, gwarantując zamknięcie bazy danych
        conn.close()
    
@bot.tree.command(name="work", description="Earn coins by working")
@premium_only()
async def work(interaction: discord.Interaction):

    user_id = interaction.user.id

    cursor.execute(
        "SELECT balance, last_work FROM economy WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    now = int(time.time())
    cooldown = 3600  # 1h

    jobs = [
        "🍔 Worked at McDonald's",
        "🚚 Delivered packages",
        "👨‍🍳 Cooked in a restaurant",
        "💻 Fixed a computer",
        "🧹 Cleaned offices",
        "📦 Worked in warehouse"
    ]

    job = random.choice(jobs)
    reward = random.randint(100, 500)

    if row:
        balance, last_work = row

        # ⏳ cooldown check
        if last_work and now - last_work < cooldown:

            elapsed = now - last_work
            remaining = cooldown - elapsed

            percent = int((elapsed / cooldown) * 100)

            bar = progress_bar(elapsed, cooldown, 10)

            minutes = remaining // 60
            seconds = remaining % 60

            embed = discord.Embed(
                title="You're tired!",
                description="You need to rest before working again",
                color=discord.Color.red()
            )

            embed.add_field(
                name="Cooldown progress",
                value=f"{bar} **{percent}%**",
                inline=False
            )

            embed.add_field(
                name="Time left",
                value=f"⏱{minutes}m {seconds}s",
                inline=False
            )

            await interaction.response.send_message(embed=embed)
            return

        new_balance = balance + reward

        cursor.execute(
            "UPDATE economy SET balance = ?, last_work = ? WHERE user_id = ?",
            (new_balance, now, user_id)
        )

    else:
        new_balance = reward

        cursor.execute(
            """
            INSERT INTO economy (user_id, balance, last_work)
            VALUES (?, ?, ?)
            """,
            (user_id, new_balance, now)
        )

    conn.commit()

    # 💼 success embed
    embed = discord.Embed(
        title="Work completed!",
        description=f"{job}",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Earned",
        value=f"**{reward} coins**",
        inline=True
    )

    embed.add_field(
        name="Balance",
        value=f"**{new_balance:,} coins**",
        inline=True
    )

    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pay", description="Send coins to another user")
@premium_only()
@app_commands.describe(
    user="User to send coins to",
    amount="Amount of coins"
)
async def pay(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):
    
    if amount <= 0:
        await interaction.response.send_message(
            "Amount must be greater than 0.",
            ephemeral=True
        )
        return
    
    sender_id = interaction.user.id
    receiver_id = user.id

    ensure_user(sender_id)
    ensure_user(receiver_id)

    cursor.execute(
        "SELECT balance FROM economy WHERE user_id = ?",
        (sender_id,)
    )

    sender_balance = cursor.fetchone()[0]

    if sender_balance < amount:
        await interaction.response.send_message(
            "You dont have enough coins.",
            ephemeral=True
        )
        return
    
    cursor.execute(
      "UPDATE economy SET balance = balance - ? WHERE user_id = ?",
      (amount, sender_id)
    )

    cursor.execute(
       "UPDATE economy SET balance = balance + ? WHERE user_id = ?",
       (amount, receiver_id)
    )

    conn.commit()

    await interaction.response.send_message(
        f"{interaction.user.mention} sent **{amount}** coins to {user.mention}!"
    )

@bot.tree.command(name="stats", description="View economy stats")
async def stats(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None
):

    if user is None:
        user = interaction.user

    ensure_user(user.id)

    cursor.execute(
        "SELECT balance FROM economy WHERE user_id = ?",
        (user.id,)
    )

    result = cursor.fetchone()

    if result is None:
        balance = 0
    else:
        balance = result[0]

    await interaction.response.send_message(
        f"Stats for **{user.display_name}**\n\n"
        f"Balance: **{balance} coins**"
    )

@bot.tree.command(name="unwarn", description="Remove the latest warning from a user")
@app_commands.describe(user="User to unwarn")
async def unwarn(interaction: discord.Interaction, user: discord.Member):

    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message(
            "You don't have permission.",
            ephemeral=True
        )
        return

    cursor.execute(
        "SELECT rowid FROM warnings WHERE user_id = ? ORDER BY rowid DESC LIMIT 1",
        (user.id,)
    )

    row = cursor.fetchone()

    if not row:
        await interaction.response.send_message(
            f"{user.mention} has no warnings."
        )
        return

    cursor.execute(
        "DELETE FROM warnings WHERE rowid = ?",
        (row[0],)
    )

    conn.commit()

    cursor.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ?",
        (user.id,)
    )

    remaining = cursor.fetchone()[0]

    await interaction.response.send_message(
        f"Removed latest warning from {user.mention}\n"
        f"Remaining warnings: **{remaining}**"
    )


@bot.tree.command(name="rank", description="Check your level")
@premium_only()
async def rank(
    interaction: discord.Interaction,
    user: discord.Member = None
):

    user = user or interaction.user

    cursor.execute(
        "SELECT xp, level FROM levels WHERE user_id = ?",
        (user.id,)
    )

    row = cursor.fetchone()

    if not row:
        await interaction.response.send_message(
            "No rank data yet."
        )
        return

    xp, level = row

    needed_xp = (level + 1) * 100

    percent = xp / needed_xp

    filled = int(percent * 10)
    empty = 10 - filled

    progress_bar = "█" * filled + "░" * empty

    embed = discord.Embed(
        title=f"{user.display_name}'s Rank",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Level",
        value=str(level),
        inline=True
    )

    embed.add_field(
        name="XP",
        value=f"{xp}/{needed_xp}",
        inline=True
    )

    embed.add_field(
        name="Progress",
        value=f"`{progress_bar}` {int(percent * 100)}%",
        inline=False
    )

    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="topxp", description="Top users by level")
async def topxp(interaction: discord.Interaction):

    cursor.execute("""
        SELECT user_id, level, xp FROM levels
        ORDER BY level DESC, xp DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message("No data yet.")
        return

    embed = discord.Embed(
        title="Top XP Users",
        color=discord.Color.gold()
    )

    description = ""

    for i, (user_id, level, xp) in enumerate(rows, start=1):

        user = await bot.fetch_user(user_id)

        description += f"**{i}. {user.name}** — Level {level} ({xp} XP)\n"

    embed.description = description

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="coinflip", description="Flip  a coin and gamble your coins")
@premium_only()
@app_commands.describe(amount="Amount of coins to bet")
async def coinflip(
    interaction: discord.Interaction,
    amount: int
):
    
    if amount <= 0:
        await interaction.response.send_message(
            "Amount must be greater than 0",
            ephemeral=True
        )
        return
    user_id = interaction.user.id
    
    ensure_user(user_id)

    cursor.execute(
        "SELECT balance FROM economy WHERE user_id = ?",
        (user_id,)
    )

    balance = cursor.fetchone()[0]

    if balance < amount:
        await interaction.response.send_message(
            "You don't have enough coins.",
            ephemeral=True
        )
        return
    won = random.choice([True, False])

    if won:
        cursor.execute(
            "UPDATE economy SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )

        conn.commit()

        await interaction.response.send_message(
            f"Coin landed on **HEADS**!\nYou won **{amount} coins**"
        )

    else:
        cursor.execute(
            "UPDATE economy SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )

        conn.commit()

        await interaction.response.send_message(
            f"Coin landed on **TAILS**!\nYou lost **{amount} coins**"
        )

@bot.tree.command(
    name="setwelcomechannel",
    description="Set welcome channel"
)
async def setwelcomechannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Administrator permission required.",
            ephemeral=True
        )
        return

    cursor.execute("""
        INSERT INTO welcome_config
        (guild_id, welcome_channel)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET welcome_channel = excluded.welcome_channel
    """, (interaction.guild.id, channel.id))

    conn.commit()

    await interaction.response.send_message(
        f"Welcome channel set to {channel.mention}"
    )

@bot.tree.command(
    name="setleavechannel",
    description="Set leave channel"
)
async def setleavechannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Administrator permission required.",
            ephemeral=True
        )
        return

    cursor.execute("""
        INSERT INTO welcome_config
        (guild_id, leave_channel)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET leave_channel = excluded.leave_channel
    """, (interaction.guild.id, channel.id))

    conn.commit()

    await interaction.response.send_message(
        f"Leave channel set to {channel.mention}"
    )


@bot.tree.command(
    name="setlevelreward",
    description="Set a role reward for a level"
)
@premium_only()
async def setlevelreward(
    interaction: discord.Interaction,
    level: int,
    role: discord.Role
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Administrator permission required.",
            ephemeral=True
        )
        return

    cursor.execute(
        """
        INSERT INTO level_rewards
        (guild_id, level, role_id)
        VALUES (?, ?, ?)
        """,
        (
            interaction.guild.id,
            level,
            role.id
        )
    )

    conn.commit()

    await interaction.response.send_message(
        f"Reward set:\nLevel **{level}** → {role.mention}"
    )
 

@bot.tree.command(name="license_add", description="Add premium license")
async def license_add(
    interaction: discord.Interaction,
    guild_id: str,
    days: int
):

    if interaction.user.id != YOUR_DISCORD_ID:
        await interaction.response.send_message(
            "Owner only.",
            ephemeral=True
        )
        return

    expires = int(time.time()) + (days * 86400)

    cursor.execute(
        """
        INSERT OR REPLACE INTO licenses
        (guild_id, plan, expires)
        VALUES (?, ?, ?)
        """,
        (int(guild_id), "premium", expires)
    )

    conn.commit()

    await interaction.response.send_message(
        f"Premium activated for guild `{guild_id}` for {days} days."
    )

@bot.tree.command(name="license_remove", description="Remove premium license")
async def license_remove(
    interaction: discord.Interaction,
    guild_id: str
):

    if interaction.user.id != YOUR_DISCORD_ID:
        await interaction.response.send_message(
            "Owner only.",
            ephemeral=True
        )
        return

    cursor.execute(
        "DELETE FROM licenses WHERE guild_id = ?",
        (int(guild_id),)
    )

    conn.commit()

    await interaction.response.send_message(
        f"License removed from guild `{guild_id}`."
    )

@bot.tree.command(name="license_info", description="Check server license")
async def license_info(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    cursor.execute(
        "SELECT plan, expires FROM licenses WHERE guild_id = ?",
        (guild_id,)
    )

    row = cursor.fetchone()

    if not row:
        await interaction.response.send_message(
            "This server has no active license."
        )
        return

    plan, expires = row

    if expires == 0:
        expires_text = "Lifetime"
    else:
        expires_text = f"<t:{int(expires)}:F>"

    embed = discord.Embed(
        title="Volt License",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Plan",
        value=plan,
        inline=False
    )

    embed.add_field(
        name="Expires",
        value=expires_text,
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Top richest users")
@premium_only()
async def leaderboard(interaction: discord.Interaction):

    await interaction.response.defer()

    cursor.execute("""
        SELECT user_id, balance
        FROM economy
        ORDER BY balance DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()

    if not rows:
        await interaction.followup.send("No data found.")
        return

    embed = discord.Embed(
        title="Economy Leaderboard",
        color=discord.Color.gold()
    )

    description = ""

    for i, (user_id, balance) in enumerate(rows, start=1):

        user = await bot.fetch_user(user_id)

        description += f"**{i}.** {user.name} — {balance:,}\n"

    embed.description = description

    embed.set_footer(text="Volt Economy System")

    await interaction.followup.send(embed=embed)


YOUR_DISCORD_ID = 1490030330084720892

@bot.tree.command(name="license_generate", description="Generate a new Premium license key (Admin Only)")
@app_commands.describe(days="How many days of Premium this key should grant")
async def license_generate(interaction: discord.Interaction, days: int):
    # 1. Zabezpieczenie: tylko Administrator serwera może generować klucze
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server administrators can generate keys.", ephemeral=True)
        return

    # Deferujemy odpowiedź, żeby bot spokojnie zapisał dane w bazie
    await interaction.response.defer(ephemeral=True)

    # 2. Generujemy unikalny klucz w formacie: VOLT-XXXX-XXXX-XXXX
    # secrets.token_hex(4) daje nam 8 losowych znaków (np. a1b2c3d4)
    key_part1 = secrets.token_hex(4).upper()
    key_part2 = secrets.token_hex(4).upper()
    key_part3 = secrets.token_hex(4).upper()
    generated_key = f"VOLT-{key_part1}-{key_part2}-{key_part3}"

    # 3. Zapisujemy wygenerowany klucz bezpośrednio do bazy volt.db
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        # Wrzucamy czysty klucz: is_used jest domyślnie 0, reszta kolumn pusta, dopóki ktoś go nie użyje
        cursor.execute(
            "INSERT INTO licenses (license_key, duration_days) VALUES (?, ?)",
            (generated_key, days)
        )
        conn.commit()

        # 4. Tworzymy ładną odpowiedź dla Ciebie w konsoli/Discordzie
        embed_key = discord.Embed(
            title="🔑 New License Key Generated",
            description="Keep this key secure. You can give it to a server owner to activate Premium.",
            color=0x00fff0 # Neonowy błękit VoltBota
        )
        embed_key.add_field(name="🎫 License Key", value=f"`{generated_key}`", inline=False)
        embed_key.add_field(name="⏳ Duration", value=f"`{days} Days`", inline=True)
        embed_key.add_field(name="🔒 Status", value="`Ready to redeem`", inline=True)
        embed_key.set_footer(text="VoltBot License System")

        await interaction.followup.send(embed=embed_key, ephemeral=True)

    except sqlite3.IntegrityError:
        # Bardzo mała szansa, ale jeśli klucz by się powtórzył w bazie:
        await interaction.followup.send("⚠️ Key collision detected. Please try running the command again.", ephemeral=True)
    except Exception as e:
        print(f"❌ [GENERATE ERROR] {e}")
        await interaction.followup.send(f"❌ Database error while generating key: `{e}`", ephemeral=True)
    finally:
        conn.close()
        
@bot.tree.command(name="license_redeem", description="Activate your subscription key for this server")
@app_commands.describe(key="Your license key (VOLT-XXXX-XXXX-XXXX)")
async def license_redeem(interaction: discord.Interaction, key: str):
    # Deferujemy odpowiedź, żeby bot miał czas na operacje na bazie i nie dostał timeoutu
    await interaction.response.defer(ephemeral=True)

    # Bezpieczeństwo: Sprawdzamy czy komenda nie jest wpisana w wiadomości prywatnej (DM)
    if not interaction.guild_id:
        await interaction.followup.send("❌ You can only redeem keys inside a server.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id) # Zapisujemy ID tego serwera jako tekst
    clean_key = key.strip()

    # Absolutna ścieżka do bazy danych volt.db
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        # 1. Sprawdzamy czy klucz w ogóle istnieje w bazie danych
        cursor.execute(
            "SELECT id, duration_days, is_used FROM licenses WHERE license_key = ?",
            (clean_key,),
        )
        row = cursor.fetchone()

        if not row:
            await interaction.followup.send("❌ This license key does not exist.", ephemeral=True)
            return

        db_id, duration_days, is_used = row

        # 2. Sprawdzamy czy klucz nie został już wcześniej przez kogoś zużyty
        if is_used == 1:
            await interaction.followup.send("❌ This license key has already been used.", ephemeral=True)
            return

        # 3. Obliczamy dokładny timestamp wygaśnięcia licencji
        seconds_to_add = int(duration_days) * 24 * 60 * 60
        expiry_timestamp = int(time.time()) + seconds_to_add

        # 4. Zapisujemy aktywację – przypisujemy ID serwera do Twojej kolumny used_by_user_id
        cursor.execute(
            """
            UPDATE licenses 
            SET is_used = 1, used_by_user_id = ?, expires_at = ? 
            WHERE id = ?
        """,
            (guild_id, expiry_timestamp, db_id),
        )

        # Zatwierdzamy zmiany w bazie danych
        conn.commit()
        
        # 5. Tworzymy piękny, profesjonalny panel sukcesu dla użytkownika Premium
        embed_success = discord.Embed(
            title="👑 Volt Premium Activated Successfully!",
            description=(
                f"Thank you for your support! Automated systems have successfully "
                f"unlocked all premium features for **{interaction.guild.name}**."
            ),
            color=0x00fff0 # Twój flagowy neonowy błękit
        )
        embed_success.add_field(name="📅 Subscription Plan", value=f"`{duration_days} Days`", inline=True)
        embed_success.add_field(name="🔒 Server Protection", value="Enhanced 🟢", inline=True)
        embed_success.add_field(
            name="🚀 What next?", 
            value="All features (including `/ticket`) are now fully unlocked for everyone on this server!", 
            inline=False
        )
        embed_success.set_footer(
            text=f"VoltBot Premium • Setup Completed", 
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        # Wysyłamy ukrytą wiadomość z potwierdzeniem
        await interaction.followup.send(embed=embed_success, ephemeral=True)

    except Exception as e:
        # W razie jakiegokolwiek błędu, logujemy go w konsoli i informujemy admina
        print(f"❌ [LICENSE ERROR] Something went wrong: {e}")
        await interaction.followup.send(f"❌ Database error during activation: `{e}`", ephemeral=True)

    finally:
        # Zawsze zamykamy połączenie, żeby nie zablokować pliku bazy .db
        conn.close()
        
@bot.tree.command(name="license_check", description="Check your subscription status")
async def license_check(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    expiration_date = database.check_user_license(user_id)
    
    if expiration_date:
        await interaction.response.send_message(
            f"**Your premium subscription is active!**\n📅 **Expires on:** `{expiration_date}` UTC", 
            ephemeral=True
        )
    else:
        # Informacja dla kogoś, kto nie aktywował żadnego klucza
        await interaction.response.send_message(
            "You do not have an active subscription.", 
            ephemeral=True
        )

def main():
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("www:app", host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
    
print(f"[DEBUG] Sprawdzanie komend przed startem:")
print(f"[DEBUG] Liczba komend w tree: {len(bot.tree.get_commands())}")
for cmd in bot.tree.get_commands():
    print(f"[DEBUG] Znaleziono komendę: {cmd.name}")

@bot.tree.command(
    name="debug_premium",
    description="DEVELOPER ONLY: Find out exactly why premium is not working",
)
async def debug_premium(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_id = interaction.user.id
    current_time = int(time.time())

    # 1. Szukamy wszystkich plików .db w folderze projektu, żeby sprawdzić czy nie ma duplikatów
    db_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".db"):
                full_path = os.path.join(root, file)
                db_files.append(full_path)

    report = f"**Znalezione pliki baz danych na dysku:** {db_files}\n\n"

    # 2. Przeszukujemy każdy znaleziony plik w poszukiwaniu Twojego ID
    report += f"**Szukam ID użytkownika:** `{user_id}` (jako liczba i jako tekst)\n\n"

    for db_path in db_files:
        report += f"**Analizuję plik:** `{db_path}`\n"
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Pobieramy listy tabel w tym konkretnym pliku
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            report += f"  ↳ Tabele w tym pliku: {tables}\n"

            for table in tables:
                # Sprawdzamy strukturę tabeli
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]

                if "user_id" in columns:
                    # Szukamy wpisu dla Twojego ID
                    cursor.execute(
                        f"SELECT * FROM {table} WHERE user_id = ? OR user_id = ?",
                        (int(user_id), str(user_id)),
                    )
                    row = cursor.fetchone()

                    if row:
                        report += f"  **Znalazłem wpis w tabeli `{table}`!**\n"
                        report += f"  ↳ Dane w bazie: `{row}`\n"
                        # Szukamy kolumny z czasem wygaśnięcia (zazwyczaj druga kolumna)
                        try:
                            expiry = int(row[1])
                            report += f"  ↳ Czas wygaśnięcia (Unix): `{expiry}`\n"
                            if expiry > current_time:
                                report += "  ↳ STATUS: Ważne (Powinno działać!)\n"
                            else:
                                report += f"  ↳ STATUS: Wygasło (Różnica: {current_time - expiry} sekund temu)\n"
                        except:
                            report += "  ↳ STATUS: Nie mogłem odczytać czasu wygaśnięcia.\n"
                    else:
                        report += f"  🔸 Brak wpisu dla Twojego ID w tabeli `{table}`.\n"

            conn.close()
        except Exception as e:
            report += f"  Błąd odczytu pliku: {str(e)}\n"
        report += "\n"

    report += f"**Aktualny czas bota (Unix):** `{current_time}`"

    # Jeśli raport jest za długi, dzielimy go na części
    if len(report) > 2000:
        report = report[:1950] + "\n... (obcięto zbyt długi raport)"

    await interaction.followup.send(report, ephemeral=True)

@bot.tree.command(name="dump_licenses", description="DEVELOPER ONLY: See raw data inside licenses table")
async def dump_licenses(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    
    try:
        # Pobieramy nazwy kolumn w tabeli licenses
        cursor.execute("PRAGMA table_info(licenses)")
        columns = [f"{col[1]} ({col[2]})" for col in cursor.fetchall()]
        col_text = ", ".join(columns)
        
        # Pobieramy 5 ostatnich rekordów
        cursor.execute("SELECT * FROM licenses LIMIT 5")
        rows = cursor.fetchall()
        
        report = f"📋 **Struktura tabeli `licenses` (Kolumny):**\n`[{col_text}]`\n\n"
        report += "📊 **Ostatnie wpisy w tej tabeli:**\n"
        
        if rows:
            for row in rows:
                report += f"🔹 `{row}`\n"
        else:
            report += "🔸 Tabela `licenses` jest całkowicie pusta!\n"
            
    except Exception as e:
        report = f"Błąd podczas sprawdzania tabeli `licenses`: {str(e)}"
        
    conn.close()
    await interaction.followup.send(report, ephemeral=True)

user_last_vote = {}


# --- KOMENDA /VOTE ---
@bot.tree.command(
    name="vote",
    description="Vote for VoltBot on Top.gg and claim your 500 coins reward!",
)
async def vote(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.datetime.utcnow()
    cooldown_time = datetime.timedelta(hours=12)

    if user_id in user_last_vote:
        last_vote_time = user_last_vote[user_id]
        if now - last_vote_time < cooldown_time:
            time_left = cooldown_time - (now - last_vote_time)
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)

            embed_cooldown = discord.Embed(
                title="⏳ Vote Cooldown",
                description=f"You have already claimed your voting reward! You can vote again in **{hours}h {minutes}m**.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(
                embed=embed_cooldown, ephemeral=True
            )
            return

    topgg_url = f"https://top.gg/bot/{bot.user.id}/vote"

    view = discord.ui.View()
    button = discord.ui.Button(
        label="Click Here to Vote!",
        url=topgg_url,
        style=discord.ButtonStyle.link,
        emoji="🚀",
    )
    view.add_item(button)

    reward_amount = 500
    # TUTAJ DOPISZ SWOJĄ FUNKCJĘ DODAJĄCĄ MONETY DO BAZY DANYCH, np:
    # await add_money(user_id, reward_amount)

    # 5. Zapisanie aktualnego czasu głosowania
    user_last_vote[user_id] = now

    # 6. Wysłanie eleganckiego Embedu z przyciskiem do kliknięcia
    embed_vote = discord.Embed(
        title="⚡ Support VoltBot!",
        description=(
            f"Thank you for supporting **VoltBot**!\n\n"
            f"💰 **+{reward_amount} coins** have been added to your balance.\n"
            f"Please make sure to actually click the button below and submit your vote on Top.gg!"
        ),
        color=discord.Color.purple(),
    )
    embed_vote.set_thumbnail(url=interaction.user.display_avatar.url)
    embed_vote.set_footer(text="You can claim this reward every 12 hours.")

    await interaction.response.send_message(embed=embed_vote, view=view)
