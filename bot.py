import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass

import betterlogging as bl
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis import asyncio as aioredis

from tgbot.config import Config, load_config
from tgbot.handlers import routers_list
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.middlewares.database import DatabaseMiddleware
from tgbot.middlewares.dev import DeveloperMiddleware
from tgbot.services import broadcaster
from tgbot.services.migration import init_db_and_migrations


@dataclass
class WebhookConfig:
    """Конфигурация для webhook"""

    host: str = "0.0.0.0"
    port: int = 80
    path: str = "/webhook"
    webhook_url: str = "http://tg_bot/webhook"


class TgBot:
    def __init__(self, config: Config, webhook_config: Optional[WebhookConfig] = None):
        self.config = config
        self.webhook_config = webhook_config or WebhookConfig()
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.redis: Optional[aioredis.Redis] = None
        self.app: Optional[web.Application] = None
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Logging setup"""
        bl.basic_colorized_config(level=logging.INFO)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
        )
        self.logger.info("Initializing bot")

    async def _init_storage(self) -> RedisStorage:
        """Initializing Redis storage"""
        try:
            return RedisStorage.from_url(
                self.config.redis.dsn(),
                key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis storage: {e}")
            raise

    async def _init_database(self) -> None:
        """Initializing database"""
        try:
            db_url = (
                f"postgresql+asyncpg://{self.config.postgres.db_user}:{self.config.postgres.db_pass}"
                f"@{self.config.postgres.db_host}:5432/{self.config.postgres.db_name}"
            )
            await init_db_and_migrations(
                database_url=db_url,
                alembic_cfg_path=str(Path(__file__).parent / "alembic.ini"),
            )
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    async def setup_bot(self) -> None:
        """Bot setup"""
        try:
            storage = await self._init_storage()
            session = AiohttpSession(api=TelegramAPIServer.from_base("http://nginx:80"))

            self.bot = Bot(
                token=self.config.tg_bot.token, parse_mode="HTML", session=session
            )
            self.dp = Dispatcher(storage=storage)

            # Register handlers and middlewares
            self.dp.include_routers(*routers_list)
            self._register_middlewares()

        except Exception as e:
            self.logger.error(f"Bot setup failed: {e}")
            raise

    def _register_middlewares(self) -> None:
        """Register middlewares"""
        middleware_types = [
            ConfigMiddleware(self.config, self.redis),
            DatabaseMiddleware(),
            DeveloperMiddleware(),
        ]

        for middleware in middleware_types:
            for event_type in [self.dp.message, self.dp.callback_query]:
                event_type.outer_middleware(middleware)

    async def setup_webhook(self) -> None:
        """Webhook setup with validation"""
        if not self.dp or not self.bot:
            raise RuntimeError(
                "Bot and dispatcher must be initialized before webhook setup"
            )

        self.app = web.Application()
        webhook_handler = SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)
        webhook_handler.register(self.app, path=self.webhook_config.path)
        setup_application(self.app, self.dp, bot=self.bot)

    @asynccontextmanager
    async def bot_context(self):
        """Context manager for starting and shutting down the bot"""
        try:
            await self._init_database()
            await self.setup_bot()
            await self.setup_webhook()

            # Setup webhook
            await self.bot.delete_webhook()
            await self.bot.set_webhook(self.webhook_config.webhook_url)

            # Notify admins
            await broadcaster.broadcast(
                self.bot, self.config.tg_bot.admin_ids, "Bot started successfully"
            )

            yield

        finally:
            await self.shutdown()

    async def shutdown(self, signal: Optional[signal.Signals] = None) -> None:
        """Улучшенное graceful shutdown"""
        if signal:
            self.logger.info(f"Received exit signal {signal.name}")

        try:
            # Notify admins
            if self.bot:
                await broadcaster.broadcast(
                    self.bot, self.config.tg_bot.admin_ids, "Bot is shutting down..."
                )

            # Close all connections
            if self.bot:
                await self.bot.session.close()
            if self.redis:
                await self.redis.close()

            self.logger.info("Shutdown completed successfully")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            asyncio.get_event_loop().stop()

    async def start(self) -> None:
        """Bot start"""
        async with self.bot_context():
            try:
                # Setup signals handler
                for sig in (signal.SIGTERM, signal.SIGINT):
                    asyncio.get_event_loop().add_signal_handler(
                        sig, lambda s=sig: asyncio.create_task(self.shutdown(s))
                    )

                # Start web-server
                runner = web.AppRunner(self.app)
                await runner.setup()
                site = web.TCPSite(
                    runner, host=self.webhook_config.host, port=self.webhook_config.port
                )
                await site.start()

                self.logger.info(
                    f"Bot started and listening on {self.webhook_config.host}:"
                    f"{self.webhook_config.port}"
                )
                await asyncio.Event().wait()

            except Exception as e:
                self.logger.error(f"Critical error during bot execution: {e}")
                raise


def main():
    try:
        config = load_config(".env")
        bot = TgBot(config)
        asyncio.run(bot.start())
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise
    finally:
        logging.info("Bot stopped")


if __name__ == "__main__":
    main()
