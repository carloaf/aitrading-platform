"""
Notification Service - AI Trading Platform
Handles Telegram, Discord, and Email notifications
"""
import os
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Notification Service",
    description="Service for sending trading alerts via Telegram, Discord, and Email",
    version="1.0.0"
)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


class NotificationRequest(BaseModel):
    """Notification request model"""
    type: str  # trade, signal, alert, error, pnl
    title: str
    message: str
    symbol: Optional[str] = None
    session_id: Optional[str] = None
    pnl: Optional[float] = None
    price: Optional[float] = None
    side: Optional[str] = None  # buy/sell
    channels: Optional[List[str]] = ["telegram", "discord"]


class TelegramSettings(BaseModel):
    """Telegram settings"""
    bot_token: str
    chat_id: str
    enabled: bool = True


class DiscordSettings(BaseModel):
    """Discord settings"""
    webhook_url: str
    enabled: bool = True


class NotificationSettings(BaseModel):
    """Full notification settings"""
    telegram: Optional[TelegramSettings] = None
    discord: Optional[DiscordSettings] = None
    notify_trades: bool = True
    notify_signals: bool = True
    notify_pnl_threshold: float = 5.0  # Percentage
    notify_errors: bool = True


# In-memory settings storage (in production, use Redis/DB)
notification_settings: dict = {}


def format_trade_message(data: NotificationRequest) -> str:
    """Format trade notification message"""
    emoji = "🟢" if data.side == "buy" else "🔴"
    pnl_emoji = "💰" if data.pnl and data.pnl > 0 else "📉" if data.pnl and data.pnl < 0 else ""
    
    lines = [
        f"{emoji} **{data.type.upper()}**: {data.title}",
        f"━━━━━━━━━━━━━━━━━━",
    ]
    
    if data.symbol:
        lines.append(f"📊 Symbol: {data.symbol}")
    if data.side:
        lines.append(f"📈 Side: {data.side.upper()}")
    if data.price:
        lines.append(f"💵 Price: ${data.price:,.2f}")
    if data.pnl is not None:
        lines.append(f"{pnl_emoji} PnL: ${data.pnl:,.2f}")
    if data.session_id:
        lines.append(f"🆔 Session: {data.session_id}")
    
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(data.message)
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(lines)


def format_signal_message(data: NotificationRequest) -> str:
    """Format signal notification message"""
    emoji = "🚀" if data.side == "buy" else "⚠️" if data.side == "sell" else "📡"
    
    lines = [
        f"{emoji} **SIGNAL**: {data.title}",
        f"━━━━━━━━━━━━━━━━━━",
    ]
    
    if data.symbol:
        lines.append(f"📊 Symbol: {data.symbol}")
    if data.side:
        lines.append(f"📈 Direction: {data.side.upper()}")
    if data.price:
        lines.append(f"💵 Price: ${data.price:,.2f}")
    
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(data.message)
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(lines)


def format_alert_message(data: NotificationRequest) -> str:
    """Format alert notification message"""
    type_emoji = {
        "error": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
        "success": "✅",
        "pnl": "💰"
    }
    
    emoji = type_emoji.get(data.type, "🔔")
    
    lines = [
        f"{emoji} **{data.title}**",
        f"━━━━━━━━━━━━━━━━━━",
        data.message,
    ]
    
    if data.pnl is not None:
        lines.append(f"💵 PnL: ${data.pnl:,.2f}")
    
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(lines)


