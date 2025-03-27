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

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id) if guild else None
    has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles) if member else False

    if interaction.data["custom_id"] == "get_access":
        await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

if interaction.data["custom_id"] == "login":
    if has_access:
        await interaction.response.edit_message(view=FullAccessMenu())
    else:
        await interaction.response.send_message("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
    return

    if interaction.data["custom_id"] == "video_text":
        if not has_access:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("📝 Please enter your text prompt:", ephemeral=True)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            prompt = msg.content
            await msg.delete()  # ✅ Delete user's text input
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        # 🔹 Simulate video generation
        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)

        # 🔹 Fake video URL (Replace with real API)
        url = f"https://example.com/video/{user.id}"
        save_video(user.id, url)
        update_credits(user.id, 20)

        # 🔹 Send video link in DM
        try:
            await user.send(f"🎥 Your video is ready! Click here: {url}")
            await interaction.followup.send("✅ Video sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ I couldn't DM you! Please enable DMs and try again.", ephemeral=True)

    if interaction.data["custom_id"] == "video_image_text":
        if not has_access:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("📷 Please upload an image for your video:", ephemeral=True)

        def image_check(msg):
            return msg.author == user and msg.channel == interaction.channel and msg.attachments

        try:
            img_msg = await bot.wait_for("message", check=image_check, timeout=60)
            image_url = img_msg.attachments[0].url
            await img_msg.delete()  # ✅ Delete image upload
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        await interaction.followup.send("📝 Now enter your text prompt for the video:", ephemeral=True)

        def text_check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            text_msg = await bot.wait_for("message", check=text_check, timeout=60)
            text_prompt = text_msg.content
            await text_msg.delete()  # ✅ Delete text prompt after receiving
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        # 🔹 Simulate video generation
        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)

        # 🔹 Fake video URL (Replace with real API)
        url = f"https://example.com/video/{user.id}"
        save_video(user.id, url)
        update_credits(user.id, 20)

        # 🔹 Send video link in DM
        try:
            await user.send(f"🎥 Your video is ready! Click here: {url}")
            await interaction.followup.send("✅ Video sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ I couldn't DM you! Please enable DMs and try again.", ephemeral=True)

@bot.event
async def setup_menu(channel):
    embed = discord.Embed(
        title="🎬 Welcome to Kolde AI Video Generator",
        description=(
            "Generate AI-powered videos using text or image + prompt.\n"
            "**Each generation costs 20 credits**. New users get 100 credits for free!\n\n"
            "💡 *Tips for prompts:* Be specific, include style, mood, and action.\n"
            "🛍️ Buy credits using the red button below.\n"
            "📜 Use the buttons below to interact with the bot."
        ),
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
    else:
        print("❌ ERROR: Channel not found!")

bot.run(TOKEN)
