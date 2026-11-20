import discord
from discord import app_commands
from discord.ext import commands
import database

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

# --- REDEEM LICENSE COMMAND ---
@bot.tree.command(name="redeem", description="Activate your VoltBot Premium license using your purchase key.")
@app_commands.describe(key="Enter your license key received on the website")
async def redeem(interaction: discord.Interaction, key: str):
    success, message = database.activate_license(interaction.user.id, key)
    
    embed = discord.Embed(
        title="✨ License Activation",
        description=message,
        color=discord.Color.green() if success else discord.Color.red()
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
