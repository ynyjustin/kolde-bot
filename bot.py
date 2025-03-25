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
CHANNEL_ID = 1227704136552939551  # Your fixed channel
ACCESS_ROLE_ID = 1227708209356345454  # Your role ID for access
PAYPAL_LINK = "https://paypal.com/checkout?amount=2.99&currency=EUR"
STRIPE_LINK = "https://stripe.com/pay?amount=2.99&currency=EUR"

# Ensure bot token is set
if not TOKEN:
    print("❌ ERROR: Missing bot token!")
    exit(1)

DB_FILE = "credits.db"

def init_db():
    """Initialize database tables if they don't exist."""
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

# --- Database Helpers ---
def get_user_credits(user_id):
    """Retrieve user credits or initialize with 100."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute("INSERT INTO user_credits (user_id, credits) VALUES (?, ?)", (user_id, 100))
        conn.commit()
        credits = 100
    else:
        credits = row[0]
    
    conn.close()
    return credits

def update_credits(user_id, cost):
    """Deduct credits from the user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_credits SET credits = credits - ? WHERE user_id = ?", (cost, user_id))
    conn.commit()
    conn.close()

def save_video(user_id, url):
    """Save video to history."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO video_history (user_id, video_url, generated_at) VALUES (?, ?, ?)",
                   (user_id, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_history(user_id):
    """Get last 5 generated videos."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT video_url, generated_at FROM video_history WHERE user_id = ? ORDER BY generated_at DESC LIMIT 5", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- Main Menu ---
class MainMenu(discord.ui.View):
    """Main menu buttons."""
    def __init__(self, has_access):
        super().__init__(timeout=None)
        self.has_access = has_access

        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link))

        if has_access:
            self.add_item(discord.ui.Button(label="Generate Video (Text)", style=discord.ButtonStyle.green, custom_id="text_gen"))
            self.add_item(discord.ui.Button(label="Generate Video (Image + Prompt)", style=discord.ButtonStyle.blurple, custom_id="image_gen"))
            self.add_item(discord.ui.Button(label="📜 History", style=discord.ButtonStyle.gray, custom_id="history"))
            self.add_item(discord.ui.Button(label="💰 Check Credits", style=discord.ButtonStyle.gray, custom_id="credits"))
        else:
            self.add_item(GetAccessButton())

class GetAccessButton(discord.ui.Button):
    """Button for purchasing access."""
    def __init__(self):
        super().__init__(label="🚀 Get Access (€2.99)", style=discord.ButtonStyle.red, custom_id="get_access")

    async def callback(self, interaction: discord.Interaction):
        """Show payment options."""
        await interaction.response.send_message("💳 Choose a payment method:", view=PaymentMenu(), ephemeral=True)

class PaymentMenu(discord.ui.View):
    """Menu for choosing PayPal or Stripe."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Pay with PayPal", url=PAYPAL_LINK, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Pay with Stripe", url=STRIPE_LINK, style=discord.ButtonStyle.link))

# --- Bot Events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    init_db()
    await ensure_menu_pinned()

async def ensure_menu_pinned():
    """Ensure the menu is pinned in the correct channel."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ ERROR: Channel not found!")
        return
    async for message in channel.history(limit=10):
        if message.author == bot.user and message.embeds:
            return
    await setup_menu(channel)

async def setup_menu(channel):
    """Post the main menu in the channel."""
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
    await channel.send(embed=embed, view=MainMenu(has_access=False))

# --- Commands ---
@bot.command()
async def menu(ctx):
    """Refresh the menu."""
    if ctx.channel.id == CHANNEL_ID:
        await setup_menu(ctx.channel)
        await ctx.send("✅ Menu refreshed.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions."""
    if interaction.data["custom_id"] in ["text_gen", "image_gen", "history", "credits"]:
        if any(r.id == ACCESS_ROLE_ID for r in interaction.user.roles):
            if interaction.data["custom_id"] == "text_gen":
                await interaction.response.send_message("✏️ Enter your video prompt:", ephemeral=True)
            elif interaction.data["custom_id"] == "image_gen":
                await interaction.response.send_message("📷 Upload an image:", ephemeral=True)
            elif interaction.data["custom_id"] == "history":
                vids = get_history(interaction.user.id)
                msg = "\n".join([f"{t} - [Watch]({u})" for u, t in vids]) if vids else "📭 No videos yet."
                await interaction.response.send_message(msg, ephemeral=True)
            elif interaction.data["custom_id"] == "credits":
                credits = get_user_credits(interaction.user.id)
                await interaction.response.send_message(f"💳 You have **{credits}** credits left.", ephemeral=True)
        else:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)

bot.run(TOKEN)
