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
        cursor.execute("INSERT INTO user_credits (user_id, credits) VALUES (?, 100)", (user_id,))
        conn.commit()
        credits = 100
    else:
        credits = row[0]
    conn.close()
    return credits

async def refresh_user_menu(interaction: discord.Interaction, has_access: bool):
    """Updates the menu dynamically for the user who clicked Get Access."""
    embed = discord.Embed(
        title="🎬 Kolde AI Video Generator",
        description="Use text or images to generate AI-powered videos.\n\n"
                    "**Each generation costs 20 credits.** New users get 100 credits free!\n\n"
                    "💡 Use detailed prompts for better results.\n"
                    "🛍️ Buy more credits using the buttons below.",
        color=discord.Color.dark_blue()
    )

    await interaction.response.edit_message(embed=embed, view=MainMenu(has_access))

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    """Payment buttons for purchasing access."""
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label="💳 Pay with PayPal", url="https://paypal.com/paylink", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="💰 Pay with Stripe", url="https://stripe.com/paylink", style=discord.ButtonStyle.link))
    
    @discord.ui.button(label="✅ I've Paid", style=discord.ButtonStyle.green, custom_id="confirm_payment")
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User confirms payment, menu refreshes dynamically."""
        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("❌ Error fetching your role!", ephemeral=True)
            return

        # Check if user already has the role
        role = discord.utils.get(interaction.guild.roles, id=ACCESS_ROLE_ID)
        if role:
            if role not in member.roles:
                await member.add_roles(role)  # Grant access role
                await interaction.user.send("🎉 Access granted! You now have full functionality.")
            else:
                await interaction.user.send("✅ You already have access!")

        # Refresh the menu with full access for the user
        await refresh_user_menu(interaction, has_access=True)

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
        title="🎬 Kolde AI Video Generator",
        description="Use text or images to generate AI-powered videos.\n\n"
                    "**Each generation costs 20 credits.** New users get 100 credits free!\n\n"
                    "💡 Use detailed prompts for better results.\n"
                    "🛍️ Buy more credits using the buttons below.",
        color=discord.Color.dark_blue()
    )

    await channel.send(embed=embed, view=MainMenu(has_access=False))  # Default menu for users without access

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
    guild = interaction.guild  # Get the guild from interaction

    if guild:
        member = guild.get_member(user.id)  # Fetch full member object with roles
        if member:
            has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles)
        else:
            has_access = False
    else:
        has_access = False

    if interaction.data["custom_id"] == "get_access":
        await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] in ["text_gen", "image_gen", "history", "credits"]:
        if has_access:
            await interaction.response.send_message("✅ You have access!", ephemeral=True)
        else:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)

@bot.command()
async def menu(ctx):
    """Manually refresh the menu based on the user's role."""
    if ctx.channel.id == CHANNEL_ID:
        member = ctx.guild.get_member(ctx.author.id)
        has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles)
        await ctx.send("✅ Menu refreshed.", view=MainMenu(has_access=has_access))

bot.run(TOKEN)
