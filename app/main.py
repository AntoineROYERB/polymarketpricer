import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from app.api.router import api_router
from app.config import settings
from app.db.engine import async_session
from app.services.alert_service import (
    mark_notified,
    poll_unnotified_alerts,
    send_discord_alert,
)
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)


async def alert_delivery_loop() -> None:
    while True:
        try:
            async with async_session() as db:
                alerts = await poll_unnotified_alerts(db)
                for alert in alerts:
                    await manager.broadcast_alert(alert)

                    if settings.discord_webhook_url:
                        success = await send_discord_alert(
                            alert, settings.discord_webhook_url
                        )
                    else:
                        success = True

                    await mark_notified(str(alert.id), success, db)

                    await asyncio.sleep(0.5)
        except Exception:
            logger.exception("Alert delivery error")

        await asyncio.sleep(settings.alert_poll_interval_seconds)


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(30)
        await manager.send_heartbeat()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    delivery_task = asyncio.create_task(alert_delivery_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    yield
    delivery_task.cancel()
    heartbeat_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
