# main.py
import os
import time
import logging
import requests
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
from python_aternos import Client

# -------------------------
# Config / Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------
# Flask keep-alive (Render)
# -------------------------
app = Flask("")

@app.route("/")
def home():
    return "I'm alive!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

# -------------------------
# Environment variables
# -------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ATERNOS_USER = os.getenv("ATERNOS_USER")
ATERNOS_PASS = os.getenv("ATERNOS_PASS")

ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")            # required
ZENROWS_URL = os.getenv("ZENROWS_URL", "https://api.zenrows.com/v1/")

# Basic checks
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN is not set. Exiting.")
    raise ValueError("Set DISCORD_TOKEN environment variable.")
if not ZENROWS_API_KEY:
    logger.error("ZENROWS_API_KEY is not set. Exiting.")
    raise ValueError("Set ZENROWS_API_KEY environment variable.")
if not ATERNOS_USER or not ATERNOS_PASS:
    logger.error("ATERNOS_USER or ATERNOS_PASS missing. Set both env vars.")
    raise ValueError("Set ATERNOS_USER and ATERNOS_PASS environment variables.")

# -------------------------
# Discord bot setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# Aternos client
# -------------------------
atclient = Client()
server = None   # cached server object after login

# -------------------------
# ZenRows helper: get cookies (single call)
# -------------------------
def get_aternos_cookies_with_zenrows(retries=2, delay=3, timeout=60):
    """
    Ask ZenRows to fetch https://aternos.org/login and return a dict of cookies
    suitable for requests.Session().cookies.update().
    Minimize retries to conserve your free quota.
    """
    params = {
        "apikey": ZENROWS_API_KEY,
        "url": "https://aternos.org/login",
        "js_render": "true",
        "premium_proxy": "true"
    }

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"ZenRows attempt {attempt}/{retries}...")
            resp = requests.get(ZENROWS_URL, params=params, timeout=timeout)
            resp.raise_for_status()

            # Try parse JSON
            data = None
            try:
                data = resp.json()
            except ValueError:
                logger.warning(f"ZenRows returned non-JSON response (len={len(resp.text)})")
                data = None

            # Pattern 1: direct "cookies" array
            if isinstance(data, dict):
                if "cookies" in data and isinstance(data["cookies"], list):
                    cookie_list = data["cookies"]
                    cookie_dict = {c["name"]: c["value"] for c in cookie_list if "name" in c and "value" in c}
                    if cookie_dict:
                        logger.info("ZenRows: found cookies in data['cookies'].")
                        return cookie_dict

                # Pattern 2: nested solution/response/result/data
                for candidate in ("solution", "response", "result", "data"):
                    if candidate in data and isinstance(data[candidate], dict):
                        cand = data[candidate]
                        if "cookies" in cand and isinstance(cand["cookies"], list):
                            cookie_list = cand["cookies"]
                            cookie_dict = {c["name"]: c["value"] for c in cookie_list if "name" in c and "value" in c}
                            if cookie_dict:
                                logger.info(f"ZenRows: found cookies in data['{candidate}']['cookies'].")
                                return cookie_dict

            # Pattern 3: Set-Cookie header
            set_cookie = resp.headers.get("Set-Cookie")
            if set_cookie:
                parts = set_cookie.split(";")
                if parts and "=" in parts[0]:
                    k, v = parts[0].split("=", 1)
                    logger.info("ZenRows: found cookie in Set-Cookie header.")
                    return {k.strip(): v.strip()}

            logger.warning("ZenRows: no cookies found in response.")
        except requests.exceptions.RequestException as e:
            logger.warning(f"ZenRows HTTP error attempt {attempt}: {e}")

        if attempt < retries:
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)

    logger.error("ZenRows: failed to obtain cookies after retries.")
    return None

# -------------------------
# Login helper: only called when a command needs Aternos
# -------------------------
def ensure_logged_in_via_zenrows():
    """
    Ensure we have a logged-in 'server'. Returns True if server is available.
    Calls ZenRows once (with minimal retries) only when needed.
    """
    global server
    if server:
        return True

    logger.info("No cached Aternos session — obtaining cookies via ZenRows...")
    cookies = get_aternos_cookies_with_zenrows()
    if not cookies:
        logger.warning("Could not obtain cookies from ZenRows.")
        return False

    # Inject cookies then perform library login
    try:
        atclient.atconn.session.cookies.update(cookies)
        atclient.login(ATERNOS_USER, ATERNOS_PASS)
        aternos = atclient.account
        servers = aternos.list_servers()
        if servers:
            server = servers[0]
            logger.info(f"Aternos login successful. Server cached: {server.name}")
            return True
        else:
            logger.warning("Aternos login succeeded but no servers found.")
            server = None
            return False
    except Exception as e:
        logger.error(f"Aternos login error after ZenRows: {e}")
        server = None
        return False

# -------------------------
# Commands (each ensures login first)
# -------------------------
@bot.command()
async def startserver(ctx):
    await ctx.send("🔄 Attempting to start server...")
    if not ensure_logged_in_via_zenrows():
        await ctx.send("❌ Failed to login to Aternos. Try `!retrycookie` or check logs.")
        return

    try:
        server.start()
        await ctx.send("✅ Server start command sent. It may take a few minutes to come online.")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        await ctx.send(f"❌ Error starting server: {e}")

@bot.command()
async def stopserver(ctx):
    await ctx.send("🔄 Attempting to stop server...")
    if not ensure_logged_in_via_zenrows():
        await ctx.send("❌ Failed to login to Aternos. Try `!retrycookie` or check logs.")
        return

    try:
        server.stop()
        await ctx.send("✅ Server stop command sent.")
    except Exception as e:
        logger.error(f"Error stopping server: {e}")
        await ctx.send(f"❌ Error stopping server: {e}")

@bot.command()
async def status(ctx):
    if not ensure_logged_in_via_zenrows():
        await ctx.send("❌ Failed to login to Aternos. Try `!retrycookie` or check logs.")
        return

    try:
        server.fetch()
        players = getattr(server, "players", "N/A")
        await ctx.send(f"🖥️ Server status: **{server.status}** | Players: **{players}**")
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        await ctx.send(f"❌ Error fetching status: {e}")

@bot.command()
async def retrycookie(ctx):
    """Force a fresh ZenRows request and re-login (use only when necessary)."""
    await ctx.send("🔄 Forcing cookie refresh via ZenRows...")
    # drop cached server so ensure_logged_in_via_zenrows will re-run
    global server
    server = None
    if ensure_logged_in_via_zenrows():
        await ctx.send(f"✅ Re-login successful. Server: {server.name}")
    else:
        await ctx.send("❌ Re-login failed. Check logs and ZenRows quota.")

# -------------------------
# Run bot
# -------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
