from email import message
from collections import defaultdict
import time
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import uvicorn
from datetime import timedelta
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
import sqlite3

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
        # 1. Tu wywołujemy inicjalizację bazy – to zadziała na 100%
        init_db() 
        
        # 2. Synchronizacja komend
        synced = await self.tree.sync()
        print(f"[✅] Zsynchronizowano {len(synced)} komend!")
        print(f"[✅] Baza danych zainicjalizowana.")

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
    print("DEBUG: Rozpoczynam inicjalizację bazy...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Licencje (Premium)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            duration_days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by_user_id TEXT,
            expires_at INTEGER
        )
    """)
    conn.commit()
    print("DEBUG: Tabela licenses powinna być gotowa.")

    # 2. Ekonomia
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS economy (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0
        )
    """)

    # 3. Poziomy (Leveling) - TO JEST DLA CIEBIE KLUCZOWE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_message REAL DEFAULT 0
        )
    """)

    # 4. Ostrzeżenia
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp INTEGER
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ [DATABASE] Wszystkie tabele (w tym levels) zostały poprawnie sprawdzone/utworzone!")

def check_premium_db(guild_id: int) -> bool:
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    current_time = int(time.time())
    
    # Szukamy serwera w tabeli 'licenses'
    # Pamiętaj: w 'licenses' masz kolumnę 'used_by_user_id' jako TEXT
    cursor.execute("SELECT expires_at FROM licenses WHERE used_by_user_id = ? AND is_used = 1", (str(guild_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] is not None:
        if int(row[0]) > current_time:
            return True
    return False
    
async def redeem_key_logic(guild_id: int, input_key: str):
    # 1. Szukamy klucza w kolekcji 'licenses'
    # .find_one szuka dokumentu spełniającego warunek
    license = await db.licenses.find_one({"license_key": input_key.strip()})
    
    # Sprawdzamy czy istnieje i czy 'is_used' nie jest równe 1
    if not license or license.get("is_used") == 1:
        return {"status": "invalid"}
        
    days_to_add = license.get("duration_days", 0)
    expiry_timestamp = int(time.time()) + (days_to_add * 24 * 60 * 60)
    
    # 2. Aktualizujemy rekord
    # find_one_and_update to bardzo potężna funkcja w MongoDB
    await db.licenses.find_one_and_update(
        {"_id": license["_id"]}, # Znajdź po unikalnym ID dokumentu
        {"$set": {
            "is_used": 1,
            "used_by_user_id": str(guild_id),
            "expires_at": expiry_timestamp
        }}
    )
    
    return {"status": "success", "days": days_to_add}

def is_premium(guild_id: int) -> bool:
    return check_premium_db(guild_id)
    
app = FastAPI()

def premium_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("❌ DM is not supported.", ephemeral=True)
            return False

        # Wymuszamy użycie funkcji, która czyta bazę
        has_premium = check_premium_db(guild_id) 
        
        print(f"DEBUG: Checking premium for guild {guild_id}, result: {has_premium}")
        
        if not has_premium:
            await interaction.response.send_message(
                "❌ **This feature requires Volt Premium!**\n"
                "Use `/license_redeem` to activate.",
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
    
@bot.tree.command(name="help", description="Show all available VoltBot commands and features")
async def help(interaction: discord.Interaction):
    
    # Tworzymy piękny embed pasujący do Twojej neonowej strony www
    embed = discord.Embed(
        title="⚡ VoltBot – Command Directory",
        description=(
            "Welcome to the official help menu. Use the commands below to manage, "
            "engage, and level up your Discord server!\n\n"
            "🔗 *Need Premium? Check out our pricing page!*"
        ),
        color=0x00ffcc # Twój jaskrawy, neonowy błękit/zieleń
    )

    # 1. MODERATION
    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`/warn` • Issue a formal warning to a user\n"
            "`/warnings` • View a user's active warnings\n"
            "`/kick` • Kick a member from the server\n"
            "`/ban` • Permanently ban a member\n"
            "`/timeout` • Temporarily mute/timeout a member"
        ),
        inline=False
    )

    # 2. ECONOMY
    embed.add_field(
        name="💰 Economy & Fun",
        value=(
            "`/balance` • Check your current wallet and bank balance\n"
            "`/work` • Shift work to earn steady cash\n"
            "`/daily` • Claim your free daily coin allowance\n"
            "`/pay` • Transfer coins securely to another user\n"
            "`/leaderboard` • See who dominates the local economy\n"
            "`/coinflip` • Gamble your coins on a 50/50 flip"
        ),
        inline=False
    )

    # 3. LEVELS & CONFIG
    embed.add_field(
        name="📈 Levels & System Config",
        value=(
            "`/rank` • Display your current level status card\n"
            "`/stats` • Detailed XP and leveling breakdown\n"
        ),
        inline=False
    )

    # 4. TICKETS
    embed.add_field(
        name="🎟️ Support Tickets",
        value=(
            "`/ticket` • Open a new dedicated support channel\n"
            "`/close` • Securely close and archive an active ticket"
        ),
        inline=False
    )

    # 5. UTILITY
    embed.add_field(
        name="⚙️ Utility",
        value=(
            "`/help` • Open this command directory interface\n"
            "`/ping` • Test the bot's current API latency\n"
            "`/serverinfo` • Fetch comprehensive server statistics\n"
            "`/userinfo` • Display detailed information about a member"
        ),
        inline=False
    )

    # Profesjonalna stopka z awatarem bota (jeśli dostępny)
    bot_avatar = bot.user.display_avatar.url if bot.user else None
    embed.set_footer(
        text=f"Volt Utilities • Serving {interaction.guild.name}", 
        icon_url=bot_avatar
    )

    # Wysyłamy menu pomocnicze jako odpowiedź
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

@bot.tree.command(name="warnings", description="View the warning history of a specific member")
@app_commands.describe(user="The member whose warnings you want to check")
async def warnings_cmd(interaction: discord.Interaction, user: discord.Member):
    # Deferujemy odpowiedź, bo odpytujemy bazę danych
    await interaction.response.defer(ephemeral=False)

    # Zabezpieczenie przed użyciem w wiadomości prywatnej (DM)
    if not interaction.guild_id:
        await interaction.followup.send("❌ This command can only be used inside a server.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Pobieramy ID ostrzeżenia oraz powód, filtrując TYLKO po obecnym serwerze i użytkowniku
        cursor.execute(
            "SELECT id, reason FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id ASC",
            (guild_id, str(user.id))
        )
        rows = cursor.fetchall()

        # Jeśli lista jest pusta – użytkownik jest czysty
        if not rows:
            embed_clean = discord.Embed(
                title="🛡️ Warning History",
                description=f"{user.mention} (`{user.id}`) has a **completely clean record** on this server. No warnings found.",
                color=discord.Color.green()
            )
            embed_clean.set_thumbnail(url=user.display_avatar.url)
            embed_clean.set_footer(text="VoltBot Moderation Suite")
            await interaction.followup.send(embed=embed_clean)
            return

        # Budujemy przejrzystą listę warnów do Embedu
        # rows zawiera krotki: (id, reason), np. (1, "Spamming chat")
        warning_list = []
        for row in rows:
            warn_id, reason = row
            warning_list.append(f"**Case #{warn_id}** — {reason}")

        # Łączymy wpisy w jeden czytelny blok tekstu
        full_text = "\n".join(warning_list)

        # Tworzymy elegancki panel z historią kar
        embed_warnings = discord.Embed(
            title=f"⚠️ Warnings for {user.name}",
            description=f"Total active infractions: `{len(rows)}`",
            color=discord.Color.orange()
        )
        embed_warnings.add_field(name="History", value=full_text, inline=False)
        embed_warnings.set_thumbnail(url=user.display_avatar.url)
        embed_warnings.set_footer(text=f"Requested by {interaction.user.name} • VoltBot Mod")

        await interaction.followup.send(embed=embed_warnings)

    except Exception as e:
        print(f"❌ [WARNINGS CMD ERROR] {e}")
        await interaction.followup.send(f"❌ Database error while fetching history: `{e}`", ephemeral=True)
        
    finally:
        # Zawsze bezpiecznie zamykamy bazę danych
        conn.close()
        
@bot.tree.command(name="serverinfo", description="Display comprehensive information and statistics about this server")
async def serverinfo(interaction: discord.Interaction):
    # Deferujemy, bo zliczanie kanałów i przetwarzanie ikon może zająć ułamek sekundy
    await interaction.response.defer(ephemeral=False)

    guild = interaction.guild
    if not guild:
        await interaction.followup.send("❌ This command can only be used inside a server.", ephemeral=True)
        return

    # 1. Dokładne zliczanie typów kanałów
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    stage_channels = len(guild.stage_channels)
    
    # 2. Bezpieczne wyciąganie właściciela serwera
    owner_mention = f"<@{guild.owner_id}>" if guild.owner_id else "Unknown"

    # 3. Przygotowanie timestampu Discorda dla daty stworzenia serwera
    created_timestamp = int(guild.created_at.timestamp())
    discord_time_full = f"<t:{created_timestamp}:F>"      # Pełna data
    discord_time_relative = f"<t:{created_timestamp}:R>"  # Np. "3 lata temu"

    # 4. Budowanie profesjonalnego Embedu w stylu Volt Premium
    embed = discord.Embed(
        title=f"📊 {guild.name} — Server Overview",
        color=0x00fff0 # Twój neonowy błękit VoltBota
    )

    # Informacje główne
    embed.add_field(name="👑 Owner", value=owner_mention, inline=True)
    embed.add_field(name="🆔 Server ID", value=f"`{guild.id}`", inline=True)
    embed.add_field(name="📆 Created On", value=f"{discord_time_full}\n({discord_time_relative})", inline=False)

    # Statystyki użytkowników i ról
    embed.add_field(name="👥 Total Members", value=f"`{guild.member_count}` members", inline=True)
    embed.add_field(name="🛡️ Roles", value=f"`{len(guild.roles)}` roles", inline=True)
    
    # Statystyki ulepszeń (Boostów)
    boost_count = guild.premium_subscription_count
    boost_level = guild.premium_tier
    embed.add_field(name="🚀 Server Boosts", value=f"Level `{boost_level}` (`{boost_count}` Boosts)", inline=True)

    # Szczegółowe zestawienie kanałów
    channels_structure = (
        f"📁 Categories: `{categories}`\n"
        f"💬 Text: `{text_channels}`\n"
        f"🔊 Voice: `{voice_channels}`"
    )
    if stage_channels > 0:
        channels_structure += f"\n🎭 Stage: `{stage_channels}`"

    embed.add_field(name="📊 Channel Directory", value=channels_structure, inline=False)

    # Dodawanie ikony serwera jako miniaturki (Thumbnail) i baneru (jeśli istnieje)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    if guild.banner:
        embed.set_image(url=guild.banner.url)

    embed.set_footer(text=f"VoltBot Utility Suite • Data current", icon_url=bot.user.display_avatar.url)

    await interaction.followup.send(embed=embed)
    
@bot.tree.command(name="userinfo", description="Display detailed profile statistics and account age of a member")
@app_commands.describe(user="Select the member to inspect (Leave blank to inspect yourself)")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    # Deferujemy odpowiedź, żeby bot na spokojnie przetworzył awatary i daty
    await interaction.response.defer(ephemeral=False)

    # Jeśli użytkownik nie wybrał nikogo, bot sprawdza osobę wpisującą komendę
    target_user = user or interaction.user

    # 1. Konwersja dat na timestampy Discorda
    created_timestamp = int(target_user.created_at.timestamp())
    joined_timestamp = int(target_user.joined_at.timestamp()) if target_user.joined_at else None

    # Tagi czasowe dla założenia konta
    account_created_full = f"<t:{created_timestamp}:F>"
    account_created_relative = f"<t:{created_timestamp}:R>"

    # Tagi czasowe dla dołączenia na serwer
    if joined_timestamp:
        server_joined_full = f"<t:{joined_timestamp}:F>\n({f'<t:{joined_timestamp}:R>'})"
    else:
        server_joined_full = "`Unknown`"

    # 2. Budowanie nowoczesnego Embedu profilu
    embed = discord.Embed(
        title=f"👤 User Profile — {target_user.name}",
        color=0x00fff0 # Twój neonowy błękit VoltBota
    )
    
    # Podstawowe ID oraz typ konta poukładane w kolumnach
    embed.add_field(name="🆔 User ID", value=f"`{target_user.id}`", inline=True)
    embed.add_field(name="🤖 Bot Account", value="`Yes 🟣`" if target_user.bot else "`No 👤`", inline=True)
    embed.add_field(name="🎭 Highest Role", value=target_user.top_role.mention, inline=False)

    # Sekcja dat (amerykański standard modowy)
    embed.add_field(
        name="📆 Account Created", 
        value=f"{account_created_full}\n({account_created_relative})", 
        inline=False
    )
    embed.add_field(
        name="🚪 Joined Server", 
        value=server_joined_full, 
        inline=False
    )

    # Ustawiamy awatar użytkownika jako główną miniaturkę
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    # Dodatkowa estetyka: jeśli użytkownik ma ustawiony baner profilu, bot może go zaciągnąć (wymaga wyższych uprawnień/fetch)
    embed.set_footer(
        text=f"Requested by {interaction.user.name} • VoltBot Lookup", 
        icon_url=interaction.user.display_avatar.url
    )

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="timeout", description="Mute/Timeout a member to restrict them from typing or joining voice channels")
@app_commands.describe(
    user="The member to timeout",
    minutes="Duration of the timeout in minutes",
    reason="The reason for the timeout"
)
async def timeout(
    interaction: discord.Interaction, 
    user: discord.Member, 
    minutes: int, 
    reason: str = "No reason provided"
):
    # 1. Sprawdzenie uprawnień moderatora
    if not interaction.user.guild_permissions.moderate_members:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Timeout Members** (`moderate_members`) permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # 2. Zabezpieczenie przed timeoutowaniem botów
    if user.bot:
        await interaction.response.send_message("⚠️ You cannot timeout bot accounts.", ephemeral=True)
        return

    # 3. Zabezpieczenie przed nałożeniem kary na samego siebie
    if user.id == interaction.user.id:
        await interaction.response.send_message("⚠️ You cannot timeout yourself!", ephemeral=True)
        return

    # 4. Sprawdzenie hierarchii ról (Zabezpieczenie przed wyciszaniem wyższych rangą)
    if interaction.user.top_role <= user.top_role and interaction.guild.owner_id != interaction.user.id:
        embed_hierarchy = discord.Embed(
            title="⚠️ Hierarchy Error",
            description="You cannot timeout this member because they have an equal or higher role than you.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed_hierarchy, ephemeral=True)
        return

    # Deferujemy odpowiedź, bo operacja wysyłania żądania do Discord API może chwilę zająć
    await interaction.response.defer(ephemeral=False)

    try:
        # 5. Nakładamy timeout za pomocą timedelta (Wymaga: from datetime import timedelta)
        duration = timedelta(minutes=minutes)
        await user.timeout(duration, reason=reason)

        # 6. Obliczamy, kiedy dokładnie kara dobiegnie końca, do dynamicznego timestampu
        # datetime.utcnow() jest przestarzałe w nowszych Pythonach, używamy timestampu z time.time()
        import time
        unmute_timestamp = int(time.time()) + (minutes * 60)
        discord_time_relative = f"<t:{unmute_timestamp}:R>" # Np. "za 30 minut"
        discord_time_full = f"<t:{unmute_timestamp}:F>"     # Dokładna data i godzina

        # 7. Budujemy profesjonalny log modowski w Embedzie
        embed_success = discord.Embed(
            title="🤫 Member Timouted",
            description=f"{user.mention} has been successfully isolated.",
            color=discord.Color.red()
        )
        embed_success.add_field(name="👤 Target", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed_success.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
        embed_success.add_field(name="⏳ Duration", value=f"`{minutes} Minute(s)`", inline=False)
        embed_success.add_field(name="🔓 Unmute Time", value=f"{discord_time_full} ({discord_time_relative})", inline=False)
        embed_success.add_field(name="📝 Reason", value=reason, inline=False)
        embed_success.set_thumbnail(url=user.display_avatar.url)
        embed_success.set_footer(text="VoltBot Moderation Core", icon_url=bot.user.display_avatar.url)

        await interaction.followup.send(embed=embed_success)

    except discord.Forbidden:
        # Wywoła się, gdy bot ma w hierarchii ról na serwerze niższą rolę niż cel, lub brak uprawnień administracyjnych
        embed_forbidden = discord.Embed(
            title="❌ Action Failed",
            description=(
                f"I cannot timeout {user.mention}.\n"
                f"Make sure my **VoltBot** role is placed **higher** than their highest role in the Server Settings."
            ),
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed_forbidden, ephemeral=True)
        
    except Exception as e:
        print(f"❌ [TIMEOUT ERROR] {e}")
        await interaction.followup.send(f"❌ An unexpected error occurred: `{e}`", ephemeral=True)

def get_user_balance_and_rank(user_id: int) -> tuple[int, int]:
    """Zwraca krotkę (stan_konta, pozycja_w_rankingu) dla danego użytkownika."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # 1. Pobieramy stan konta
        cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        balance = row[0] if row else 0
        
        # Jeśli użytkownika nie ma jeszcze w bazie, opcjonalnie możesz go tu dodać,
        # ale na razie zwracamy po prostu 0, a pozycja w rankingu policzy się automatycznie.
        
        # 2. Obliczamy pozycję w rankingu (Twój świetny patent!)
        cursor.execute("SELECT COUNT(*) + 1 FROM economy WHERE balance > ?", (balance,))
        rank = cursor.fetchone()[0]
        
        return balance, rank
    finally:
        conn.close()

