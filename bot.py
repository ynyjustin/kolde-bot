import os
import discord
from discord.ext import commands
import asyncio
import stripe
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
CHANNEL_ID = 1227704136552939551
ACCESS_ROLE_ID = 1227708209356345454
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not TOKEN or not RUNWAY_API_KEY:
    print("❌ ERROR: Missing bot token or API key!")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def get_credits(user_id):
    response = supabase.table("user_credits").select("credits").eq("user_id", user_id).execute()
    if response.data:
        return response.data[0]["credits"]
    return 0

def add_credits(user_id, amount):
    current = get_credits(user_id)
    if current:
        supabase.table("user_credits").update({"credits": current + amount}).eq("user_id", user_id).execute()
    else:
        supabase.table("user_credits").insert({"user_id": user_id, "credits": amount}).execute()

def deduct_credits(user_id, amount):
    current = get_credits(user_id)
    if current >= amount:
        supabase.table("user_credits").update({"credits": current - amount}).eq("user_id", user_id).execute()
        return True
    return False

def save_video(user_id, url):
    supabase.table("video_history").insert({"user_id": user_id, "video_url": url, "generated_at": datetime.utcnow().isoformat()}).execute()

def fetch_video_history(user_id):
    response = supabase.table("video_history").select("video_url").eq("user_id", user_id).order("generated_at", desc=True).limit(10).execute()
    return [entry["video_url"] for entry in response.data]

def generate_video(prompt, ratio, image_url=None):
    try:
        response = requests.post(
            "API_URL",
            json={"prompt": prompt, "ratio": ratio, "image_url": image_url},
            timeout=30  # Avoid infinite waiting
        )
        response.raise_for_status()  # Raise exception for HTTP errors

        data = response.json()
        return data.get("video_url")  # Ensure this key exists

    except requests.exceptions.RequestException as e:
        print(f"⚠️ API Error: {e}")
        return None
    
    # Default parameters based on the API documentation
    payload = {
        "text_prompt": prompt,  # The required text prompt
        "model": "gen3",  # Default to 'gen3' model (can be changed)
        "width": 1344,  # Default video width
        "height": 768,  # Default video height
        "motion": 5,  # Default motion intensity (won't be used by Gen3 Alpha)
        "seed": 0,  # Random seed (0 means random)
        "callback_url": None,  # You can provide a callback URL if needed
        "time": 5  # Default video time
    }
    
    # If you want to use a custom image, include it in the payload (optional)
    if image_url:
        payload["image_url"] = image_url

    # Ensure the aspect_ratio is passed properly, adjusting width/height accordingly
    if aspect_ratio == "16:9":
        payload["width"] = 1344
        payload["height"] = 768
    elif aspect_ratio == "9:16":
        payload["width"] = 768
        payload["height"] = 1344
    elif aspect_ratio == "1:1":
        payload["width"] = 768
        payload["height"] = 768

    # Send POST request to the API
    url = "https://api.aivideoapi.com/runway/generate/text"
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        video_url = data.get("video_url")  # Assuming the response contains the video URL
        return video_url
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None

def init_db():
    try:
        # Supabase doesn't support table creation via client, so just validate with a test query
        # Optional: Insert dummy rows to ensure the table structure works

        # Test user_credits table
        supabase.table("user_credits").select("user_id, credits").limit(1).execute()

        # Test video_history table
        supabase.table("video_history").select("user_id, video_url, generated_at").limit(1).execute()

        print("✅ Tables are accessible and seem to exist.")
    except Exception as e:
        print("❌ Error accessing Supabase tables! Make sure 'user_credits' and 'video_history' exist.")
        print(e)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Main Menu ---
class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔓 Login", style=discord.ButtonStyle.blurple, custom_id="login"))
        self.add_item(discord.ui.Button(label="🔒 Get Access", style=discord.ButtonStyle.red, custom_id="get_access"))
        self.add_item(discord.ui.Button(label="📄 Prompt Guide", url="https://docs.google.com/document/d/13oxxQQvtHuHqdvIv5i6yIOgGldXGQk9AuGAeUiTlM4o/edit?usp=sharing", style=discord.ButtonStyle.link))

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
    def __init__(self, interaction: discord.Interaction, video_type: str):
        super().__init__(timeout=60)
        self.add_item(RatioButton("16:9", f"ratio_16_9_{video_type}"))
        self.add_item(RatioButton("9:16", f"ratio_9_16_{video_type}"))
        self.add_item(RatioButton("1:1", f"ratio_1_1_{video_type}"))

