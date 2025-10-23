# Discord Aternos Bot

## Overview
A Discord bot that manages an Aternos Minecraft server through Discord commands. Users can start, stop, and check the status of their Minecraft server directly from Discord. A Flask web server runs alongside to keep the bot alive on Replit.

## Features
- **Server Control**: Start and stop Aternos Minecraft servers via Discord commands
- **Status Monitoring**: Check current server status
- **Keep-Alive Server**: Flask web server on port 8080 to prevent Replit from sleeping

## Commands
- `!startserver` - Starts the Aternos Minecraft server
- `!stopserver` - Stops the Aternos Minecraft server  
- `!status` - Shows current server status

## Project Structure
- `main.py` - Main bot file with Discord commands and Aternos integration
- `pyproject.toml` - Python dependencies
- `.gitignore` - Git ignore file for Python projects

## Environment Variables Required
- `DISCORD_TOKEN` - Discord bot token from Discord Developer Portal
- `ATERNOS_USER` - Aternos account username/email
- `ATERNOS_PASS` - Aternos account password

## Technical Stack
- **Discord.py** - Discord API wrapper for bot functionality
- **python-aternos** - Python wrapper for Aternos API
- **Flask** - Lightweight web framework for keep-alive server
- **Threading** - Run Flask and Discord bot concurrently

## Recent Changes
- Initial project setup (October 23, 2025)
- Installed Python 3.11 and required dependencies
- Created Discord bot with server control commands
- Configured Flask keep-alive server on port 8080