def get_user_balance_and_rank(user_id: int) -> tuple[int, int]:
    """Pobiera stan konta użytkownika oraz oblicza jego pozycję w globalnym rankingu bogactwa."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # 1. Upewniamy się, że użytkownik istnieje w bazie (żeby nie było błędu pustego rekordu)
        cursor.execute("INSERT OR IGNORE INTO economy (user_id, balance, last_daily, streak) VALUES (?, 0, 0, 0)", (user_id,))
        conn.commit()
        
        # 2. Pobieramy stan konta użytkownika
        cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        
        # 3. Obliczamy pozycję w rankingu (liczymy ile osób ma WIĘCEJ monet niż nasz użytkownik)
        cursor.execute("SELECT COUNT(*) FROM economy WHERE balance > ?", (balance,))
        rank = cursor.fetchone()[0] + 1  # +1 oznacza, że jeśli 0 osób ma więcej, zajmuje 1. miejsce
        
        return balance, rank
        
    except Exception as e:
        print(f"🔴 [DB BALANCE ERROR]: {e}")
        return 0, 999  # W razie błędu zwracamy bezpieczne wartości domyślne
    finally:
        conn.close()

@bot.tree.command(name="balance", description="Check your current coin balance and leaderboard standings")
@premium_only() # Komenda zabezpieczona Twoim nowym dekoratorem Premium!
@app_commands.describe(user="Select a member to check their balance (Leave blank to check your own)")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    # Deferujemy odpowiedź, ponieważ operacje na pliku bazy danych mogą zająć chwilę
    await interaction.response.defer(ephemeral=False)

    # Jeśli parametr 'user' jest pusty, sprawdzamy osobę, która wywołała komendę
    target_user = user or interaction.user

    try:
        # Wywołujemy bezpiecznie funkcję bazodanową w osobnym wątku, żeby nie zamrażać bota
        balance_amount, leaderboard_rank = await asyncio.to_thread(
            get_user_balance_and_rank, target_user.id
        )

        # Budujemy nowoczesny, złoty Embed w stylu Volt Economy
        embed = discord.Embed(
            title=f"💰 {target_user.name}'s Wallet",
            color=discord.Color.gold()
        )
        
        # Jeśli sprawdzamy bota, dodajemy mały smaczek (boty zazwyczaj nie mają kasy)
        if target_user.bot:
            embed.description = "🤖 *Bots carry digital wallets, but they are usually empty...*"

        # Poukładane dane w czytelne kolumny
        embed.add_field(
            name="💵 Balance", 
            value=f"**{balance_amount:,}** Volt Coins", # Formatowanie 1,000,000 działa automatycznie
            inline=True
        )
        embed.add_field(
            name="🏆 Global Rank", 
            value=f"**#{leaderboard_rank}**", 
            inline=True
        )
        
        # Ustawiamy awatar sprawdzanego użytkownika jako miniaturkę
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Ładne stopki z ikonką wykonawcy komendy
        embed.set_footer(
            text=f"Requested by {interaction.user.name} • Volt Economy", 
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"❌ [BALANCE CMD ERROR] {e}")
        await interaction.followup.send(
            f"❌ An error occurred while fetching the wallet data: `{e}`", 
            ephemeral=True
        )

def process_daily_reward(user_id: int, custom_reward: int) -> tuple[str, dict]:
    """Przetwarza nagrodę daily i zwraca status ('cooldown', 'success', 'error') oraz dane."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    now = int(time.time())
    cooldown = 86400  # 24 godziny
    
    try:
        cursor.execute("SELECT balance, last_daily, streak FROM economy WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            balance, last_daily, streak = row
            
            # 1. Sprawdzenie czasu oczekiwania
            if last_daily and (now - last_daily) < cooldown:
                unlocked_at = last_daily + cooldown
                return "cooldown", {"unlocked_at": unlocked_at}
            
            # 2. Sprawdzenie zachowania streaku (czy minęło mniej niż 48h od ostatniego odebrania)
            if last_daily and (now - last_daily) <= (cooldown * 2):
                streak += 1
            else:
                streak = 1
                
            new_balance = balance + custom_reward
            cursor.execute(
                "UPDATE economy SET balance = ?, last_daily = ?, streak = ? WHERE user_id = ?",
                (new_balance, now, streak, user_id)
            )
        else:
            # Nowy gracz w bazie
            streak = 1
            new_balance = custom_reward
            cursor.execute(
                "INSERT INTO economy (user_id, balance, last_daily, streak) VALUES (?, ?, ?, ?)",
                (user_id, new_balance, now, streak)
            )
            
        conn.commit()
        return "success", {"reward": custom_reward, "balance": new_balance, "streak": streak}
        
    except Exception as e:
        print(f"🔴 [DB DAILY ERROR]: {e}")
        return "error", {"error_msg": str(e)}
    finally:
        conn.close()


# --- KOMENDA SLASH /DAILY ---
@bot.tree.command(name="daily", description="Claim your daily allowance of Volt Coins")
@premium_only()
async def daily(interaction: discord.Interaction):
    # Informujemy Discord, że przetwarzamy dane
    await interaction.response.defer(ephemeral=False)
    
    user_id = interaction.user.id
    custom_reward = 100  # Podstawowa nagroda finansowa
    
    # Odpalamy całą logikę bazy danych w osobnym bezpiecznym wątku
    status, data = await asyncio.to_thread(process_daily_reward, user_id, custom_reward)
    
    if status == "cooldown":
        unlocked_timestamp = data["unlocked_at"]
        embed_cooldown = discord.Embed(
            title="⏳ Reward Locked",
            description=(
                f"You have already claimed your daily reward today!\n"
                f"Your next allowance is available **<t:{unlocked_timestamp}:R>** (at <t:{unlocked_timestamp}:t>)."
            ),
            color=discord.Color.red()
        )
        embed_cooldown.set_footer(text="VoltBot Economy Module")
        await interaction.followup.send(embed=embed_cooldown, ephemeral=True)
        return
        
    elif status == "error":
        await interaction.followup.send(
            f"❌ An error occurred while accessing the vault: `{data['error_msg']}`", 
            ephemeral=True
        )
        return
        
    # Status: Success - Generujemy piękny panel nagrody
    streak = data["streak"]
    reward = data["reward"]
    new_balance = data["balance"]
    
    # Mały bonus wizualny: co każde 5 dni streaku dodajemy ognistą animację w tekście
    streak_display = f"`{streak} Day(s)`" + (" 🔥" if streak >= 5 else " ⚡")

    embed_success = discord.Embed(
        title="🎁 Daily Reward Claimed!",
        description=f"You successfully collected your daily stimulus package.",
        color=discord.Color.green()
    )
    embed_success.add_field(name="💰 Added", value=f"**+{reward}** Volt Coins", inline=True)
    embed_success.add_field(name="📈 Streak", value=streak_display, inline=True)
    embed_success.add_field(name="💳 Total Net Worth", value=f"**{new_balance:,}** coins", inline=False)
    
    embed_success.set_thumbnail(url=interaction.user.display_avatar.url)
    embed_success.set_footer(
        text=f"Claimed by {interaction.user.name} • Come back tomorrow!", 
        icon_url=interaction.user.display_avatar.url
    )
    
    await interaction.followup.send(embed=embed_success)
    
# --- POMOCNICZA FUNKCJA BAZODANOWA DLA /WORK (Bezpieczna praca) ---
def process_work_job(user_id: int, jobs: list[str]) -> tuple[str, dict]:
    """Przetwarza czas pracy użytkownika w tle. Zapobiega lagom i blokowaniu bazy."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    now = int(time.time())
    cooldown = 3600  # 1 godzina
    
    try:
        # Zabezpieczenie: Tworzymy profil ekonomii, jeśli nie istnieje
        cursor.execute("INSERT OR IGNORE INTO economy (user_id, balance, last_daily, streak) VALUES (?, 0, 0, 0)", (user_id,))
        
        cursor.execute("SELECT balance, last_work FROM economy WHERE user_id = ?", (user_id,))
        balance, last_work = cursor.fetchone()
        
        # Sprawdzamy cooldown
        if last_work and (now - last_work) < cooldown:
            return "cooldown", {"last_work": last_work, "now": now, "cooldown": cooldown}
            
        # Losujemy pracę i nagrodę
        job = random.choice(jobs)
        reward = random.randint(100, 500)
        new_balance = balance + reward
        
        cursor.execute("UPDATE economy SET balance = ?, last_work = ? WHERE user_id = ?", (new_balance, now, user_id))
        conn.commit()
        
        return "success", {"job": job, "reward": reward, "balance": new_balance}
        
    except Exception as e:
        print(f"🔴 [DB WORK ERROR]: {e}")
        return "error", {"error_msg": str(e)}
    finally:
        conn.close()

@bot.tree.command(name="work", description="Earn coins by working shifts")
@premium_only()
async def work(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    user_id = interaction.user.id
    jobs = [
        "🍔 Worked a shift at McDonald's",
        "🚚 Delivered express packages",
        "👨‍🍳 Cooked a premium dish in a restaurant",
        "💻 Fixed a complex computer bug",
        "🧹 Cleaned high-end offices",
        "📦 Sorted cargo in a warehouse"
    ]
    
    status, data = await asyncio.to_thread(process_work_job, user_id, jobs)
    
    if status == "cooldown":
        last_work = data["last_work"]
        now = data["now"]
        cooldown = data["cooldown"]
        
        elapsed = now - last_work
        remaining = cooldown - elapsed
        percent = int((elapsed / cooldown) * 100)
        
        # Pasek postępu (zakładam, że masz już funkcję progress_bar zdefiniowaną w pliku)
        bar = progress_bar(elapsed, cooldown, 10) if 'progress_bar' in globals() else "░" * 10
        
        minutes = remaining // 60
        seconds = remaining % 60
        
        embed_tired = discord.Embed(
            title="⏳ You are exhausted!",
            description="Your body needs rest before taking another shift.",
            color=discord.Color.red()
        )
        embed_tired.add_field(name="Cooldown Progress", value=f"{bar} **{percent}%**", inline=False)
        embed_tired.add_field(name="Time Left", value=f"⏱️ **{minutes}m {seconds}s**", inline=False)
        embed_tired.set_footer(text="VoltBot Economy Module")
        
        await interaction.followup.send(embed=embed_tired)
        return
        
    elif status == "error":
        await interaction.followup.send(f"❌ Shift manager error: `{data['error_msg']}`", ephemeral=True)
        return
        
    # Sukces - wyświetlamy ładny panel wykonanej pracy
    embed_success = discord.Embed(
        title="💼 Shift Completed!",
        description=f"**{data['job']}**",
        color=discord.Color.green()
    )
    embed_success.add_field(name="💰 Earned", value=f"**+{data['reward']}** coins", inline=True)
    embed_success.add_field(name="💳 New Balance", value=f"**{data['balance']:,}** coins", inline=True)
    embed_success.set_thumbnail(url=interaction.user.display_avatar.url)
    embed_success.set_footer(text="Thank you for your hard work! Come back in an hour.")
    
    await interaction.followup.send(embed=embed_success)

def process_coin_transfer(sender_id: int, receiver_id: int, amount: int) -> tuple[str, str]:
    """Przetwarza przelew monet wewnątrz bezpiecznej transakcji."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        cursor.execute("INSERT OR IGNORE INTO economy (user_id, balance, last_daily, streak) VALUES (?, 0, 0, 0)", (sender_id,))
        cursor.execute("INSERT OR IGNORE INTO economy (user_id, balance, last_daily, streak) VALUES (?, 0, 0, 0)", (receiver_id,))
        
        cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (sender_id,))
        sender_balance = cursor.fetchone()[0]
        
        if sender_balance < amount:
            conn.rollback()
            return "insufficient_funds", "You do not have enough coins to complete this transfer."
            
        cursor.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
        cursor.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (amount, receiver_id))
        
        conn.commit()
        return "success", ""
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 [DB TRANSFER ERROR]: {e}")
        return "error", str(e)
        
    finally:
        conn.close() # <- Ta linia MUSI tu być, żeby zamknąć blok powyżej!

