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
CHANNEL_ID = 1227704136552939551  
ACCESS_ROLE_ID = 1227708209356345454  

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_history (
            user_id INTEGER,
            video_url TEXT,
            generated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

def user_has_access(member):
    return any(role.id == ACCESS_ROLE_ID for role in member.roles)

# --- Main Menu ---
class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔓 Login", style=discord.ButtonStyle.blurple, custom_id="login", row=0))
        self.add_item(discord.ui.Button(label="🔒 Get Access", style=discord.ButtonStyle.red, custom_id="get_access", row=0))

        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link, row=1))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link, row=1))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link, row=1))

# --- Full Function Menu ---
class FullFunctionMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🎥 Video by Text Prompt", style=discord.ButtonStyle.green, custom_id="video_text", row=0))
        self.add_item(discord.ui.Button(label="🖼️ Video by Image + Text", style=discord.ButtonStyle.green, custom_id="video_image", row=0))

        self.add_item(discord.ui.Button(label="📜 View History", style=discord.ButtonStyle.blurple, custom_id="history", row=1))
        self.add_item(discord.ui.Button(label="🔄 Refresh Menu", style=discord.ButtonStyle.gray, custom_id="refresh", row=1))

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="💰 Buy Access", url="https://example.com/buy", style=discord.ButtonStyle.link))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions and ensure role-based access dynamically."""
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id) if guild else None
    has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles) if member else False

    await interaction.response.defer()

    if interaction.data["custom_id"] == "get_access":
        await interaction.followup.send("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] == "login":
        if has_access:
            try:
                await interaction.message.edit(view=FullFunctionMenu())  
            except discord.Forbidden:
                await interaction.followup.send("⚠️ I don't have permission to edit this message!", ephemeral=True)
        else:
            await interaction.followup.send("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] in ["video_text", "video_image"]:
        if not has_access:
            await interaction.followup.send("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return

        # 🔹 Ask for input based on the selected function
        prompt_request = "📝 Please enter your prompt:" if interaction.data["custom_id"] == "video_text" else "🖼️ Upload an image and enter a prompt:"
        await interaction.followup.send(prompt_request, ephemeral=True)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)  
            prompt = msg.content
            image_url = None

            # If image + text, check if there's an attachment
            if interaction.data["custom_id"] == "video_image":
                if msg.attachments:
                    image_url = msg.attachments[0].url
                else:
                    await interaction.followup.send("⚠️ Please attach an image along with your text!", ephemeral=True)
                    return

            await msg.delete()  # ✅ Delete user's message after receiving input

        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)  

        url = f"https://example.com/video/{user.id}"
        save_video(user.id, url)

        # 🔹 Send video in DM
        try:
            await user.send(f"🎥 Your video is ready! Click here: {url}")
            await interaction.followup.send("✅ Video sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ I couldn't DM you! Please enable DMs and try again.", ephemeral=True)

    if interaction.data["custom_id"] == "history":
        if not has_access:
            await interaction.followup.send("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return

        history = fetch_video_history(user.id)

        if not history:
            await interaction.followup.send("📜 No history found!", ephemeral=True)
        else:
            history_text = "\n".join([f"📹 {video}" for video in history])
            await user.send(f"📜 **Your Video History:**\n{history_text}")
            await interaction.followup.send("✅ Your history has been sent to DMs!", ephemeral=True)

def save_video(user_id, url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO video_history (user_id, video_url, generated_at) VALUES (?, ?, ?)", (user_id, url, datetime.utcnow()))
    conn.commit()
    conn.close()

def fetch_video_history(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT video_url FROM video_history WHERE user_id = ?", (user_id,))
    history = [row[0] for row in cursor.fetchall()]
    conn.close()
    return history

@bot.event
async def setup_menu(channel):
    embed = discord.Embed(
        title="🎬 Welcome to Kolde AI Video Generator",
        description="Generate AI-powered videos using text or image + prompt.",
        color=discord.Color.dark_blue()
    )
    await channel.send(embed=embed, view=MainMenu())

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    init_db()
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await setup_menu(channel)

bot.run(TOKEN)
