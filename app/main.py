import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.db.engine import async_session
from app.services.alert_service import (
    mark_notified,
    poll_unnotified_alerts,
    send_discord_alert,
)
from app.services.ws_manager import manager


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
        except Exception as e:
            print(f"Alert delivery error: {e}")

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
