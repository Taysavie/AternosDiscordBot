import os
import discord
from discord.ext import commands, tasks
from python_aternos import Client
from flask import Flask
from threading import Thread
import requests
import logging
import time

# -------------------------
# Logging setup
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------------
# Flask keep-alive
# -------------------------
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run_flask():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_flask).start()

# -------------------------
# Environment variables
# -------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ATERNOS_USER = os.getenv("ATERNOS_USER")
ATERNOS_PASS = os.getenv("ATERNOS_PASS")
FLARE_URL = os.getenv("FLARE_URL")

if not DISCORD_TOKEN or not ATERNOS_USER or not ATERNOS_PASS or not FLARE_URL:
    logger.error("Missing required environment variables!")
    raise ValueError("Set DISCORD_TOKEN, ATERNOS_USER, ATERNOS_PASS, FLARE_URL.")

# -------------------------
# Discord bot setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# FlareSolverr helper with retry
# -------------------------
def get_aternos_cookies(retries=3, delay=5):
    payload = {
        "cmd": "request.get",
        "url": "https://aternos.org/login",
        "maxTimeout": 120000  # 2 minutes
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(f"{FLARE_URL}/v1", json=payload, timeout=150)
            resp.raise_for_status()
            data = resp.json()

            if 'solution' in data and 'cookies' in data['solution']:
                cookies = data['solution']['cookies']
                cookie_dict = {c['name']: c['value'] for c in cookies}
                logger.info(f"✅ Obtained cookies from FlareSolverr on attempt {attempt}.")
                return cookie_dict
            else:
                logger.warning(f"⚠️ Attempt {attempt}: FlareSolverr returned invalid data: {data}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Attempt {attempt}: HTTP request failed: {e}")
        except ValueError as e:
            logger.warning(f"⚠️ Attempt {attempt}: Failed to parse JSON: {e}")

        if attempt < retries:
            logger.info(f"⏳ Retrying in {delay} seconds...")
            time.sleep(delay)

    logger.error(f"❌ Failed to get cookies from FlareSolverr after {retries} attempts.")
    return None

# -------------------------
# Aternos client setup
# -------------------------
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
                logger.info(f"✅ Logged in to Aternos. Server: {server.name}")
            else:
                logger.warning("⚠️ No servers found on Aternos account.")
        else:
            logger.warning("⚠️ Could not obtain cookies, Aternos login skipped.")
    except Exception as e:
        logger.error(f"❌ Aternos login error: {e}")
        server = None

# -------------------------
# Discord status update
# -------------------------
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
    except Exception as e:
        await bot.change_presence(activity=discord.Game(name="Server status unknown"))
        logger.warning(f"Error updating status: {e}")

# -------------------------
# Discord events & commands
# -------------------------
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")
    try:
        login_aternos()
    except Exception as e:
        logger.warning(f"Aternos login failed at startup: {e}")
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
        logger.error(f"Error starting server: {e}")

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
        logger.error(f"Error fetching status: {e}")

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
        logger.error(f"Error stopping server: {e}")

@bot.command()
async def retryflare(ctx):
    """Manually retry FlareSolverr and Aternos login."""
    await ctx.send("🔄 Retrying FlareSolverr...")
    logger.info("Manual retry triggered via Discord command.")

    try:
        cookies = get_aternos_cookies()
        if not cookies:
            await ctx.send("❌ Failed to get cookies from FlareSolverr.")
            return

        atclient.atconn.session.cookies.update(cookies)
        atclient.login(ATERNOS_USER, ATERNOS_PASS)
        aternos = atclient.account
        servers = aternos.list_servers()
        global server
        if servers:
            server = servers[0]
            await ctx.send(f"✅ FlareSolverr retry successful! Server: {server.name}")
            logger.info(f"✅ FlareSolverr retry successful. Server: {server.name}")
            # Restart status updater to refresh immediately
            update_discord_status.restart()
        else:
            server = None
            await ctx.send("⚠️ No servers found on Aternos account.")
            logger.warning("No servers found after manual retry.")
    except Exception as e:
        await ctx.send(f"❌ Error during FlareSolverr retry: {e}")
        logger.error(f"Error during FlareSolverr retry: {e}")

# -------------------------
# Run bot
# -------------------------
bot.run(DISCORD_TOKEN)
