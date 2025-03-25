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

if not TOKEN or not RUNWAY_API_KEY:
    print("❌ ERROR: Missing bot token or API key!")
    exit(1)

DB_FILE = "credits.db"
ACCESS_ROLE_ID = 1227708209356345454  # Define your access role ID here

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

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Helpers ---
def get_user_credits(user_id):
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_credits SET credits = credits - ? WHERE user_id = ?", (cost, user_id))
    conn.commit()
    conn.close()

def save_video(user_id, url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO video_history (user_id, video_url, generated_at) VALUES (?, ?, ?)",
                   (user_id, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_history(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT video_url, generated_at FROM video_history WHERE user_id = ? ORDER BY generated_at DESC LIMIT 5", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

async def ensure_menu_pinned():
    await bot.wait_until_ready()  # Ensure bot is fully connected
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("❌ ERROR: Channel not found!")
        return

    print(f"✅ Successfully retrieved the channel: {channel.name}")

    async for message in channel.history(limit=10):
        if message.author == bot.user and message.embeds:
            return  # Don't repost if already sent

    embed = discord.Embed(
        title="🎬 Welcome to Kolde AI",
        description="Click below to access the video generation tools.",
        color=discord.Color.orange()
    )
    await channel.send(embed=embed, view=GatekeeperView())

# --- Main Button View ---
class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="📘 Help", url="https://docs.example.com", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://example.com/prompt-guide", style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="🔔 Updates", url="https://example.com/updates", style=discord.ButtonStyle.link))

    @discord.ui.button(label="Generate Video (Text)", style=discord.ButtonStyle.green, custom_id="text_gen")
    async def gen_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✏️ Please enter your video prompt:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            prompt = msg.content
            await msg.delete()

            if get_user_credits(interaction.user.id) < 20:
                await interaction.followup.send("❌ You don't have enough credits!", ephemeral=True)
                return

            await interaction.followup.send("⏳ Generating video from prompt...", ephemeral=True)
            await asyncio.sleep(5)  
            url = f"https://example.com/video/{interaction.user.id}"
            save_video(interaction.user.id, url)
            update_credits(interaction.user.id, 20)
            await interaction.user.send(f"🎥 Your video is ready!\n{url}")
        except asyncio.TimeoutError:
            await interaction.followup.send("⌛ Timed out waiting for prompt!", ephemeral=True)

    @discord.ui.button(label="📜 History", style=discord.ButtonStyle.gray, custom_id="history")
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        vids = get_history(interaction.user.id)
        if not vids:
            await interaction.response.send_message("📭 You haven't generated any videos yet.", ephemeral=True)
        else:
            msg = "\n".join([f"{t} - [Watch Video]({u})" for u, t in vids])
            await interaction.user.send(f"📼 **Your Video History:**\n{msg}")
            await interaction.response.send_message("📩 Sent to your DMs!", ephemeral=True)

# View shown to everyone on first load
class GatekeeperView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

  @discord.ui.button(label="🚪 Open Menu", style=discord.ButtonStyle.green, custom_id="open_menu")
async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
    if not interaction.guild:
        await interaction.response.send_message("❌ This button must be used inside a server.", ephemeral=True)
        return

    # Fetch the role using the stored ID
    role = interaction.guild.get_role(ACCESS_ROLE_ID)
    if not role:
        await interaction.response.send_message("❌ Access role not found. Please contact an admin.", ephemeral=True)
        return

    # Check if the user has the role correctly
    if any(r.id == ACCESS_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message(
            "✅ Access granted! Opening main menu...",
            view=MainMenu(),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "🔒 You need access to unlock video generation tools.",
            view=AccessView(),
            ephemeral=True
        )

# Start the bot
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is now online!")
    await ensure_menu_pinned()

bot.run(TOKEN)
