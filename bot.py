import os
import logging
import asyncio
import re
import aiohttp
import json
from datetime import datetime

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Your Vercel API endpoint

# Channel configuration
CHANNEL_NAMES = {
    1251179699674288208: "SHOCKED",
    1251848915305631834: "VANQUISH", 
    1250885750158000203: "DIGI",
    1323011103894016133: "PASTEL",
    1358931443786584144: "CRYPTIC",
    1256632909008339035: "YOGURTVERSE",
    1319692012261347360: "HEAVEN OR HELL",
    1316031095497818143: "MINTED",
    1392587523838185592: "SERENITY",
    1302921864540323861: "TECHNICAL ALPHA",
    1307140339991183380: "PF TRENCHES",
    1304074398185029632: "POTION",
    1250885751768481849: "PROSPERITY DAO",
    1316784867962519603: "SECRET SOCIETY",
}

# Discord client setup (for user token - NOT RECOMMENDED)
# WARNING: This violates Discord ToS and can result in account ban
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

async def send_to_vercel(message_data):
    """Send message data to Vercel API"""
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL not configured")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WEBHOOK_URL}/api/discord/message",
                json=message_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Message sent to Vercel: {message_data['author_name']}")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send to Vercel: {response.status} - {error_text}")
    except asyncio.TimeoutError:
        logger.error("❌ Timeout sending to Vercel")
    except Exception as e:
        logger.error(f"❌ Error sending to Vercel: {e}")

def format_message_for_api(message: discord.Message) -> dict:
    """Format Discord message for API"""
    
    # Process attachments
    attachments = []
    if message.attachments:
        for attachment in message.attachments:
            is_image = (
                attachment.content_type and attachment.content_type.startswith('image/') or
                attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))
            )
            attachments.append({
                "filename": attachment.filename,
                "url": attachment.url,
                "is_image": is_image,
                "size": attachment.size
            })

    # Clean content
    cleaned_content = message.content or ""
    if cleaned_content:
        # Remove ** around @mentions
        cleaned_content = re.sub(r'\*\*(@[^*]+)\*\*', r'\1', cleaned_content)

    # Handle replies
    reply_info = None
    if message.reference and message.reference.message_id:
        try:
            replied_message = message.reference.resolved
            if replied_message:
                replied_content = replied_message.content[:50] + "..." if len(replied_message.content) > 50 else replied_message.content
                reply_info = {
                    "author": replied_message.author.display_name,
                    "content": replied_content
                }
        except:
            reply_info = {"author": "Unknown", "content": "Message not found"}

    return {
        "channel_id": str(message.channel.id),
        "author_name": message.author.display_name,
        "author_avatar": str(message.author.display_avatar.url) if message.author.display_avatar else None,
        "content": cleaned_content,
        "timestamp": message.created_at.isoformat(),
        "message_id": str(message.id),
        "attachments": attachments,
        "reply": reply_info
    }

@discord_client.event
async def on_ready():
    logger.info(f'🤖 Discord client logged in as {discord_client.user}')
    logger.info(f'🔗 Connected to {len(discord_client.guilds)} guilds')
    logger.info(f'🎯 Monitoring {len(CHANNEL_NAMES)} channels')
    logger.info(f'📡 Webhook URL configured: {bool(WEBHOOK_URL)}')
    logger.info(f'📡 Webhook URL: {WEBHOOK_URL}')
    
    # Send startup notification to all channels
    for guild in discord_client.guilds:
        logger.info(f'🏠 Guild: {guild.name} ({guild.id})')
        for channel_id in CHANNEL_NAMES.keys():
            channel = guild.get_channel(channel_id)
            if channel:
                logger.info(f'✅ Found channel: #{channel.name} ({channel_id})')
            else:
                logger.warning(f'❌ Channel not found: {channel_id} ({CHANNEL_NAMES[channel_id]})')

@discord_client.event
async def on_message(message):
    # Don't process own messages (important for user tokens)
    if message.author == discord_client.user:
        return
    
    # Don't process other bot messages
    if message.author.bot:
        return
    
    # Check if message is in a monitored channel
    if message.channel.id not in CHANNEL_NAMES:
        return
    
    # Skip messages from Rick
    if message.author.display_name.lower() == "rick":
        logger.info(f"⏭️ Skipping message from Rick")
        return
    
    # Filter Discord promotional content
    if message.content:
        content_lower = message.content.lower()
        discord_keywords = [
            "go to mention", "[go to mention]", "discord.com/channels/",
            "referenced message", "[referenced message]"
        ]
        
        if any(keyword in content_lower for keyword in discord_keywords):
            logger.info(f"🚫 Blocked promotional content")
            return
    
    # Format and send message to Vercel
    try:
        message_data = format_message_for_api(message)
        await send_to_vercel(message_data)
        
        logger.info(f"📤 Processed message from #{message.channel.name}: {message.author.display_name} - {message.content[:50]}...")
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")

@discord_client.event
async def on_error(event, *args, **kwargs):
    logger.error(f'❌ Discord error in {event}: {args[0] if args else "Unknown"}')

# Health check endpoint (for Render)
from aiohttp import web

async def health_check(request):
    return web.json_response({
        "status": "healthy",
        "client_ready": discord_client.is_ready(),
        "guilds": len(discord_client.guilds) if discord_client.is_ready() else 0,
        "webhook_configured": bool(WEBHOOK_URL),
        "webhook_url": WEBHOOK_URL,
        "monitored_channels": len(CHANNEL_NAMES),
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        "user": str(discord_client.user) if discord_client.user else "Not logged in"
    })

async def start_web_server():
    """Start a simple web server for health checks"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)  # Also respond to root
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Health check server started on port {port}")

async def main():
    """Main function to run both Discord client and web server"""
    logger.info(f"🐍 Python version: {os.sys.version}")
    
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN environment variable not set")
        return
    
    if not WEBHOOK_URL:
        logger.error("❌ WEBHOOK_URL environment variable not set")
        return
    
    logger.warning("⚠️ WARNING: Using user token violates Discord ToS and may result in account ban!")
    
    # Validate token format (user tokens should be longer and not start with Bot)
    if DISCORD_TOKEN.startswith('Bot '):
        logger.error("❌ This appears to be a bot token. Please use a user account token.")
        return
    
    # Start web server for health checks
    await start_web_server()
    
    # Start Discord client with user token
    try:
        logger.info("🚀 Starting Discord client...")
        logger.info(f"🔑 Token starts with: {DISCORD_TOKEN[:10]}...")
        await discord_client.start(DISCORD_TOKEN, bot=False)  # bot=False for user tokens
    except discord.LoginFailure:
        logger.error("❌ Invalid token. Please check your DISCORD_TOKEN environment variable.")
        logger.error("💡 Make sure you're using a user account token, not a bot token.")
    except Exception as e:
        logger.error(f"❌ Failed to start Discord client: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Client stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

import sys
