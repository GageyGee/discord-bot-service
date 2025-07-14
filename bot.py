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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Your Vercel API endpoint (backup)
WEBSOCKET_SERVER_URL = os.getenv('WEBSOCKET_SERVER_URL', 'http://localhost:3001')  # WebSocket server
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

# Map Discord channel IDs to WebSocket server channel IDs
CHANNEL_ID_MAPPING = {
    1251179699674288208: "shocked",
    1251848915305631834: "vanquish", 
    1250885750158000203: "digi",
    1323011103894016133: "pastel",
    1358931443786584144: "cryptic",
    1256632909008339035: "yogurtverse",
    1319692012261347360: "heaven_or_hell",
    1316031095497818143: "minted",
    1392587523838185592: "serenity",
    1302921864540323861: "technical_alpha",
    1307140339991183380: "pf_trenches",
    1304074398185029632: "potion",
    1250885751768481849: "prosperity_dao",
    1316784867962519603: "secret_society",
}

# Discord client setup
discord_client = discord.Client()

async def send_to_websocket_server(message_data):
    """Send message data to WebSocket server (primary)"""
    if not WEBSOCKET_SERVER_URL:
        logger.warning("WEBSOCKET_SERVER_URL not configured")
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WEBSOCKET_SERVER_URL}/api/message",
                json=message_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Message sent to WebSocket server: {message_data['author']['name']}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send to WebSocket server: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error sending to WebSocket server: {e}")
        return False

async def send_to_vercel(message_data):
    """Send message data to Vercel API (backup)"""
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured")
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WEBHOOK_URL}",
                json=message_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Message sent to Vercel backup: {message_data['author']['name']}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send to Vercel: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error sending to Vercel: {e}")
        return False

def format_message_for_websocket(message: discord.Message) -> dict:
    """Format Discord message for WebSocket server"""
    
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

    # Process embeds (for bots like Rick, Utrax RepBot)
    embeds = []
    if message.embeds:
        for embed in message.embeds:
            embed_data = {
                "title": embed.title,
                "description": embed.description,
                "url": str(embed.url) if embed.url else None,
                "image": {"url": str(embed.image.url)} if embed.image else None,
                "thumbnail": {"url": str(embed.thumbnail.url)} if embed.thumbnail else None
            }
            embeds.append(embed_data)

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

    # Format for WebSocket server
    return {
        "channel_id": int(message.channel.id),  # WebSocket server expects the Discord channel ID
        "content": cleaned_content,
        "author": {
            "name": message.author.display_name,
            "avatar": str(message.author.display_avatar.url) if message.author.display_avatar else None,
            "bot": message.author.bot
        },
        "embeds": embeds,
        "attachments": attachments,
        "reply": reply_info
    }

def format_message_for_vercel(message: discord.Message) -> dict:
    """Format Discord message for Vercel API (legacy format)"""
    
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

    # Process embeds
    embeds = []
    if message.embeds:
        for embed in message.embeds:
            embed_data = {
                "title": embed.title,
                "description": embed.description,
                "url": embed.url,
                "image": {"url": embed.image.url} if embed.image else None,
                "thumbnail": {"url": embed.thumbnail.url} if embed.thumbnail else None
            }
            embeds.append(embed_data)

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
        "embeds": embeds,
        "reply": reply_info,
        "is_bot": message.author.bot
    }

async def check_websocket_server():
    """Check if WebSocket server is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{WEBSOCKET_SERVER_URL}/api/health") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ WebSocket server is healthy: {data}")
                    return True
    except Exception as e:
        logger.error(f"❌ WebSocket server health check failed: {e}")
    return False

@discord_client.event
async def on_ready():
    logger.info(f"🤖 Discord client `{discord_client.user}` logged in")
    logger.info(f"🔗 Connected to {len(discord_client.guilds)} guilds")
    logger.info(f"🎯 Monitoring {len(CHANNEL_NAMES)} channels")
    
    # Check WebSocket server connection
    if await check_websocket_server():
        logger.info("✅ WebSocket server connection verified")
    else:
        logger.warning("⚠️ WebSocket server not available - messages will be lost!")
    
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
    
    # Process ALL messages from monitored channels
    try:
        # Format for WebSocket server (primary)
        websocket_data = format_message_for_websocket(message)
        websocket_success = await send_to_websocket_server(websocket_data)
        
        # Format for Vercel (backup)
        vercel_data = format_message_for_vercel(message)
        vercel_success = await send_to_vercel(vercel_data)
        
        if websocket_success:
            logger.info(f"📤 Processed via WebSocket: {message.author.display_name} in #{message.channel.name}")
        elif vercel_success:
            logger.info(f"📤 Processed via Vercel backup: {message.author.display_name} in #{message.channel.name}")
        else:
            logger.error(f"❌ Failed to process message from {message.author.display_name}")
            
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")

# Health check endpoint
from aiohttp import web

async def health_check(request):
    websocket_healthy = await check_websocket_server()
    
    return web.json_response({
        "status": "healthy",
        "client_ready": discord_client.is_ready(),
        "guilds": len(discord_client.guilds) if discord_client.is_ready() else 0,
        "webhook_configured": bool(WEBHOOK_URL),
        "websocket_server_configured": bool(WEBSOCKET_SERVER_URL),
        "websocket_server_healthy": websocket_healthy,
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
        logger.info("🚀 Starting Discord WebSocket bridge...")
        
        if not DISCORD_TOKEN:
            logger.error("❌ DISCORD_TOKEN environment variable not set")
            return
        
        if not WEBSOCKET_SERVER_URL:
            logger.error("❌ WEBSOCKET_SERVER_URL environment variable not set")
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
