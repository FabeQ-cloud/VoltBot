import discord
from discord import app_commands
from discord.ext import commands
import database
import secrets
import string

# Initialize database
database.init_db()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"[🤖] VoltBot logged in as {bot.user} and slash commands synced!")
    except Exception as e:
        print(f"[❌] Failed to sync slash commands: {e}")

# --- FREE COMMAND ---
@bot.tree.command(name="ping", description="Check VoltBot's latency and connection status.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"VoltBot is online and running smoothly.\nLatency: `{latency}ms`",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- REDEEM LICENSE COMMAND (Z komunikatem "Thanks for purchase") ---
@bot.tree.command(name="redeem", description="Activate your VoltBot Premium license using your purchase key.")
@app_commands.describe(key="Enter your 16-character license key received after purchase")
async def redeem(interaction: discord.Interaction, key: str):
    # Wywołujemy funkcję aktywacji z bazy danych
    success, message = database.activate_license(interaction.user.id, key.strip())
    
    if success:
        description = "🎉 **Thanks for your purchase!** Your Premium status has been successfully activated. Enjoy all exclusive features!"
        color = discord.Color.green()
    else:
        description = f"❌ {message}"
        color = discord.Color.red()

    embed = discord.Embed(
        title="✨ License Activation",
        description=description,
        color=color
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- PREMIUM COMMAND (PAYWALL) ---
@bot.tree.command(name="premiumbot", description="Exclusive advanced feature available only for Premium subscribers.")
async def premiumbot(interaction: discord.Interaction):
    is_premium = database.check_user_premium(interaction.user.id)
    
    if not is_premium:
        embed = discord.Embed(
            title="🔒 Premium Feature Locked",
            description="This command requires an active **VoltBot Premium** subscription.\nVisit our website to get your license, then use `/redeem [key]`!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⚡ Welcome to the VIP Zone!",
        description="You have successfully accessed the exclusive premium features of VoltBot.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="genkey", description="[ADMIN] Generate a 16-character premium license key.")
@app_commands.describe(days="Duration in days (e.g., 30 for Monthly, 365 for Yearly)")
async def genkey(interaction: discord.Interaction, days: int):
    # 👇 TUTAJ WPISZ SWOJE PRAWDZIWE DISCORD USER ID (w liczbach)
    OWNER_ID = 1490030330084720892  # Zastąp to swoim ID, jeśli jest inne
    
    # Sprawdzamy czy osoba wpisująca komendę to Ty
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(
            title="⛔ Access Denied",
            description="Only owner can generate code",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Jeśli to Ty, generujemy 16-znakowy kod (format: XXXX-XXXX-XXXX-XXXX)
    alphabet = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(alphabet) for _ in range(4))
    part2 = ''.join(secrets.choice(alphabet) for _ in range(4))
    part3 = ''.join(secrets.choice(alphabet) for _ in range(4))
    part4 = ''.join(secrets.choice(alphabet) for _ in range(4))
    
    key = f"{part1}-{part2}-{part3}-{part4}"
    
    # Zapis do bazy danych
    database.create_license_key(key, duration_days=days)

    embed = discord.Embed(
        title="🔑 16-Character License Generated",
        description=f"Successfully created a **{days}-day** premium key:\n`{key}`\n\nGive this key to your customer!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
