import os
import discord
from discord.ext import commands
import sqlite3
import asyncio
import stripe
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
CHANNEL_ID = 1227704136552939551
ACCESS_ROLE_ID = 1227708209356345454
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

if not TOKEN or not RUNWAY_API_KEY:
    print("❌ ERROR: Missing bot token or API key!")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY
DB_FILE = "credits.db"

CREDIT_COST = 0.4
MIN_CREDITS = 5


def create_checkout_session(user_id):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        success_url="https://kolde-bot.onrender.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://kolde-bot.onrender.com/cancel",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Kolde AI Access"},
                "unit_amount": 299,
            },
            "quantity": 1,
        }],
        metadata={"user_id": user_id, "type": "access"}
    )
    return session.url


def create_credit_purchase_session(user_id, amount):
    quantity = max(amount, MIN_CREDITS)
    unit_amount = int(CREDIT_COST * 100)  # cents
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        success_url="https://kolde-bot.onrender.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://kolde-bot.onrender.com/cancel",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": f"{quantity} Kolde Credits"},
                "unit_amount": unit_amount,
            },
            "quantity": quantity,
        }],
        metadata={"user_id": user_id, "type": "credits", "credit_amount": quantity}
    )
    return session.url


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 0
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


def get_credits(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def add_credits(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_credits (user_id, credits) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET credits = credits + ?", (user_id, amount, amount))
    conn.commit()
    conn.close()


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

def user_has_access(member):
    return any(role.id == ACCESS_ROLE_ID for role in member.roles)

# --- Main Menu ---
class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔓 Login", style=discord.ButtonStyle.blurple, custom_id="login"))
        self.add_item(discord.ui.Button(label="🔒 Get Access", style=discord.ButtonStyle.red, custom_id="get_access"))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link))

# --- Full Function Menu ---
class FullFunctionMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🎥 Video by Text Prompt", style=discord.ButtonStyle.green, custom_id="video_text"))
        self.add_item(discord.ui.Button(label="🖼️ Video by Image + Text", style=discord.ButtonStyle.green, custom_id="video_image"))
        self.add_item(discord.ui.Button(label="📜 View History", style=discord.ButtonStyle.blurple, custom_id="history"))
        self.add_item(discord.ui.Button(label="💳 Buy Credits", style=discord.ButtonStyle.green, custom_id="buy_credits"))
        self.add_item(discord.ui.Button(label="💼 Check Credits", style=discord.ButtonStyle.gray, custom_id="check_credits"))
        self.add_item(discord.ui.Button(label="🔄 Refresh Menu", style=discord.ButtonStyle.gray, custom_id="refresh"))

# --- Payment Menu ---
class PaymentMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="💰 Buy Access", url="https://example.com/buy", style=discord.ButtonStyle.link))

