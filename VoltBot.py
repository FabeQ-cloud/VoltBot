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

def check_premium_db(user_id):
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    
    # Wymuszamy int() na user_id na wypadek, gdyby w bazie był zapisany jako tekst
    cursor.execute("SELECT premium_until FROM subscriptions WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    
    conn.close()
    
    if row and row[0] is not None:
        try:
            premium_until = int(row[0]) # Konwertujemy wynik z bazy na int
            current_time = int(time.time())
            
            
            print(f"DEBUG PREMIUM: User {user_id} has premium until {premium_until}. Current time: {current_time}")
            
            if premium_until > current_time:
                return True
        except ValueError:
            print(f"❌ DEBUG PREMIUM: Błąd konwersji timestampu dla użytkownika {user_id}")
            return False
            
    return False
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
        user_id = interaction.user.id
        
        # Bezpiecznie pytamy bazę danych w osobnym wątku
        has_premium = await asyncio.to_thread(check_premium_db, user_id)
        
        if not has_premium:
            # Informujemy użytkownika, że ta funkcja wymaga zakupu
            await interaction.response.send_message(
                "❌ **This feature requires Volt Premium!**\n"
                "Visit the link: https://voltbot-az88.onrender.com/shop to purchase a license key and support the project.",
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
        
@bot.event
async def on_message(message):

    if message.author.bot:
        return
    
    user_id = message.author.id
    current_time = time.time()

    user_message_times[user_id].append(current_time)

    user_message_times[user_id] = [
        t for t in user_message_times[user_id]
        if current_time - t < 5
    ]

    user_recent_messages[user_id].append(message)

    user_recent_messages[user_id] = user_recent_messages[user_id][-20:]

    if len(user_message_times[user_id]) >= 6:

        for msg in user_recent_messages[user_id]:
            try:
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        user_message_times[user_id].clear()
        user_recent_messages[user_id].clear()

        warning = await message.channel.send(
            f"{message.author.mention} Stop spamming!"
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except discord.NotFound:
            pass

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {latency} ms")

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

@bot.tree.command(name="ticket", description="Open ticket panel")
@premium_only()
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Support Tickets",
        description="Click a button below to open a ticket.",
        color=0x00ffcc
    )
    await interaction.response.send_message(
        embed=embed,
        view=TicketView(), 
        ephemeral=False
    )

@bot.tree.command(name="close", description="Close this ticket")
async def close(interaction: discord.Interaction):

    channel = interaction.channel

    if "ticket-" not in channel.name:
        await interaction.response.send_message(
            "This is not a ticket channel.",
            ephemeral=True
        )
        return

    await interaction.response.send_message("Closing ticket...")
    await channel.delete()
    
@bot.tree.command(name="clear", description="Delete messages")
@app_commands.describe(amount="How many messages to delete")
async def clear(interaction: discord.Interaction, amount: int):

    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("No permission ", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    deleted = await interaction.channel.purge(limit=amount + 1)

    await interaction.followup.send(
        f" Deleted {len(deleted)} messages"
    )
@bot.tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason" ):

    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("No permission!", ephemeral=True)
        return
    
    await user.kick(reason=reason)

    await interaction.response.send_message(
        f"{user} kicked, Reason: {reason}"
    )
@bot.tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):

    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("No permission!", ephemeral=True)
        return
    
    await user.ban(reason=reason)

    await interaction.response.send_message(
        f"{user} banned, Reason: {reason}"
    )

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(
    user="User to warn",
    reason="Reason for warning"
)
async def warn(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str
):

    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message(
            "You don't have permission to warn users.",
            ephemeral=True
        )
        return

    if user.bot:
        await interaction.response.send_message(
            "You cannot warn bots.",
            ephemeral=True
        )
        return

    cursor.execute(
        "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
        (user.id, reason)
    )

    conn.commit()

    cursor.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ?",
        (user.id,)
    )

    warn_count = cursor.fetchone()[0]

    embed = discord.Embed(
        title="User Warned",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="User",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name="Moderator",
        value=interaction.user.mention,
        inline=True
    )

    embed.add_field(
        name="Reason",
        value=reason,
        inline=False
    )

    embed.add_field(
        name="Total Warnings",
        value=str(warn_count),
        inline=False
    )

    await interaction.response.send_message(embed=embed)

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


# Pomocnicza funkcja do operacji na bazie - uruchamiana w osobnym wątku
def process_daily_db(user_id):
    # Otwieramy nowe, bezpieczne połączenie dla tego wątku
    conn = sqlite3.connect("volt.db")
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT balance, last_daily, streak FROM economy WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()

    now = int(time.time())
    cooldown = 86400
    base_reward = 1000

    if row:
        balance, last_daily, streak = row

        # 1. Sprawdzenie cooldownu
        if last_daily and now - last_daily < cooldown:
            remaining = cooldown - (now - last_daily)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            conn.close()
            return {"status": "cooldown", "hours": hours, "minutes": minutes}

        # 2. Sprawdzenie czy streak został utrzymany (w ciągu 48 godzin)
        if last_daily and now - last_daily <= cooldown * 2:
            streak += 1
        else:
            streak = 1

        reward = base_reward + (streak * 50)
        new_balance = balance + reward

        cursor.execute(
            """
            UPDATE economy
            SET balance = ?, last_daily = ?, streak = ?
            WHERE user_id = ?
            """,
            (new_balance, now, streak, user_id)
        )
    else:
        # Nowy użytkownik w ekonomii
        streak = 1
        reward = base_reward
        new_balance = reward

        cursor.execute(
            """
            INSERT INTO economy (user_id, balance, last_daily, streak)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, new_balance, now, streak)
        )

    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "reward": reward,
        "streak": streak,
        "new_balance": new_balance
    }

@bot.tree.command(name="daily", description="Claim your daily reward")
@premium_only()
async def daily(interaction: discord.Interaction):
    await interaction.response.defer()

    user_id = interaction.user.id
    
    result = await asyncio.to_thread(process_daily_db, user_id)

    
    if result["status"] == "cooldown":
        await interaction.followup.send(
            f"You already claimed daily!\nTry again in **{result['hours']}h {result['minutes']}m**",
            ephemeral=True
        )
        return

    
    embed = discord.Embed(
        title="Daily Reward",
        description=f"+{result['reward']} coins\nStreak: {result['streak']} 🔥",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Balance",
        value=f"{result['new_balance']:,} coins",
        inline=False
    )

    await interaction.followup.send(embed=embed)
    
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


YOUR_DISCORD_ID = 1490030330084720892  # Twoje poprawne ID

@bot.tree.command(name="license_generate", description="Generate a new license key (Admin only)")
@app_commands.describe(days="How many days of subscription")
async def license_generate(interaction: discord.Interaction, days: int):
    # Sprawdzamy, czy to na pewno Ty
    if interaction.user.id == YOUR_DISCORD_ID:
        try:
            # Generujemy bezpieczny, losowy klucz
            raw_key = secrets.token_hex(6).upper()
            license_key = f"VOLT-{raw_key[:4]}-{raw_key[4:8]}-{raw_key[8:12]}"
            
            # Próba zapisu do bazy danych
            db_status = database.add_license_key(license_key, days)
            
            if db_status:
                await interaction.response.send_message(
                    f"**New license key generated!**\n`{license_key}` ({days} days)", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Failed to generate key. Try again.", 
                    ephemeral=True
                )
                
        except Exception as error:
            # Jeśli baza danych lub cokolwiek innego wywali błąd, bot natychmiast Ci go wyświetli
            await interaction.response.send_message(
                f"**Backend Error:** `{str(error)}`", 
                ephemeral=True
            )
    else:
        # Odpowiedź dla obcych użytkowników
        await interaction.response.send_message(
            "You do not have permission to use this command.", 
            ephemeral=True
        )

@bot.tree.command(name="license_redeem", description="Activate your subscription key")
@app_commands.describe(key="Your license key (VOLT-XXXX-XXXX-XXXX)")
async def license_redeem(interaction: discord.Interaction, key: str):
    user_id = str(interaction.user.id)
    status = database.redeem_license_key(key.strip(), user_id)
    
    if status == "invalid":
        await interaction.response.send_message("This license key does not exist.", ephemeral=True)
    elif status == "used":
        await interaction.response.send_message("This license key has already been used.", ephemeral=True)
    elif status == "success":
        await interaction.response.send_message("License activated successfully! Thank you for your purchase.", ephemeral=True)

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
