import os
import discord
from discord.ext import commands, tasks
from python_aternos import Client
from flask import Flask
from threading import Thread

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
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")

if not DISCORD_TOKEN or not ATERNOS_SESSION:
    raise ValueError("Missing required environment variables. Please set DISCORD_TOKEN and ATERNOS_SESSION.")

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Aternos client using cookie ---
atclient = Client()
atclient.login_cookie(ATERNOS_SESSION)
aternos = atclient.account
servers = aternos.list_servers()

if not servers:
    raise ValueError("No Aternos servers found. Please create a server on Aternos first.")

server = servers[0]

# --- Function to update Discord status ---
@tasks.loop(minutes=1)
async def update_discord_status():
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
        print(f"Error updating status: {e}")

# --- Events & Commands ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    update_discord_status.start()

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
        players = getattr(server, "players", "N/A")
        await ctx.send(f"🖥️ Server status: **{server.status}** | Players: **{players}**")
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

# --- Run bot ---
bot.run(DISCORD_TOKEN)
