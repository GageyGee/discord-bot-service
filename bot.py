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

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Your Vercel API endpoint
GUILD_ID = os.getenv('GUILD_ID')  # Optional: Specific Discord Server ID to monitor

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

# Discord client setup - using same pattern as your working Telegram bridge
discord_client = discord.Client()

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

# Log on_ready event - same pattern as your working script
@discord_client.event
async def on_ready():
    logger.info(f"Discord client `{discord_client.user}` logged in.")
    logger.info(f'🔗 Connected to {len(discord_client.guilds)} guilds')
    logger.info(f'🎯 Monitoring {len(CHANNEL_NAMES)} channels')
    logger.info(f'📡 Webhook URL configured: {bool(WEBHOOK_URL)}')
    logger.info(f'🏠 Guild ID filter: {GUILD_ID if GUILD_ID else "None (monitoring all guilds)"}')
    
    # DEBUG: List all available guilds and channels
    logger.info("=== DEBUG: Available Guilds ===")
    target_guild = None
    
    for guild in discord_client.guilds:
        logger.info(f'🏠 Guild: {guild.name} (ID: {guild.id})')
        
        # If GUILD_ID is specified, only look in that guild
        if GUILD_ID and str(guild.id) == str(GUILD_ID):
            target_guild = guild
            logger.info(f'   ✅ This is the target guild!')
        elif not GUILD_ID:
            # Show channels for all guilds if no specific guild is set
            logger.info(f'   📋 Available channels in {guild.name}:')
            for channel in guild.channels:
                if hasattr(channel, 'name'):  # Text channels have names
                    logger.info(f'      #{channel.name} (ID: {channel.id})')
    
    # If specific guild is set, show only that guild's channels
    if GUILD_ID and target_guild:
        logger.info(f"=== Channels in target guild: {target_guild.name} ===")
        for channel in target_guild.channels:
            if hasattr(channel, 'name'):
                logger.info(f'   #{channel.name} (ID: {channel.id})')
    elif GUILD_ID and not target_guild:
        logger.error(f"❌ Could not find guild with ID: {GUILD_ID}")
        logger.info("Available guild IDs:")
        for guild in discord_client.guilds:
            logger.info(f"   - {guild.name}: {guild.id}")
        return
    
    logger.info("=== Looking for monitored channels ===")
    # Check for monitored channels
    found_channels = 0
    guilds_to_check = [target_guild] if target_guild else discord_client.guilds
    
    for guild in guilds_to_check:
        logger.info(f'🔍 Checking guild: {guild.name} (ID: {guild.id})')
        for channel_id in CHANNEL_NAMES.keys():
            channel = guild.get_channel(channel_id)
            if channel:
                logger.info(f'✅ Found channel: #{channel.name} ({channel_id}) in {guild.name}')
                found_channels += 1
            else:
                logger.warning(f'❌ Channel not found: {channel_id} ({CHANNEL_NAMES[channel_id]})')
    
    logger.info(f"📊 Found {found_channels}/{len(CHANNEL_NAMES)} monitored channels")

# Process incoming messages - same pattern as your working script
@discord_client.event
async def on_message(message: discord.Message):
    # DEBUG: Log every single message we receive
    logger.info(f"🔍 DEBUG: Received message from {message.author.display_name} in #{message.channel.name}")
    logger.info(f"   - Author ID: {message.author.id}")
    logger.info(f"   - Is bot: {message.author.bot}")
    logger.info(f"   - Channel ID: {message.channel.id}")
    logger.info(f"   - Guild: {message.guild.name if message.guild else 'DM'}")
    logger.info(f"   - Content preview: {message.content[:50]}...")
    
    # Skip messages from Rick since there's already a Rick bot in Telegram
    if message.author.display_name.lower() == "rick":
        logger.info(f"⏭️ Skipping message from Rick (already have Rick bot in Telegram)")
        return
    
    # Don't process own messages (important for user tokens)
    if message.author == discord_client.user:
        logger.info(f"⏭️ Skipping own message")
        return
    
    # Don't process other bot messages
    if message.author.bot:
        logger.info(f"⏭️ Skipping bot message from {message.author.display_name}")
        return
    
    # If GUILD_ID is specified, only process messages from that guild
    if GUILD_ID and str(message.guild.id) != str(GUILD_ID):
        logger.info(f"⏭️ Skipping message from different guild: {message.guild.name}")
        return
    
    # Check if message is in a monitored channel
    if message.channel.id not in CHANNEL_NAMES:
        logger.info(f"⏭️ Skipping message from unmonitored channel: #{message.channel.name}")
        return
    
    logger.info(f"✅ Processing message from monitored channel #{message.channel.name}")
    
    # Filter Discord promotional content
    if message.content:
        content_lower = message.content.lower()
        discord_keywords = [
            "go to mention", "[go to mention]", "discord.com/channels/",
            "referenced message", "[referenced message]"
        ]
        
        if any(keyword in content_lower for keyword in discord_keywords):
            logger.info(f"🚫 Blocked promotional content: {message.content[:100]}...")
            return
    
    # Format and send message to Vercel
    try:
        logger.info(f"🚀 Formatting message for webhook...")
        message_data = format_message_for_api(message)
        logger.info(f"📤 Sending to webhook: {message_data}")
        await send_to_vercel(message_data)
        
        logger.info(f"📤 Processed message from #{message.channel.name}: {message.author.display_name} - {message.content[:50]}...")
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        import traceback
        logger.error(traceback.format_exc())

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

# Main function to run both clients - same pattern as your working script
async def main():
    try:
        logger.info("Starting Discord message bridge...")
        logger.info(f"🐍 Python version: {os.sys.version}")
        logger.info(f"📦 Discord.py version: {discord.__version__}")
        
        if not DISCORD_TOKEN:
            logger.error("❌ DISCORD_TOKEN environment variable not set")
            return
        
        if not WEBHOOK_URL:
            logger.error("❌ WEBHOOK_URL environment variable not set")
            return
        
        logger.warning("⚠️ WARNING: Using user token violates Discord ToS and may result in account ban!")
        
        if GUILD_ID:
            logger.info(f"🏠 Targeting specific guild ID: {GUILD_ID}")
        else:
            logger.info("🌐 Monitoring all accessible guilds")
        
        # Start web server for health checks
        await start_web_server()
        
        # Start Discord client - same pattern as your working Telegram bridge
        logger.info("Starting Discord client...")
        await discord_client.start(DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        try:
            await discord_client.close()
            logger.info("Discord client disconnected.")
        except:
            pass

# Run the bot - same pattern as your working script
if __name__ == "__main__":
    asyncio.run(main())
