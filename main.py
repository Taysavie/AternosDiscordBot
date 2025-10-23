import os
import discord
from discord.ext import commands
from python_aternos import Client
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ATERNOS_USER = os.getenv("ATERNOS_USER")
ATERNOS_PASS = os.getenv("ATERNOS_PASS")

if not DISCORD_TOKEN or not ATERNOS_USER or not ATERNOS_PASS:
    raise ValueError("Missing required environment variables. Please set DISCORD_TOKEN, ATERNOS_USER, and ATERNOS_PASS.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

atclient = Client()
atclient.login(ATERNOS_USER, ATERNOS_PASS)
aternos = atclient.account
servers = aternos.list_servers()

if not servers:
    raise ValueError("No Aternos servers found. Please create a server on Aternos first.")

server = servers[0]

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def startserver(ctx):
    await ctx.send("⏳ Starting your Aternos server...")
    try:
        server.start()
        await ctx.send("✅ Server start command sent! It may take a few minutes to come online.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def status(ctx):
    try:
        server.fetch()
        await ctx.send(f"🖥️ Server status: **{server.status}**")
    except Exception as e:
        await ctx.send(f"❌ Error getting status: {e}")

@bot.command()
async def stopserver(ctx):
    await ctx.send("🛑 Stopping server...")
    try:
        server.stop()
        await ctx.send("✅ Server stopped.")
    except Exception as e:
        await ctx.send(f"❌ Error stopping server: {e}")

bot.run(DISCORD_TOKEN)
