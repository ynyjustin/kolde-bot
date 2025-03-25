import os
import discord
from discord.ext import commands
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
CHANNEL_ID = 1227704136552939551  # Fixed channel ID
ACCESS_ROLE_ID = 1227708209356345454  # Required role ID

if not TOKEN or not RUNWAY_API_KEY:
    print("❌ ERROR: Missing bot token or API key!")
    exit(1)

DB_FILE = "credits.db"

def init_db():
    """Initialize the SQLite database for credits and history."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 100
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_history (
            user_id INTEGER,
            video_url TEXT,
            generated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Helpers ---
def get_user_credits(user_id):
    """Fetch the user's current credit balance."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO user_credits (user_id, credits) VALUES (?, ?)", (user_id, 100))
        conn.commit()
        credits = 100
    else:
        credits = row[0]
    conn.close()
    return credits

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    """Payment buttons for purchasing access."""
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label="💳 Pay with PayPal", url="https://paypal.com/paylink", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="💰 Pay with Stripe", url="https://stripe.com/paylink", style=discord.ButtonStyle.link))

# --- Main Menu ---
class MainMenu(discord.ui.View):
    """Main menu buttons with role-based access handling."""
    def __init__(self, has_access: bool):
        super().__init__(timeout=None)

        # Public buttons (everyone sees these)
        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link))

        # If user has access, show full menu
        if has_access:
            self.add_item(discord.ui.Button(label="🎬 Generate Video (Text)", style=discord.ButtonStyle.green, custom_id="text_gen"))
            self.add_item(discord.ui.Button(label="📷 Generate Video (Image + Prompt)", style=discord.ButtonStyle.blurple, custom_id="image_gen"))
            self.add_item(discord.ui.Button(label="📜 History", style=discord.ButtonStyle.gray, custom_id="history"))
            self.add_item(discord.ui.Button(label="💰 Check Credits", style=discord.ButtonStyle.gray, custom_id="credits"))
        else:
            # If no access, show Get Access button
            self.add_item(discord.ui.Button(label="🚀 Get Access", style=discord.ButtonStyle.red, custom_id="get_access"))

async def setup_menu():
    """Ensure the menu is posted in the designated channel."""
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ ERROR: Channel not found!")
        return
    
    async for message in channel.history(limit=10):
        if message.author == bot.user and message.embeds:
            return  # Menu already exists

    embed = discord.Embed(
        title="🎬 Welcome to Kolde AI Video Generator",
        description=(
            "Generate high-quality AI videos using text or images.\n"
            "**Each generation costs 20 credits**. New users get 100 credits for free!\n\n"
            "💡 Use specific prompts for better results.\n"
            "🛍️ Buy credits using the red button below.\n"
        ),
        color=discord.Color.dark_blue()
    )
    
    guild = bot.get_guild(channel.guild.id)
    bot_member = guild.me
    await channel.send(embed=embed, view=MainMenu(has_access=True))  # Ensuring bot itself has access

# --- Events ---
@bot.event
async def on_ready():
    """Initialize bot and ensure menu is pinned."""
    print(f"✅ Logged in as {bot.user}")
    init_db()
    bot.loop.create_task(setup_menu())  # Fixes menu not appearing

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions and check role dynamically."""
    user = interaction.user
    has_access = any(role.id == ACCESS_ROLE_ID for role in user.roles)

    if interaction.data["custom_id"] == "get_access":
        await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] in ["text_gen", "image_gen", "history", "credits"]:
        if has_access:
            if interaction.data["custom_id"] == "text_gen":
                await interaction.response.send_message("✏️ Enter your video prompt:", ephemeral=True)
            elif interaction.data["custom_id"] == "image_gen":
                await interaction.response.send_message("📷 Upload an image:", ephemeral=True)
            elif interaction.data["custom_id"] == "history":
                await interaction.response.send_message("📜 Your history is being fetched...", ephemeral=True)
            elif interaction.data["custom_id"] == "credits":
                credits = get_user_credits(interaction.user.id)
                await interaction.response.send_message(f"💳 You have **{credits}** credits left.", ephemeral=True)
        else:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)

@bot.command()
async def menu(ctx):
    """Manual command to refresh menu."""
    if ctx.channel.id == CHANNEL_ID:
        await setup_menu()
        await ctx.send("✅ Menu refreshed.")

bot.run(TOKEN)
