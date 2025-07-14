import os
import logging
import asyncio
import re
import aiohttp
import json
from datetime import datetime

import discord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Your Vercel API endpoint
GUILD_ID = os.getenv('GUILD_ID')  # Optional: Specific Discord Server ID to monitor

# Channel configuration - ONLY these channels will be monitored
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

# Discord client setup
discord_client = discord.Client()

async def send_to_vercel(message_data):
    """Send message data to Vercel API"""
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL not configured")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WEBHOOK_URL}",
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
    logger.info(f"🤖 Discord client `{discord_client.user}` logged in")
    logger.info(f"🔗 Connected to {len(discord_client.guilds)} guilds")
    logger.info(f"🎯 Monitoring {len(CHANNEL_NAMES)} channels")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}")
    
    if GUILD_ID:
        logger.info(f"🏠 Targeting specific guild ID: {GUILD_ID}")
    
    # Check for monitored channels
    found_channels = 0
    target_guild = None
    
    # Find target guild if specified
    if GUILD_ID:
        for guild in discord_client.guilds:
            if str(guild.id) == str(GUILD_ID):
                target_guild = guild
                break
        
        if not target_guild:
            logger.error(f"❌ Could not find guild with ID: {GUILD_ID}")
            return
        
        guilds_to_check = [target_guild]
    else:
        guilds_to_check = discord_client.guilds
    
    # Check for monitored channels
    for guild in guilds_to_check:
        logger.info(f"🔍 Checking guild: {guild.name}")
        for channel_id in CHANNEL_NAMES.keys():
            channel = guild.get_channel(channel_id)
            if channel:
                logger.info(f"✅ Found monitored channel: #{channel.name}")
                found_channels += 1
    
    logger.info(f"📊 Found {found_channels}/{len(CHANNEL_NAMES)} monitored channels")

@discord_client.event
async def on_message(message: discord.Message):
    # Don't process own messages (prevent infinite loops)
    if message.author == discord_client.user:
        return
    
    # If GUILD_ID is specified, only process messages from that guild
    if GUILD_ID and str(message.guild.id) != str(GUILD_ID):
        return
    
    # Check if message is in a monitored channel
    if message.channel.id not in CHANNEL_NAMES:
        return
    
    # Process ALL messages from monitored channels (no filtering)
    try:
        message_data = format_message_for_api(message)
        await send_to_vercel(message_data)
        logger.info(f"📤 Processed: {message.author.display_name} in #{message.channel.name}")
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")

# Health check endpoint
from aiohttp import web

async def health_check(request):
    return web.json_response({
        "status": "healthy",
        "client_ready": discord_client.is_ready(),
        "guilds": len(discord_client.guilds) if discord_client.is_ready() else 0,
        "webhook_configured": bool(WEBHOOK_URL),
        "monitored_channels": len(CHANNEL_NAMES),
        "timestamp": datetime.now().isoformat()
    })

async def start_web_server():
    """Start a simple web server for health checks"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Health check server started on port {port}")

async def main():
    try:
        logger.info("🚀 Starting Discord message bridge...")
        
        if not DISCORD_TOKEN:
            logger.error("❌ DISCORD_TOKEN environment variable not set")
            return
        
        if not WEBHOOK_URL:
            logger.error("❌ WEBHOOK_URL environment variable not set")
            return
        
        logger.warning("⚠️ WARNING: Using user token violates Discord ToS")
        
        # Start web server for health checks
        await start_web_server()
        
        # Start Discord client
        logger.info("🔌 Connecting to Discord...")
        await discord_client.start(DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        try:
            await discord_client.close()
            logger.info("🔌 Discord client disconnected")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
