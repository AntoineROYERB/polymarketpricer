from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.dependencies.auth import verify_api_key
from app.config import settings
from app.db.models import Alert, Market, Wallet
from app.models.schemas import AlertItem, AlertListResponse
from app.services.ws_manager import manager
from app.utils.sql import escape_like

router = APIRouter()


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List Alerts",
    description="Smart money alerts, filterable by category, score, or wallet.",
)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    min_score: Decimal | None = None,
    wallet: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    stmt = (
        select(Alert, Market.event_slug, Market.condition_id)
        .join(Market, Alert.market_id == Market.id, isouter=True)
        .order_by(Alert.detected_at.desc())
    )

    if category:
        stmt = stmt.where(Alert.category.ilike(category))
    if min_score is not None:
        stmt = stmt.where(Alert.wallet_score >= min_score)
    if wallet:
        # Escape LIKE metacharacters so a caller-supplied "%" matches a literal
        # percent sign instead of turning the filter into a match-everything.
        stmt = stmt.where(Alert.wallet.ilike(f"%{escape_like(wallet)}%", escape="\\"))

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    return AlertListResponse(
        data=[_alert_to_item(a, es, ci) for a, es, ci in rows],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stats",
    response_model=dict,
    summary="Alert Statistics",
    description="Aggregate counts and top categories/wallets for alerts.",
)
async def alert_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    total = await db.execute(select(sa_func.count(Alert.id)))
    today = await db.execute(
        select(sa_func.count(Alert.id)).where(
            Alert.detected_at >= sa_func.current_date()
        )
    )

    cat_rows = await db.execute(
        select(Alert.category, sa_func.count(Alert.id).label("count"))
        .group_by(Alert.category)
        .order_by(sa_func.count(Alert.id).desc())
        .limit(5)
    )

    wallet_rows = await db.execute(
        select(Alert.wallet, sa_func.count(Alert.id).label("alert_count"))
        .group_by(Alert.wallet)
        .order_by(sa_func.count(Alert.id).desc())
        .limit(5)
    )

    return {
        "total_alerts": total.scalar() or 0,
        "alerts_today": today.scalar() or 0,
        "top_categories": [
            {"category": row.category, "count": row.count}
            for row in cat_rows.all()
        ],
        "top_wallets": [
            {"wallet": row.wallet, "alert_count": row.alert_count}
            for row in wallet_rows.all()
        ],
    }


@router.websocket("/ws")
async def alert_websocket(
    websocket: WebSocket,
    api_key: str | None = Query(default=None),
) -> None:
    """Real-time smart money alert stream via WebSocket.

    Browsers cannot set headers on a WebSocket handshake, so the key travels as a
    query parameter. It is still required: a missing key is rejected exactly like a
    wrong one.
    """
    if not verify_api_key(api_key):
        await websocket.close(code=4001)
        return
    origin = websocket.headers.get("origin", "")
    if origin and origin not in settings.cors_origins:
        await websocket.close(code=4001)
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "pong":
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get(
    "/{wallet}",
    response_model=AlertListResponse,
    summary="Wallet Alerts",
    description="Alerts triggered for a specific wallet.",
)
async def wallet_alerts(
    wallet: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    w = await db.execute(select(Wallet).where(Wallet.wallet == wallet))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    stmt = (
        select(Alert, Market.event_slug, Market.condition_id)
        .join(Market, Alert.market_id == Market.id, isouter=True)
        .where(Alert.wallet == wallet)
        .order_by(Alert.detected_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return AlertListResponse(
        data=[_alert_to_item(a, es, ci) for a, es, ci in rows],
        limit=limit,
        offset=offset,
    )


def _alert_to_item(
    a: Alert,
    event_slug: str | None = None,
    condition_id: str | None = None,
) -> AlertItem:
    item = AlertItem.model_validate(a)
    item.event_slug = event_slug
    item.condition_id = condition_id
    return item