# --- Video Ratio Selection Menu ---
class VideoRatioMenu(discord.ui.View):
    def __init__(self, original_interaction, mode):
        super().__init__(timeout=None)
        self.original_interaction = original_interaction
        self.mode = mode  # "video_text" or "video_image"

        self.add_item(discord.ui.Button(label="16:9", style=discord.ButtonStyle.blurple, custom_id="ratio_16_9"))
        self.add_item(discord.ui.Button(label="9:16", style=discord.ButtonStyle.blurple, custom_id="ratio_9_16"))
        self.add_item(discord.ui.Button(label="1:1", style=discord.ButtonStyle.blurple, custom_id="ratio_1_1"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id) if guild else None
    has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles) if member else False

    await interaction.response.defer()

    if interaction.data["custom_id"] == "get_access":
        session_url = create_checkout_session(user.id)
        await interaction.followup.send(
            "🔒 You need access! Click below to purchase:",
            view=discord.ui.View().add_item(discord.ui.Button(label="💰 Buy Access", style=discord.ButtonStyle.link, url=session_url)),
            ephemeral=True
        )
        return

    if interaction.data["custom_id"] == "login":
        if has_access:
            await interaction.followup.send("✅ You now have access to all functions!", view=FullFunctionMenu(), ephemeral=True)
        else:
            await interaction.followup.send("🔒 You need access! Choose a payment method below:", view=PaymentMenu(), ephemeral=True)
        return

    if interaction.data["custom_id"] == "check_credits":
        credits = get_credits(user.id)
        await interaction.followup.send(f"💼 You have **{credits}** credits.", ephemeral=True)
        return

    if interaction.data["custom_id"] == "buy_credits":
        await interaction.followup.send("💰 Enter how many credits you want to buy (min 5):", ephemeral=True)

        def check(m):
            return m.author.id == user.id and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
            quantity = int(msg.content)
            await msg.delete()
            if quantity < MIN_CREDITS:
                await interaction.followup.send("❌ Minimum is 5 credits.", ephemeral=True)
                return

            session_url = create_credit_purchase_session(user.id, quantity)
            await interaction.followup.send("Click below to purchase your credits:",
                                           view=discord.ui.View().add_item(discord.ui.Button(label="💳 Buy Now", url=session_url)),
                                           ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Invalid input or timeout.", ephemeral=True)

    if interaction.data["custom_id"] in ["video_text", "video_image"]:
        if not has_access:
            await interaction.followup.send("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return

        required_credits = 2 if interaction.data["custom_id"] == "video_image" else 1
        credits = get_credits(user.id)
        if credits < required_credits:
            await interaction.followup.send("⚠️ You don’t have enough credits. Please buy more.", ephemeral=True)
            return

        # Show aspect ratio selection first
        menu = VideoRatioMenu(interaction, interaction.data["custom_id"])  # Use the correct class here
        message = await interaction.followup.send("📐 Choose a video aspect ratio:", view=menu, ephemeral=True)
        menu.message = message
        return

   # Handle aspect ratio selection
if interaction.data["custom_id"].startswith("ratio_"):
    ratio = interaction.data["custom_id"].split("_")[-1]  # Get 16_9, 9_16, or 1_1
    video_type = "video_text" if "text" in interaction.data["custom_id"] else "video_image"

    if video_type == "video_text":
        prompt_request = "📝 Please enter your text prompt:"
    else:  # video_image
        prompt_request = "🖼️ Upload an image and enter a text prompt:"

    await interaction.followup.send(prompt_request, ephemeral=True)

    def check(msg):
        return msg.author == user and msg.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        prompt = msg.content
        image_url = None

        # Only for video_image, check if an image is attached
        if video_type == "video_image":
            if msg.attachments:
                image_url = msg.attachments[0].url
            else:
                await interaction.followup.send("⚠️ Please attach an image along with your text!", ephemeral=True)
                return

        await msg.delete()

    except asyncio.TimeoutError:
        await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
        return

        # Deduct credits
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_credits SET credits = credits - ? WHERE user_id = ?", (required_credits, user.id))
        conn.commit()
        conn.close()

        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)

        url = f"https://example.com/video/{user.id}?ratio={ratio}"
        save_video(user.id, url)

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
            embed = discord.Embed(title="📜 Your Video History", description=history_text, color=discord.Color.blue())
            await interaction.followup.send(embed=embed, ephemeral=True)

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

async def setup_menu(channel):
    embed = discord.Embed(
        title="🎬 Kolde AI",
        description=(
"Kolde AI este primul serviciu romanesc prin care puteti genera videoclip-uri AI!\n"
        "**Functii:**\n"
         "📝 **Video by text prompt:genereaza videoclip-uri folosind o descriere**\n"
         "🖼️ **Video by Image+Text:genereaza videoclip-uri prin intermediul unei imagini+descriere**\n\n"
         "**🛒 Prețuri:**\n" 
         "🔹 **Acces(include 10 credite):** 2.99€\n"
         "🔹 **Credite:** 1 credit = 0.40€\n"
         "🔹 **Video by text:** 1 credit\n"
         "🔹 **Video by image+text:** 2 credit\n\n"
        ),
        color=discord.Color.dark_blue()
    )
    await channel.send(embed=embed, view=MainMenu())
    
async def keep_alive():
    while True:
        print("✅ Bot is running... (Keep-alive)")
        await asyncio.sleep(600)  # Keep active every 10 minutes

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    init_db()
    bot.loop.create_task(keep_alive())  # Keep bot active
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await setup_menu(channel)

@bot.event
async def on_disconnect():
    print("🔴 Bot disconnected! Reconnecting...")
    await asyncio.sleep(5)  # Wait 5 seconds before trying to reconnect

@bot.event
async def on_resumed():
    print("🔄 Reconnected successfully!")

bot.run(TOKEN)
