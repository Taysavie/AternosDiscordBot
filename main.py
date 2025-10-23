import os
import discord
from discord.ext import commands, tasks
from python_aternos import Client, AternosError
from flask import Flask
from threading import Thread
import requests

# --- Keep bot alive ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

# --- Environment variables ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ATERNOS_USER = os.getenv("ATERNOS_USER")
ATERNOS_PASS = os.getenv("ATERNOS_PASS")
FLARE_URL = os.getenv("FLARE_URL")

if not DISCORD_TOKEN or not ATERNOS_USER or not ATERNOS_PASS or not FLARE_URL:
    raise ValueError("Missing environment variables. Set DISCORD_TOKEN, ATERNOS_USER, ATERNOS_PASS, FLARE_URL.")

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Function to get cookies from FlareSolverr ---
def get_aternos_cookies():
    payload = {
        "cmd": "request.get",
        "url": "https://aternos.org/login",
        "maxTimeout": 60000
    }
    try:
        resp = requests.post(f"{FLARE_URL}/v1", json=payload, timeout=60).json()
        cookies = resp['solution']['cookies']
        cookie_dict = {c['name']: c['value'] for c in cookies}
        return cookie_dict
    except Exception as e:
        print(f"❌ Error getting cookies from FlareSolverr: {e}")
        return None

# --- Aternos client setup ---
atclient = Client()
server = None

def login_aternos():
    global server
    try:
        cookies = get_aternos_cookies()
        if cookies:
            atclient.atconn.session.cookies.update(cookies)
            atclient.login(ATERNOS_USER, ATERNOS_PASS)
            aternos = atclient.account
            servers = aternos.list_servers()
            if servers:
                server = servers[0]
                print(f"✅ Logged in to Aternos, server: {server.name}")
            else:
                print("⚠️ No servers found on Aternos account.")
        else:
            print("⚠️ Failed to get cookies from FlareSolverr.")
    except AternosError as e:
        print(f"❌ Aternos login error: {e}")

# --- Function to update Discord status ---
@tasks.loop(minutes=1)
async def update_discord_status():
    if not server:
        await bot.change_presence(activity=discord.Game(name="Aternos unavailable"))
        return
    try:
        server.fetch()
        status = server.status
        players = getattr(server, "players", None)
        if players is not None:
            activity_text = f"{status.capitalize()} - {players} players"
        else:
            activity_text = f"{status.capitalize()}"
        await bot.change_presence(activity=discord.Game(name=activity_text))
    except Exception:
        await bot.change_presence(activity=discord.Game(name="Server status unknown"))

# --- Discord events & commands ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    login_aternos()
    update_discord_status.start()

@bot.command()
async def startserver(ctx):
    if not server:
        await ctx.send("⚠️ Aternos server unavailable.")
        return
    await ctx.send("⏳ Starting server...")
    try:
        server.start()
        await ctx.send("✅ Server start command sent!")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def status(ctx):
    if not server:
        await ctx.send("⚠️ Aternos server unavailable.")
        return
    try:
        server.fetch()
        players = getattr(server, "players", "N/A")
        await ctx.send(f"🖥️ Server status: **{server.status}** | Players: **{players}**")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def stopserver(ctx):
    if not server:
        await ctx.send("⚠️ Aternos server unavailable.")
        return
    await ctx.send("🛑 Stopping server...")
    try:
        server.stop()
        await ctx.send("✅ Server stopped.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# --- Run bot ---
bot.run(DISCORD_TOKEN)
