from flask import Flask, request, jsonify
import sqlite3
import os
import discord
import asyncio

app = Flask(__name__)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_ID = 1227708209356345454

intents = discord.Intents.all()
bot = discord.Client(intents=intents)

@app.route("/")
def home():
    return "Kolde AI Webhook is live!"

@app.route("/sellfy", methods=["POST"])
def handle_sellfy():
    data = request.json
    discord_tag = data.get("custom_field")  # Like "User#1234"
    print(f"Received order for: {discord_tag}")

    async def assign_role():
        await bot.wait_until_ready()
        for guild in bot.guilds:
            for member in guild.members:
                if str(member) == discord_tag:
                    role = guild.get_role(ROLE_ID)
                    if role:
                        await member.add_roles(role)
                        add_credits(member.id, 100)
                        try:
                            await member.send("✅ Thanks for purchasing Kolde AI! You’ve been given access + 100 credits.")
                        except:
                            pass
                        return

    asyncio.ensure_future(assign_role())
    return jsonify({"status": "ok"})

def add_credits(user_id, amount):
    conn = sqlite3.connect("credits.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO user_credits (user_id, credits) VALUES (?, ?)", (user_id, 0))
    cursor.execute("UPDATE user_credits SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()