import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from sqlalchemy import select, text

from app.api.router import api_router
from app.config import settings
from app.db.engine import async_session
from app.db.models import WalletFollow
from app.services.alert_service import (
    build_discord_embed,
    get_follow_info_for_embed,
    mark_notified,
    poll_unnotified_alerts,
    send_discord_alert,
)
from app.services.paper_trading import execute_copy_trade
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)


async def alert_delivery_loop() -> None:
    while True:
        try:
            async with async_session() as db:
                alerts = await poll_unnotified_alerts(db)
                for alert in alerts:
                    follow_info, copy_suggestion, category_str = await get_follow_info_for_embed(
                        db, alert.wallet  # type: ignore[arg-type]
                    )
                    embed = build_discord_embed(alert, follow_info, copy_suggestion, category_str)

                    await manager.broadcast_alert(alert, follow_info, copy_suggestion)

                    if settings.discord_webhook_url:
                        success = await send_discord_alert(
                            embed, settings.discord_webhook_url
                        )
                    else:
                        success = True

                    await mark_notified(str(alert.id), success, db)

                    await asyncio.sleep(0.5)
        except Exception:
            logger.exception("Alert delivery error")

        await asyncio.sleep(settings.alert_poll_interval_seconds)


async def paper_trade_generation_loop() -> None:
    """Background task: poll for new alerts and generate paper trades."""
    while True:
        try:
            async with async_session() as db:
                result = await db.execute(
                    text("""
                        SELECT a.id, a.wallet, a.market_id, a.action,
                               a.position_size, a.category, a.price,
                               wf.copy_mode, wf.copy_value, wf.category_filter,
                               wf.user_id
                        FROM alerts a
                        JOIN wallet_follows wf ON wf.wallet = a.wallet
                            AND wf.active = true
                            AND wf.auto_copy_enabled = true
                        LEFT JOIN paper_trades pt ON pt.source_alert_id = a.id
                        WHERE pt.id IS NULL
                          AND a.detected_at >= NOW() - INTERVAL '1 hour'
                        ORDER BY a.detected_at
                        LIMIT 20
                        FOR UPDATE SKIP LOCKED
                    """)
                )
                rows = result.all()

                for row in rows:
                    m = row._mapping
                    alert_dict = dict(m)
                    # category_filter check is handled inside execute_copy_trade

                    follow = await db.execute(
                        select(WalletFollow).where(
                            WalletFollow.user_id == m["user_id"],
                            WalletFollow.wallet == m["wallet"],
                        )
                    )
                    follow_obj = follow.scalar_one_or_none()
                    if follow_obj:
                        await execute_copy_trade(db, alert_dict, follow_obj)

        except Exception:
            logger.exception("Paper trade generation error")

        await asyncio.sleep(10)


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(30)
        await manager.send_heartbeat()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    delivery_task = asyncio.create_task(alert_delivery_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    paper_trade_task = asyncio.create_task(paper_trade_generation_loop())
    yield
    delivery_task.cancel()
    heartbeat_task.cancel()
    paper_trade_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