class RatioButton(discord.ui.Button):
    def __init__(self, label: str, custom_id: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done:  # Remove the await
            await interaction.response.defer(ephemeral=True)
        
import discord
import asyncio

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id) if guild else None
    has_access = any(role.id == ACCESS_ROLE_ID for role in member.roles) if member else False

    custom_id = interaction.data.get("custom_id", "")

    print(f"Interaction received: {custom_id}")  # Debugging

    defer_needed = custom_id in ["video_text", "video_image", "ratio_16_9", "ratio_9_16", "check_credits", "history"]

    if defer_needed and not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            print("Interaction expired before deferring.")
            return

    if custom_id == "get_access":
        session_url = create_checkout_session(user.id)
        await interaction.response.send_message(
            "🔒 You need access! Click below to purchase:",
            view=discord.ui.View().add_item(
                discord.ui.Button(label="💰 Buy Access", style=discord.ButtonStyle.link, url=session_url)
            ),
            ephemeral=True
        )
        return

    if custom_id == "login":
        await interaction.response.send_message(
            "✅ You now have access to all functions!" if has_access else "🔒 You need access! Choose a payment method below:",
            view=FullFunctionMenu() if has_access else PaymentMenu(),
            ephemeral=True
        )
        return

    if custom_id == "check_credits":
        credits = get_credits(user.id)
        await interaction.followup.send(f"💼 You have **{credits}** credits.", ephemeral=True)
        return

    if custom_id == "buy_credits":
        await interaction.response.send_message("💰 Enter how many credits you want to buy (min 5):", ephemeral=True)
        
        def check(m):
            return m.author.id == user.id and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
            quantity = int(msg.content)

            try:
                await msg.delete()
            except discord.NotFound:
                print("Message already deleted or not found.")

            if quantity < MIN_CREDITS:
                await interaction.followup.send("❌ Minimum is 5 credits.", ephemeral=True)
                return

            session_url = create_credit_purchase_session(user.id, quantity)
            await interaction.followup.send(
                "Click below to purchase your credits:",
                view=discord.ui.View().add_item(discord.ui.Button(label="💳 Buy Now", url=session_url)),
                ephemeral=True
            )
        except Exception:
            await interaction.followup.send("❌ Invalid input or timeout.", ephemeral=True)
        return

    if custom_id in ["video_text", "video_image"]:
        if not has_access:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return

        required_credits = 2 if custom_id == "video_image" else 1
        credits = get_credits(user.id)
        if credits < required_credits:
            await interaction.followup.send("⚠️ You don’t have enough credits. Please buy more.", ephemeral=True)
            return

        print(f"User selecting aspect ratio for {custom_id}")

        menu = VideoRatioMenu(interaction, custom_id)
        await interaction.followup.send("📐 Choose a video aspect ratio:", view=menu, ephemeral=True)
        return

    if custom_id.startswith("ratio_"):
        parts = custom_id.split("_")
        if len(parts) < 3:
            await interaction.followup.send("⚠️ Invalid selection!", ephemeral=True)
            return

        ratio = f"{parts[1]}_{parts[2]}"
        video_type = "video_text" if "video_text" in custom_id else "video_image"

        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.errors.NotFound:
                print("Interaction expired before deferring.")
                return

        prompt_request = "📝 Please enter your text prompt:" if video_type == "video_text" else "🖼️ Upload an image and enter a text prompt:"
        await interaction.followup.send(prompt_request, ephemeral=True)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            prompt = msg.content
            image_url = msg.attachments[0].url if video_type == "video_image" and msg.attachments else None

            if video_type == "video_image" and not image_url:
                await interaction.followup.send("⚠️ Please attach an image along with your text!", ephemeral=True)
                return

            try:
                await msg.delete()
            except discord.NotFound:
                print("Message already deleted or not found.")

        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Timeout! Please try again.", ephemeral=True)
            return

        required_credits = 2 if video_type == "video_image" else 1
        deduct_credits(user.id, required_credits)

        print(f"Generating video with prompt: {prompt}, ratio: {ratio}, image_url: {image_url}")
        await interaction.followup.send("⏳ Generating your video...", ephemeral=True)
        await asyncio.sleep(5)

        video_url = generate_video(prompt, ratio, image_url)
        print(f"Generated video URL: {video_url}")

        if not video_url:
            await interaction.followup.send("❌ Failed to generate video. Please try again later.", ephemeral=True)
            return

        save_video(user.id, video_url)

        try:
            await user.send(f"🎥 Your video is ready! Click here: {video_url}")
            await interaction.followup.send("✅ Video sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"🎥 Your video is ready! Click here: {video_url}", ephemeral=True)

    if custom_id == "history":
        if not has_access:
            await interaction.response.send_message("🔒 You need access!", view=PaymentMenu(), ephemeral=True)
            return

        history = fetch_video_history(user.id)
        history_text = "\n".join([f"📹 {video}" for video in history]) if history else "📜 No history found!"
        embed = discord.Embed(title="📜 Your Video History", description=history_text, color=discord.Color.blue())
        await interaction.followup.send(embed=embed, ephemeral=True)
            
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

@bot.command(name="add_credits")
@commands.has_permissions(administrator=True)
async def add_credits_command(ctx, member: discord.Member, amount: int):
    add_credits(member.id, amount)
    await ctx.send(f"✅ Added {amount} credits to {member.mention}.")

@bot.command(name="remove_credits")
@commands.has_permissions(administrator=True)
async def remove_credits_command(ctx, member: discord.Member):
    supabase.table("user_credits").delete().eq("user_id", member.id).execute()
    await ctx.send(f"🗑️ Removed all credits for {member.mention}.")

@bot.command(name="check_credits")
async def check_credits_command(ctx, member: discord.Member = None):
    user = member or ctx.author
    credits = get_credits(user.id)
    await ctx.send(f"💰 {user.mention} has **{credits}** credits.")

@bot.command(name="list_credits")
@commands.has_permissions(administrator=True)
async def list_credits(ctx):
    result = supabase.table("user_credits").select("*").execute()
    if result.data:
        lines = [f"{row['user_id']}: {row['credits']} credits" for row in result.data]
        await ctx.send("🧾 **All users & credits:**\n" + "\n".join(lines))
    else:
        await ctx.send("❌ No credit records found.")

@bot.command(name="post_tos")
@commands.has_permissions(administrator=True)
async def post_tos(ctx):
    embed = discord.Embed(
        title="📜 Termeni și Condiții – Kolde AI",
        description=(
            "**🔒 Plăți & Securitate**\n"
            "- Toate plățile sunt procesate prin Stripe – o platformă securizată și global recunoscută.\n"
            "- Nu stocăm detalii ale cardurilor sau informații bancare.\n\n"
            "**💸 Politica de Rambursare**\n"
            "- Rambursările sunt disponibile doar în cazul unei erori tehnice majore.\n"
            "- Creditele consumate nu pot fi returnate.\n\n"
            "**🛠️ Funcționalități**\n"
            "- Generare video AI pe bază de text sau imagine + text.\n"
            "- Istoric video personal și sistem de creditare.\n\n"
            "**📈 Prețuri**\n"
            "- Acces: 2.99€ (include 10 credite).\n"
            "- Credit: 0.40€/credit.\n"
            "- Video text: 1 credit | Video imagine+text: 2 credite.\n\n"
            "**📌 Alte Detalii**\n"
            "- Kolde AI este un serviciu experimental.\n"
            "- Accesul poate fi revocat în caz de abuz sau spam.\n"
            "- Prin utilizare, ești de acord cu acești termeni."
        ),
        color=discord.Color.orange()
    )
    embed.set_footer(text="Ultima actualizare: Martie 2025")

    await ctx.send(embed=embed)

bot.run(TOKEN)
