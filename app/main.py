import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from sqlalchemy import select, text

from app.api.router import api_router
from app.config import settings
from app.db.engine import async_session
from app.db.models_follow import WalletFollow
from app.services.alert_service import (
    build_discord_embed,
    get_follow_info_for_embed,
    mark_notified,
    poll_unnotified_alerts,
    send_discord_alert,
)
from app.services.paper_trading import (
    execute_copy_trade,
    handle_market_resolution,
    update_unrealized_pnl,
)
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
                        FOR UPDATE OF a SKIP LOCKED
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


async def monitor_pipeline_failures_loop() -> None:
    """Poll pipeline_run_log every 5 min and alert Discord on failures."""
    last_check = datetime.now(timezone.utc)
    while True:
        await asyncio.sleep(300)
        try:
            async with async_session() as db:
                result = await db.execute(
                    text("""
                        SELECT pipeline_name, status, updated_at
                        FROM pipeline_run_log
                        WHERE status != 'success'
                          AND updated_at > :last_check
                        ORDER BY updated_at
                    """),
                    {"last_check": last_check},
                )
                failures = result.all()
                if not failures:
                    continue

                lines = [
                    f"**{m['pipeline_name']}** — `{m['status']}` ({m['updated_at'].isoformat()})"
                    for row in failures
                    if (m := row._mapping)
                ]
                payload = {"content": "🚨 **ETL Pipeline Failure**\n" + "\n".join(lines)}

                if settings.discord_webhook_url:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(settings.discord_webhook_url, json=payload)
                        if resp.status_code not in (200, 204):
                            logger.warning("Discord webhook returned %s", resp.status_code)

                last_check = datetime.now(timezone.utc)
        except Exception:
            logger.exception("Pipeline monitor error")


async def paper_pnl_update_loop() -> None:
    """Update unrealized PnL for all open paper positions."""
    while True:
        await asyncio.sleep(30)
        try:
            async with async_session() as db:
                await update_unrealized_pnl(db)
        except Exception:
            logger.exception("Paper PnL update error")


async def paper_market_resolution_loop() -> None:
    """Auto-close paper positions on resolved markets."""
    while True:
        await asyncio.sleep(30)
        try:
            async with async_session() as db:
                result = await db.execute(
                    text("""
                        SELECT DISTINCT m.id, m.winning_outcome
                        FROM markets m
                        JOIN paper_positions pp ON pp.market_id = m.id
                        WHERE m.winning_outcome IS NOT NULL
                          AND pp.status = 'OPEN'
                    """)
                )
                for row in result.all():
                    await handle_market_resolution(
                        db, row._mapping["id"], row._mapping["winning_outcome"]
                    )
        except Exception:
            logger.exception("Paper market resolution error")


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(30)
        await manager.send_heartbeat()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    delivery_task = asyncio.create_task(alert_delivery_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    paper_trade_task = asyncio.create_task(paper_trade_generation_loop())
    paper_pnl_task = asyncio.create_task(paper_pnl_update_loop())
    paper_resolution_task = asyncio.create_task(paper_market_resolution_loop())
    monitor_task = asyncio.create_task(monitor_pipeline_failures_loop())
    yield
    delivery_task.cancel()
    heartbeat_task.cancel()
    paper_trade_task.cancel()
    paper_pnl_task.cancel()
    paper_resolution_task.cancel()
    monitor_task.cancel()


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
