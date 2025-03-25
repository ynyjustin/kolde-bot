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

def update_credits(user_id, cost):
    """Deduct credits after video generation."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_credits SET credits = credits - ? WHERE user_id = ?", (cost, user_id))
    conn.commit()
    conn.close()

def save_video(user_id, url):
    """Save video generation history."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO video_history (user_id, video_url, generated_at) VALUES (?, ?, ?)",
                   (user_id, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_history(user_id):
    """Retrieve the last 5 generated videos for a user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT video_url, generated_at FROM video_history WHERE user_id = ? ORDER BY generated_at DESC LIMIT 5", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    """Payment buttons for purchasing access."""
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label="💳 Pay with PayPal", url="https://paypal.com/paylink", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="💰 Pay with Stripe", url="https://stripe.com/paylink", style=discord.ButtonStyle.link))

# --- Main Button View ---
class MainMenu(discord.ui.View):
    """Main menu buttons with role-based access handling."""
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        self.member = member
        self.has_access = any(r.id == ACCESS_ROLE_ID for r in member.roles)

        # Public buttons (everyone sees these)
        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link))

        # If user has access, show full menu
        if self.has_access:
            self.add_item(discord.ui.Button(label="🎬 Generate Video (Text)", style=discord.ButtonStyle.green, custom_id="text_gen"))
            self.add_item(discord.ui.Button(label="📷 Generate Video (Image + Prompt)", style=discord.ButtonStyle.blurple, custom_id="image_gen"))
            self.add_item(discord.ui.Button(label="📜 History", style=discord.ButtonStyle.gray, custom_id="history"))
            self.add_item(discord.ui.Button(label="💰 Check Credits", style=discord.ButtonStyle.gray, custom_id="credits"))
        else:
            # If no access, show Get Access button
            self.add_item(discord.ui.Button(label="🚀 Get Access", style=discord.ButtonStyle.red, custom_id="get_access"))

async def setup_menu(channel, member):
    """Post the main menu with updated role check."""
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
    await channel.send(embed=embed, view=MainMenu(member))

# --- Events ---
@bot.event
async def on_ready():
    """Initialize bot and ensure menu is pinned."""
    print(f"✅ Logged in as {bot.user}")
    init_db()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions and check role dynamically."""
    user_roles = [role.id for role in interaction.user.roles]
    has_access = ACCESS_ROLE_ID in user_roles

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
                vids = get_history(interaction.user.id)
                msg = "\n".join([f"{t} - [Watch]({u})" for u, t in vids]) if vids else "📭 No videos yet."
                await interaction.response.send_message(msg, ephemeral=True)
            elif interaction.data["custom_id"] == "credits":
                credits = get_user_credits(interaction.user.id)
                await interaction.response.send_message(f"💳 You have **{credits}** credits left.", ephemeral=True)
        else:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)

@bot.command()
async def menu(ctx):
    """Manual command to refresh menu."""
    if ctx.channel.id == CHANNEL_ID:
        await setup_menu(ctx.channel, ctx.author)
        await ctx.send("✅ Menu refreshed.")

bot.run(TOKEN)
