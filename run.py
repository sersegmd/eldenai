from __future__ import annotations

import asyncio
import contextlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand

from app.bot import bot, dp
from app.config import settings
from app.db import init_db
from app.video import restore_video_monitors
from app.web import app
from app.delivery import worker as delivery_worker

log = logging.getLogger("elden.startup")

COMMANDS = [
    BotCommand(command="start", description="Start ELDEN AI"),
    BotCommand(command="menu", description="Show the temporary menu"),
    BotCommand(command="video", description="Create an AI video"),
    BotCommand(command="image", description="Create an AI image"),
    BotCommand(command="creator", description="Create a complete short video"),
    BotCommand(command="modes", description="Choose an AI mode"),
    BotCommand(command="animate", description="Animate an image"),
    BotCommand(command="article", description="Turn article or PDF into a Reel"),
    BotCommand(command="new", description="New private chat session"),
    BotCommand(command="voice", description="Voice mode: male or female"),
    BotCommand(command="voicelang", description="Set voice language"),
    BotCommand(command="cancel", description="Cancel the current wizard"),
    BotCommand(command="personality", description="Customize AI personality"),
    BotCommand(command="plans", description="Plans and Telegram Stars"),
    BotCommand(command="referral", description="Referral rewards"),
    BotCommand(command="redeem", description="Redeem a coupon"),
    BotCommand(command="language", description="Change language"),
    BotCommand(command="privacy", description="Privacy information"),
    BotCommand(command="terms", description="Terms of use"),
    BotCommand(command="paysupport", description="Payment support"),
    BotCommand(command="help", description="Help"),
]


async def serve_web() -> None:
    config = uvicorn.Config(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
    )
    await uvicorn.Server(config).serve()


async def connect_telegram() -> None:
    """Wait for Telegram instead of terminating on a temporary network outage."""
    attempt = 0
    while True:
        attempt += 1
        try:
            me = await bot.get_me(request_timeout=30)
            await bot.set_my_commands(COMMANDS, request_timeout=30)
            log.info("Telegram connected as @%s", me.username or me.id)
            return
        except TelegramUnauthorizedError:
            log.error("Telegram rejected BOT_TOKEN. Correct BOT_TOKEN in .env and restart.")
            raise
        except (TelegramNetworkError, OSError, asyncio.TimeoutError) as exc:
            delay = min(60, settings.telegram_retry_seconds * max(1, min(attempt, 4)))
            log.warning(
                "Telegram is unreachable (%s). Retrying in %s seconds; the bot will stay open.",
                exc,
                delay,
            )
            await asyncio.sleep(delay)


async def main() -> None:
    fmt=logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root=logging.getLogger();root.setLevel(settings.log_level);root.handlers.clear()
    console=logging.StreamHandler();console.setFormatter(fmt);root.addHandler(console)
    Path("logs").mkdir(exist_ok=True);rot=RotatingFileHandler("logs/elden.log",maxBytes=5*1024*1024,backupCount=6,encoding="utf-8");rot.setFormatter(fmt);root.addHandler(rot)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    web_task: asyncio.Task | None = None
    delivery_task: asyncio.Task | None = None
    try:
        await init_db()
        web_task = asyncio.create_task(serve_web(), name="elden-dashboard")
        await connect_telegram()
        delivery_task=asyncio.create_task(delivery_worker(bot),name="delivery-worker")
        await restore_video_monitors(bot)
        # Aiogram handles later Telegram connection drops with its own polling backoff.
        await dp.start_polling(bot, close_bot_session=False)
    finally:
        if delivery_task is not None:
            delivery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError): await delivery_task
        if web_task is not None:
            web_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await web_task
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