@bot.tree.command(name="pay", description="Transfer a specific amount of Volt Coins to another server member")
@premium_only()
@app_commands.describe(
    user="The member you want to send coins to",
    amount="The amount of coins to transfer"
)
async def pay(interaction: discord.Interaction, user: discord.Member, amount: int):
    # 1. Zabezpieczenie: Kwota musi być większa od zera
    if amount <= 0:
        await interaction.response.send_message("❌ The transfer amount must be greater than 0.", ephemeral=True)
        return

    # 2. Zabezpieczenie: Nie można przelać pieniędzy samemu sobie
    if user.id == interaction.user.id:
        await interaction.response.send_message("⚠️ You cannot send Volt Coins to yourself!", ephemeral=True)
        return

    # 3. Zabezpieczenie: Nie można przelewać monet botom
    if user.bot:
        await interaction.response.send_message("⚠️ Bot accounts cannot hold wallets or receive currency.", ephemeral=True)
        return

    # Informujemy Discord, że bot przetwarza transakcję bankową
    await interaction.response.defer(ephemeral=False)

    sender_id = interaction.user.id
    receiver_id = user.id

    # Uruchamiamy bezpieczny transfer w osobnym wątku systemowym
    status, error_msg = await asyncio.to_thread(process_coin_transfer, sender_id, receiver_id, amount)

    if status == "insufficient_funds":
        embed_poor = discord.Embed(
            title="❌ Transaction Declined",
            description=f"You do not have enough coins.\nRequired: **{amount:,}** coins.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed_poor, ephemeral=True)
        return
        
    elif status == "error":
        await interaction.followup.send(f"❌ Bank system error during transfer: `{error_msg}`", ephemeral=True)
        return

    # Status: Success - Budujemy piękny, zielony Embed udanej transakcji
    embed_success = discord.Embed(
        title="💸 Transfer Successful!",
        description=f"Funds have been securely moved between accounts.",
        color=discord.Color.green()
    )
    embed_success.add_field(name="📤 Sender", value=interaction.user.mention, inline=True)
    embed_success.add_field(name="📥 Receiver", value=user.mention, inline=True)
    embed_success.add_field(name="💰 Amount Transferred", value=f"**{amount:,}** Volt Coins", inline=False)
    
    # Ustawiamy awatar odbiorcy, żeby było widać do kogo poszła kasa
    embed_success.set_thumbnail(url=user.display_avatar.url)
    embed_success.set_footer(text="VoltBot Banking Protocol", icon_url=bot.user.display_avatar.url)

    await interaction.followup.send(embed=embed_success)

def get_detailed_user_stats(user_id: int) -> tuple[int, int, int]:
    """Zwraca (balance, streak, last_daily) dla danego użytkownika."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # Zaciągamy od razu komplet danych ekonomicznych
        cursor.execute("SELECT balance, streak, last_daily FROM economy WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            return row[0], row[1], row[2]
        return 0, 0, 0 # Jeśli użytkownika nie ma w bazie, zwracamy same zera
    finally:
        conn.close()

@bot.tree.command(name="stats", description="View comprehensive economic profile and stats for a member")
@app_commands.describe(user="Select a member to view stats (Leave blank to view your own)")
async def stats(interaction: discord.Interaction, user: discord.Member = None):
    # Deferujemy odpowiedź bota
    await interaction.response.defer(ephemeral=False)

    # Domyślnie sprawdzamy osobę wpisującą komendę
    target_user = user or interaction.user

    try:
        # Pobieramy dane w osobnym wątku
        balance, streak, last_daily = await asyncio.to_thread(get_detailed_user_stats, target_user.id)
        
        # Obliczamy status Daily Reward
        now = int(time.time())
        cooldown = 86400 # 24 godziny
        
        if last_daily == 0:
            daily_status = "🟢 Ready to claim! (`/daily`)"
        elif (now - last_daily) >= cooldown:
            daily_status = "🟢 Ready to claim! (`/daily`)"
        else:
            next_claim = last_daily + cooldown
            daily_status = f"⏳ Available <t:{next_claim}:R>"

        # Tworzymy profesjonalny Embed statystyk
        embed = discord.Embed(
            title=f"📊 Financial Profile — {target_user.name}",
            color=0x00fff0 # Twój neonowy błękit VoltBota
        )
        
        # Sekcja finansów i aktywności
        embed.add_field(name="💳 Net Worth", value=f"**{balance:,}** Volt Coins", inline=True)
        embed.add_field(name="🔥 Daily Streak", value=f"`{streak} Day(s)`", inline=True)
        embed.add_field(name="🎁 Daily Reward Status", value=daily_status, inline=False)
        
        # Smaczek: typ konta
        account_type = "🤖 System Bot" if target_user.bot else "👤 Server Member"
        embed.add_field(name="🗂️ Account Type", value=f"`{account_type}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{target_user.id}`", inline=True)

        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.set_footer(
            text=f"Requested by {interaction.user.name} • Volt Ledger", 
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"❌ [STATS CMD ERROR] {e}")
        await interaction.followup.send(f"❌ Error while generating statistics: `{e}`", ephemeral=True)

def process_unwarn(guild_id: int, user_id: int) -> tuple[bool, int]:
    """Usuwa najnowsze ostrzeżenie użytkownika na danym serwerze.
    Zwraca krotkę: (czy_usunięto, liczba_pozostałych_warnów)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # 1. Szukamy ID najnowszego ostrzeżenia, filtrując TYLKO po obecnym serwerze
        cursor.execute(
            "SELECT id FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
            (str(guild_id), str(user_id))
        )
        row = cursor.fetchone()
        
        if not row:
            # Użytkownik nie ma żadnych warnów na tym serwerze
            return False, 0
            
        latest_warn_id = row[0]
        
        # 2. Usuwamy dokładnie to jedno konkretne ostrzeżenie
        cursor.execute("DELETE FROM warnings WHERE id = ?", (latest_warn_id,))
        conn.commit()
        
        # 3. Zliczamy ile ostrzeżeń mu jeszcze zostało NA TYM SERWERZE
        cursor.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
        remaining_count = cursor.fetchone()[0]
        
        return True, remaining_count
        
    finally:
        conn.close()

@bot.tree.command(name="unwarn", description="Remove the most recent warning from a server member")
@app_commands.describe(user="The member whose latest warning you want to pardon")
async def unwarn(interaction: discord.Interaction, user: discord.Member):
    # 1. Sprawdzenie uprawnień moderatora (Spójne z /timeout i /warn)
    if not interaction.user.guild_permissions.moderate_members:
        embed_no_perm = discord.Embed(
            title="❌ Permission Denied",
            description="You need the **Timeout Members** (`moderate_members`) permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_no_perm, ephemeral=True)
        return

    # Zabezpieczenie przed użyciem w DM
    if not interaction.guild_id:
        await interaction.response.send_message("❌ This command can only be used inside a server.", ephemeral=True)
        return

    # Deferujemy odpowiedź, bo modyfikujemy plik bazy danych
    await interaction.response.defer(ephemeral=False)

    guild_id = interaction.guild_id
    user_id = user.id

    try:
        # Odpalamy bezpieczny proces usuwania w tle
        was_removed, remaining_warns = await asyncio.to_thread(process_unwarn, guild_id, user_id)
        
        if not was_removed:
            embed_clean = discord.Embed(
                title="🛡️ Operation Cancelled",
                description=f"{user.mention} does not have any active warnings on this server.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed_clean)
            return

        # Budujemy piękny log sukcesu w Embedzie
        embed_success = discord.Embed(
            title="⚖️ Warning Pardoned",
            description=f"The most recent infraction for {user.mention} has been successfully expunged.",
            color=discord.Color.green()
        )
        embed_success.add_field(name="👤 Target", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed_success.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
        embed_success.add_field(name="📊 Remaining Warnings", value=f"`{remaining_warns}` active warnings", inline=False)
        
        embed_success.set_thumbnail(url=user.display_avatar.url)
        embed_success.set_footer(text="VoltBot Moderation Core", icon_url=bot.user.display_avatar.url)

        await interaction.followup.send(embed=embed_success)

    except Exception as e:
        print(f"❌ [UNWARN CMD ERROR] {e}")
        await interaction.followup.send(f"❌ An error occurred while removing the warning: `{e}`", ephemeral=True)

def get_user_rank_data(user_id: int) -> tuple[int, int] | None:
    """Pobiera (xp, level) dla użytkownika. Zwraca None, jeśli użytkownik nie ma jeszcze danych."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()

@bot.tree.command(name="rank", description="Check your or another member's current level and XP progress")
@premium_only()
@app_commands.describe(user="Select a member to check their rank (Leave blank to check your own)")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    target_user = user or interaction.user

    try:
        row = await asyncio.to_thread(get_user_rank_data, target_user.id)

        if not row:
            embed_no_data = discord.Embed(
                title="📈 No Rank Data",
                description=f"{target_user.mention} hasn't earned any XP yet. Start chatting to gain experience!",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed_no_data)
            return

        xp, level = row
        needed_xp = (level + 1) * 100
        percent = min(max(xp / needed_xp, 0.0), 1.0)

        filled = int(percent * 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        percent_display = int(percent * 100)

        embed = discord.Embed(
            title=f"🏆 {target_user.name}'s Rank Progression",
            color=0x00fff0
        )
        embed.add_field(name="📊 Current Level", value=f"Level **{level}**", inline=True)
        embed.add_field(name="✨ Experience Points", value=f"**{xp}** / **{needed_xp}** XP", inline=True)
        embed.add_field(name="📈 Progress to Level Up", value=f"{bar} **{percent_display}%**", inline=False)
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.name} • Volt Progression Core")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"❌ [RANK CMD ERROR] {e}")
        await interaction.followup.send(f"❌ Error while generating statistics: `{e}`", ephemeral=True)


def get_top_xp_data(limit: int = 10) -> list[tuple[int, int, int]]:
    """Pobiera z bazy danych TOP 10 użytkowników z najwyższym poziomem i XP."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # Sortujemy najpierw po poziomie (desc), a potem po dodatkowym XP (desc)
        cursor.execute("""
            SELECT user_id, level, xp 
            FROM levels 
            ORDER BY level DESC, xp DESC 
            LIMIT ?
        """, (limit,))
        
        return cursor.fetchall()
        
    except Exception as e:
        print(f"🔴 [DB TOPXP ERROR]: {e}")
        return []
    finally:
        conn.close()

@bot.tree.command(name="topxp", description="Display the global server leaderboard by level and XP")
async def topxp(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    try:
        rows = await asyncio.to_thread(get_top_xp_data, 10)

        if not rows:
            embed_empty = discord.Embed(
                title="📈 XP Leaderboard",
                description="No rank data has been recorded on this server yet.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed_empty)
            return

        badges = {1: "🥇", 2: "🥈", 3: "🥉"}
        description_lines = []

        for i, (user_id, level, xp) in enumerate(rows, start=1):
            badge = badges.get(i, f"`#{i}`")
            user = bot.get_user(user_id)
            
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except discord.NotFound:
                    username = f"Deleted User ({user_id})"
                except Exception:
                    username = f"Unknown User ({user_id})"
            
            if user:
                username = user.name

            description_lines.append(f"{badge} **{username}** — Level `{level}` *(Total: {xp:,} XP)*")

        embed = discord.Embed(
            title="🏆 VoltBot Global Experience Leaderboard",
            description="\n".join(description_lines),
            color=0x00fff0
        )
        
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
            
        embed.set_footer(text=f"Requested by {interaction.user.name} • Live Leaderboard Updates", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"❌ [TOPXP CMD ERROR] {e}")
        await interaction.followup.send(f"❌ An error occurred while generating the leaderboard: `{e}`", ephemeral=True)


def process_coinflip_gamble(user_id: int, bet_amount: int) -> tuple[str, dict]:
    """Przetwarza rzut monetą wewnątrz bezpiecznej transakcji."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("INSERT OR IGNORE INTO economy (user_id, balance, last_daily, streak) VALUES (?, 0, 0, 0)", (user_id,))
        
        cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        current_balance = cursor.fetchone()[0]
        
        if current_balance < bet_amount:
            conn.rollback()
            return "insufficient_funds", {"balance": current_balance}
            
        outcome = random.choice(["Heads", "Tails"])
        is_winner = random.choice([True, False])
        
        if is_winner:
            new_balance = current_balance + bet_amount
            cursor.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (bet_amount, user_id))
            status = "win"
        else:
            new_balance = current_balance - bet_amount
            cursor.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (bet_amount, user_id))
            status = "lose"
            
        conn.commit()
        return status, {"outcome": outcome, "new_balance": new_balance}
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 [DB COINFLIP ERROR]: {e}")
        return "error", {"error_msg": str(e)}
    finally:
        conn.close()

@bot.tree.command(name="coinflip", description="Flip a coin and gamble your Volt Coins with a 50/50 chance")
@premium_only()
@app_commands.describe(amount="The amount of coins you want to wager")
async def coinflip(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Your wager must be greater than 0 coins.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)
    user_id = interaction.user.id

    status, data = await asyncio.to_thread(process_coinflip_gamble, user_id, amount)

    if status == "insufficient_funds":
        embed_poor = discord.Embed(
            title="❌ Bet Rejected",
            description=f"You do not have enough coins to place this wager.\nYour balance: **{data['balance']:,}** coins.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed_poor, ephemeral=True)
        return
        
    elif status == "error":
        await interaction.followup.send(f"❌ Casino engine error: `{data['error_msg']}`", ephemeral=True)
        return

    coin_side = data["outcome"]
    new_balance = data["new_balance"]

    if status == "win":
        embed_win = discord.Embed(
            title="🟩 YOU WON!",
            description=f"The coin spun through the air and landed on **{coin_side.upper()}**!",
            color=discord.Color.green()
        )
        embed_win.add_field(name="💰 Earnings", value=f"**+{amount:,}** Volt Coins", inline=True)
        embed_win.add_field(name="💳 New Balance", value=f"**{new_balance:,}** coins", inline=True)
        embed_win.set_footer(text="VoltBot Entertainment Hub • Fortune favors the bold")
        await interaction.followup.send(embed=embed_win)
        
    else:
        embed_lose = discord.Embed(
            title="🟥 YOU LOST",
            description=f"The coin spun through the air and landed on **{coin_side.upper()}**...",
            color=discord.Color.red()
        )
        embed_lose.add_field(name="📉 Loss", value=f"**-{amount:,}** Volt Coins", inline=True)
        embed_lose.add_field(name="💳 New Balance", value=f"**{new_balance:,}** coins", inline=True)
        embed_lose.set_footer(text="VoltBot Entertainment Hub • House always wins")
        await interaction.followup.send(embed=embed_lose)


def get_top_economy_data(limit: int = 10) -> list[tuple[str, int]]:
    """Bezpiecznie pobiera TOP 10 najbogatszych graczy z bazy danych w tle."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT user_id, balance
            FROM economy
            ORDER BY balance DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    except Exception as e:
        print(f"🔴 [DB LEADERBOARD ERROR]: {e}")
        return []
    finally:
        conn.close()

@bot.tree.command(name="leaderboard", description="Display the global economy leaderboard of the richest users")
@premium_only() # Trzymamy komendę jako ekskluzywną funkcję Premium!
async def leaderboard(interaction: discord.Interaction):
    
    # Deferujemy odpowiedź, bo pobieranie nazw użytkowników może chwilę zająć
    await interaction.response.defer()

    # Pobieramy dane z bazy w bezpiecznym wątku
    rows = await asyncio.to_thread(get_top_economy_data, 10)

    if not rows:
        await interaction.followup.send("❌ No economy data found yet. Start working to earn some coins!")
        return

    embed = discord.Embed(
        title="💰 Volt Gold Reserve — Leaderboard",
        color=discord.Color.gold()
    )

    description_lines = []

    # Przetwarzamy wyniki
    for i, (user_id_str, balance) in enumerate(rows, start=1):
        user_id = int(user_id_str)
        
        # ⚡ OPTYMALIZACJA: Najpierw szukamy w pamięci podręcznej bota (0 ms lagów)
        user = bot.get_user(user_id)
        
        if not user:
            try:
                # Jeśli nie ma w cache, dopiero wtedy odpytujemy API Discorda
                user = await bot.fetch_user(user_id)
            except Exception:
                user = None

        # Formatujemy wyświetlaną nazwę
        username = user.name if user else f"Unknown User ({user_id})"
        
        # Dodajemy linijkę (pogrubiamy TOP 3 dla lepszego wyglądu)
        if i == 1:
            description_lines.append(f"🥇 **{username}** — `{balance:,}` coins")
        elif i == 2:
            description_lines.append(f"🥈 **{username}** — `{balance:,}` coins")
        elif i == 3:
            description_lines.append(f"🥉 **{username}** — `{balance:,}` coins")
        else:
            description_lines.append(f"**{i}.** {username} — `{balance:,}` coins")

    embed.description = "\n".join(description_lines)
    
    bot_avatar = bot.user.display_avatar.url if bot.user else None
    embed.set_footer(text="Volt Premium Economy System", icon_url=bot_avatar)

    await interaction.followup.send(embed=embed)


YOUR_DISCORD_ID = 1490030330084720892

@bot.tree.command(name="license_generate", description="Generate a new Premium license key (Owner Only)")
@app_commands.describe(days="How many days of Premium this key should grant")
async def license_generate(interaction: discord.Interaction, days: int):
    # ZABEZPIECZENIE: Tylko Ty możesz użyć tej komendy
    if interaction.user.id != YOUR_DISCORD_ID:
        # Wysyłamy wiadomość, że to komenda tylko dla właściciela
        await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
        return

    # Deferujemy odpowiedź
    await interaction.response.defer(ephemeral=True)

    # Generowanie klucza
    key_part1 = secrets.token_hex(4).upper()
    key_part2 = secrets.token_hex(4).upper()
    key_part3 = secrets.token_hex(4).upper()
    generated_key = f"VOLT-{key_part1}-{key_part2}-{key_part3}"

    # Zapis do bazy
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO licenses (license_key, duration_days) VALUES (?, ?)",
            (generated_key, days)
        )
        conn.commit()

        # Embed odpowiedzi
        embed_key = discord.Embed(
            title="🔑 New License Key Generated",
            description="Premium license created successfully.",
            color=0x00fff0
        )
        embed_key.add_field(name="🎫 License Key", value=f"`{generated_key}`", inline=False)
        embed_key.add_field(name="⏳ Duration", value=f"`{days} Days`", inline=True)
        embed_key.add_field(name="🔒 Status", value="`Ready to redeem`", inline=True)
        embed_key.set_footer(text="VoltBot License System")

        await interaction.followup.send(embed=embed_key, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Database error: `{e}`", ephemeral=True)
    finally:
        conn.close()
        
@bot.tree.command(name="license_redeem", description="Activate your subscription key for this server")
@app_commands.describe(key="Your license key (VOLT-XXXX-XXXX-XXXX)")
async def license_redeem(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=True)

    if not interaction.guild_id:
        await interaction.followup.send("❌ You can only redeem keys inside a server.", ephemeral=True)
        return

    clean_key = key.strip()
    guild_id_str = str(interaction.guild_id)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        # 1. Sprawdzamy czy klucz istnieje i nie jest użyty
        cursor.execute(
            "SELECT id, duration_days, is_used FROM licenses WHERE license_key = ?",
            (clean_key,),
        )
        row = cursor.fetchone()

        if not row:
            await interaction.followup.send("❌ This license key does not exist.", ephemeral=True)
            return

        db_id, duration_days, is_used = row

        if is_used == 1:
            await interaction.followup.send("❌ This license key has already been used.", ephemeral=True)
            return

        # 2. Obliczamy czas wygaśnięcia
        expiry_timestamp = int(time.time()) + (int(duration_days) * 24 * 60 * 60)

        # 3. Zapisujemy aktywację (UPDATE)
        cursor.execute("""
            UPDATE licenses 
            SET is_used = 1, used_by_user_id = ?, expires_at = ? 
            WHERE id = ?
        """, (guild_id_str, expiry_timestamp, db_id))

        conn.commit()
        
        print(f"DEBUG: Aktywowano klucz {clean_key} dla serwera {guild_id_str}. Zmieniono wierszy: {cursor.rowcount}")

        # 4. Sukces
        embed_success = discord.Embed(
            title="👑 Volt Premium Activated Successfully!",
            description=f"Premium features are now unlocked for **{interaction.guild.name}**.",
            color=0x00fff0
        )
        embed_success.add_field(name="📅 Subscription Plan", value=f"`{duration_days} Days`", inline=True)
        await interaction.followup.send(embed=embed_success, ephemeral=True)

    except Exception as e:
        print(f"❌ [LICENSE ERROR] {e}")
        await interaction.followup.send(f"❌ Database error: `{e}`", ephemeral=True)
    finally:
        conn.close()
        
@bot.tree.command(name="license_check", description="Check the Premium subscription status for this server")
async def license_check(interaction: discord.Interaction):
    # Deferujemy odpowiedź, bo zaglądamy do bazy danych
    await interaction.response.defer(ephemeral=True)

    # Zabezpieczenie przed wpisaniem w DM
    if not interaction.guild_id:
        await interaction.followup.send("❌ This command can only be used inside a server.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "volt.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    current_time = int(time.time())

    try:
        # Szukamy aktywnej licencji przypisanej do tego serwera
        cursor.execute(
            "SELECT expires_at FROM licenses WHERE used_by_user_id = ? AND is_used = 1",
            (guild_id,)
        )
        row = cursor.fetchone()

        if row and row[0] is not None:
            expires_at = int(row[0])

            # Sprawdzamy czy licencja jeszcze NIE wygasła
            if expires_at > current_time:
                # <t:expires_at:F> - Pełna data i godzina (np. 18 czerwca 2026 16:30)
                # <t:expires_at:R> - Odliczanie relatywne (np. za 20 dni)
                discord_time_full = f"<t:{expires_at}:F>"
                discord_time_relative = f"<t:{expires_at}:R>"

                embed_active = discord.Embed(
                    title="👑 Volt Premium Status",
                    description=f"This server **{interaction.guild.name}** has an active Premium subscription! 🌌",
                    color=0x00fff0 # Twój neonowy błękit
                )
                embed_active.add_field(name="📅 Expiration Date", value=discord_time_full, inline=False)
                embed_active.add_field(name="⏳ Time Remaining", value=discord_time_relative, inline=False)
                embed_active.add_field(name="🔒 Server Protection", value="`Enabled 🟢`", inline=True)
                embed_active.add_field(name="⚡ Features Unlocked", value="`All Premium Commands`", inline=True)
                embed_active.set_footer(text="Thank you for supporting VoltBot!")
                
                await interaction.followup.send(embed=embed_active, ephemeral=True)
                return

        # Jeśli row jest pusty lub czas wygasł – serwer nie ma Premium
        embed_inactive = discord.Embed(
            title="❌ Premium Inactive",
            description=(
                f"This server **{interaction.guild.name}** does not have an active Premium subscription.\n\n"
                f"To unlock premium modules like advanced `/ticket` logs and filters, "
                f"redeem a valid key using `/license_redeem`."
            ),
            color=discord.Color.red()
        )
        embed_inactive.set_footer(text="VoltBot Licensing Hub")
        await interaction.followup.send(embed=embed_inactive, ephemeral=True)

    except Exception as e:
        print(f"❌ [CHECK ERROR] {e}")
        await interaction.followup.send(f"❌ An error occurred while checking license: `{e}`", ephemeral=True)
    finally:
        conn.close()

def main():
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("www:app", host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
    
print(f"[DEBUG] Sprawdzanie komend przed startem:")
print(f"[DEBUG] Liczba komend w tree: {len(bot.tree.get_commands())}")
for cmd in bot.tree.get_commands():
    print(f"[DEBUG] Znaleziono komendę: {cmd.name}")

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
