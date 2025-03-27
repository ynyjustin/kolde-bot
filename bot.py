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
CHANNEL_ID = 1227704136552939551  # Your fixed channel
ACCESS_ROLE_ID = 1227708209356345454  # Role required for access

if not TOKEN or not RUNWAY_API_KEY:
    print("❌ ERROR: Missing bot token or API key!")
    exit(1)

DB_FILE = "credits.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 100
        )
    """)
    conn.commit()
    conn.close()

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Helpers ---
def user_has_access(member):
    """Check if a user has the required role for access."""
    return any(role.id == ACCESS_ROLE_ID for role in member.roles)

async def setup_menu(channel):
    embed = discord.Embed(
        title="🎬 Welcome to Kolde AI Video Generator",
        description=(
            "Generate high-quality AI videos using text or image + prompt.\n"
            "**Each generation costs 20 credits**. New users get 100 credits for free!\n\n"
            "💡 *Tips for prompts:* Use specific descriptions, mention style, mood, and action.\n"
            "🛍️ You can buy credits using the red button below.\n"
            "📜 Use the buttons below to interact with the bot."
        ),
        color=discord.Color.dark_blue()
    )
    await channel.send(embed=embed, view=MainMenu())

# --- Main Button View ---
class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔓 Login", style=discord.ButtonStyle.blurple, custom_id="login", row=0))
        self.add_item(discord.ui.Button(label="🔒 Get Access", style=discord.ButtonStyle.red, custom_id="get_access", row=0))

        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link, row=1))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link, row=1))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link, row=1))

# --- Events ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions and ensure role-based access dynamically."""
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id) if guild else None

    if not member:
        await interaction.response.send_message("❌ Error: Could not retrieve user info.", ephemeral=True)
        return

    has_access = user_has_access(member)

    if interaction.data["custom_id"] == "get_access":
        await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] == "login":
        if has_access:
            await interaction.response.send_message("✅ You already have access!", ephemeral=True)
        else:
            await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] in ["text_gen", "image_gen"]:
        if not has_access:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        # 🔹 Ask for a prompt from the user
        await interaction.followup.send("📝 Please enter your prompt:", ephemeral=True)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)  
            prompt = msg.content
            await msg.delete()  # ✅ Delete user's message after receiving
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)  

        url = f"https://example.com/video/{user.id}"
        
        try:
            await user.send(f"🎥 Your video is ready! Click here: {url}")
            await interaction.followup.send("✅ Video sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ I couldn't DM you! Please enable DMs and try again.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    init_db()
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await setup_menu(channel)

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="💳 Pay with PayPal", url="https://paypal.com", style=discord.ButtonStyle.blurple))
        self.add_item(discord.ui.Button(label="💳 Pay with Stripe", url="https://stripe.com", style=discord.ButtonStyle.blurple))
        self.add_item(discord.ui.Button(label="✅ Confirm Payment", style=discord.ButtonStyle.green, custom_id="confirm_payment"))

# Optional: Refresh menu manually
@bot.command()
async def menu(ctx):
    if ctx.channel.id == CHANNEL_ID:
        await setup_menu(ctx.channel)
        await ctx.send("✅ Menu refreshed.")

bot.run(TOKEN)
