from flask import Flask, request, jsonify
import stripe
import os
import discord
import asyncio

app = Flask(__name__)

# Load environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

stripe.api_key = STRIPE_SECRET_KEY

# Discord Bot Setup
intents = discord.Intents.default()
bot = discord.Client(intents=intents)

ACCESS_ROLE_ID = 1227708209356345454  # Replace with your Discord role ID
GUILD_ID = 1227704136552939551  # Replace with your Discord server ID

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return "Webhook signature verification failed", 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])

        asyncio.run_coroutine_threadsafe(grant_access(user_id), bot.loop)

    return jsonify(success=True)

async def grant_access(user_id):
    """Grants the Discord role to the user after payment."""
    guild = bot.get_guild(GUILD_ID)
    if guild:
        member = guild.get_member(user_id)
        if member:
            role = guild.get_role(ACCESS_ROLE_ID)
            if role:
                await member.add_roles(role)
                print(f"✅ Granted access role to {member.name}")

if __name__ == '__main__':
    bot.loop.create_task(bot.start(DISCORD_TOKEN))  # Start Discord bot in async loop
    app.run(host="0.0.0.0", port=10000)  # Make sure it runs on Render