async def send_telegram(message: str, bot_token: str = None, chat_id: str = None) -> bool:
    """Send message via Telegram"""
    token = bot_token or TELEGRAM_BOT_TOKEN
    cid = chat_id or TELEGRAM_CHAT_ID
    
    if not token or not cid:
        logger.warning("Telegram credentials not configured")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Convert markdown to Telegram format
    message = message.replace("**", "*")
    
    payload = {
        "chat_id": cid,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Telegram message sent successfully")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Telegram error: {error}")
                    return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def send_discord(message: str, webhook_url: str = None) -> bool:
    """Send message via Discord webhook"""
    url = webhook_url or DISCORD_WEBHOOK_URL
    
    if not url:
        logger.warning("Discord webhook not configured")
        return False
    
    # Convert to Discord format
    message = message.replace("**", "**")  # Discord uses same markdown
    
    payload = {
        "content": message,
        "username": "AI Trading Bot",
        "avatar_url": "https://i.imgur.com/4M34hi2.png"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status in [200, 204]:
                    logger.info(f"Discord message sent successfully")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Discord error: {error}")
                    return False
    except Exception as e:
        logger.error(f"Discord send error: {e}")
        return False


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "notification-service",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "discord_configured": bool(DISCORD_WEBHOOK_URL),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/notify")
async def send_notification(
    notification: NotificationRequest,
    background_tasks: BackgroundTasks
):
    """Send notification to configured channels"""
    
    # Format message based on type
    if notification.type == "trade":
        message = format_trade_message(notification)
    elif notification.type == "signal":
        message = format_signal_message(notification)
    else:
        message = format_alert_message(notification)
    
    results = {
        "telegram": False,
        "discord": False
    }
    
    # Send to requested channels
    if "telegram" in notification.channels:
        results["telegram"] = await send_telegram(message)
    
    if "discord" in notification.channels:
        results["discord"] = await send_discord(message)
    
    return {
        "status": "sent",
        "channels": results,
        "message_preview": message[:200] + "..." if len(message) > 200 else message
    }


@app.post("/notify/telegram")
async def send_telegram_notification(
    notification: NotificationRequest,
    settings: Optional[TelegramSettings] = None
):
    """Send notification via Telegram only"""
    
    if notification.type == "trade":
        message = format_trade_message(notification)
    elif notification.type == "signal":
        message = format_signal_message(notification)
    else:
        message = format_alert_message(notification)
    
    token = settings.bot_token if settings else None
    chat_id = settings.chat_id if settings else None
    
    success = await send_telegram(message, token, chat_id)
    
    return {
        "status": "sent" if success else "failed",
        "channel": "telegram"
    }


@app.post("/notify/discord")
async def send_discord_notification(
    notification: NotificationRequest,
    settings: Optional[DiscordSettings] = None
):
    """Send notification via Discord only"""
    
    if notification.type == "trade":
        message = format_trade_message(notification)
    elif notification.type == "signal":
        message = format_signal_message(notification)
    else:
        message = format_alert_message(notification)
    
    webhook = settings.webhook_url if settings else None
    
    success = await send_discord(message, webhook)
    
    return {
        "status": "sent" if success else "failed",
        "channel": "discord"
    }


@app.post("/settings/{user_id}")
async def save_settings(user_id: str, settings: NotificationSettings):
    """Save notification settings for a user"""
    notification_settings[user_id] = settings.dict()
    return {"status": "saved", "user_id": user_id}


@app.get("/settings/{user_id}")
async def get_settings(user_id: str):
    """Get notification settings for a user"""
    if user_id not in notification_settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return notification_settings[user_id]


@app.post("/test/telegram")
async def test_telegram(settings: TelegramSettings):
    """Test Telegram connection"""
    test_message = """
🔔 **Test Notification**
━━━━━━━━━━━━━━━━━━
✅ Telegram connection successful!
AI Trading Platform is ready to send alerts.
━━━━━━━━━━━━━━━━━━
⏰ """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    success = await send_telegram(test_message, settings.bot_token, settings.chat_id)
    
    return {
        "status": "success" if success else "failed",
        "message": "Test message sent" if success else "Failed to send test message"
    }


@app.post("/test/discord")
async def test_discord(settings: DiscordSettings):
    """Test Discord connection"""
    test_message = """
🔔 **Test Notification**
━━━━━━━━━━━━━━━━━━
✅ Discord connection successful!
AI Trading Platform is ready to send alerts.
━━━━━━━━━━━━━━━━━━
⏰ """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    success = await send_discord(test_message, settings.webhook_url)
    
    return {
        "status": "success" if success else "failed",
        "message": "Test message sent" if success else "Failed to send test message"
    }


# Trade notification endpoint (called by execution engine)
@app.post("/trade-executed")
async def trade_executed(
    session_id: str,
    symbol: str,
    side: str,
    price: float,
    quantity: float,
    pnl: Optional[float] = None
):
    """Called when a trade is executed"""
    notification = NotificationRequest(
        type="trade",
        title="Trade Executed",
        message=f"{'Bought' if side == 'buy' else 'Sold'} {quantity} {symbol} at ${price:,.2f}",
        symbol=symbol,
        session_id=session_id,
        side=side,
        price=price,
        pnl=pnl,
        channels=["telegram", "discord"]
    )
    
    return await send_notification(notification, BackgroundTasks())


# Signal notification endpoint
@app.post("/signal-generated")
async def signal_generated(
    session_id: str,
    symbol: str,
    signal: int,  # 1 = buy, -1 = sell, 0 = hold
    strategy: str,
    price: float
):
    """Called when a trading signal is generated"""
    if signal == 0:
        return {"status": "no_notification", "reason": "hold signal"}
    
    side = "buy" if signal == 1 else "sell"
    
    notification = NotificationRequest(
        type="signal",
        title=f"{strategy} Signal",
        message=f"Signal generated: {side.upper()} {symbol}",
        symbol=symbol,
        session_id=session_id,
        side=side,
        price=price,
        channels=["telegram", "discord"]
    )
    
    return await send_notification(notification, BackgroundTasks())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3009)
