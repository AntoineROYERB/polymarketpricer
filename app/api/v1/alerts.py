from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.config import settings
from app.db.models import Alert, Wallet
from app.models.schemas import AlertItem, AlertListResponse
from app.services.ws_manager import manager
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
    category: Optional[str] = None,
    min_score: Optional[Decimal] = None,
    wallet: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    stmt = select(Alert).order_by(Alert.detected_at.desc())

    if category:
        stmt = stmt.where(Alert.category.ilike(category))
    if min_score is not None:
        stmt = stmt.where(Alert.wallet_score >= min_score)
    if wallet:
        stmt = stmt.where(Alert.wallet.ilike(f"%{wallet}%"))

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(
        data=[_alert_to_item(a) for a in alerts],
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
) -> None:
    """Real-time smart money alert stream via WebSocket."""
    origin = websocket.headers.get("origin", "")
    allowed_origins = getattr(settings, "cors_origins", ["*"])
    if origin and allowed_origins != ["*"] and origin not in allowed_origins:
        await websocket.close(code=4001)
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "pong":
                pass
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
        select(Alert)
        .where(Alert.wallet == wallet)
        .order_by(Alert.detected_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(
        data=[_alert_to_item(a) for a in alerts],
        limit=limit,
        offset=offset,
    )


def _alert_to_item(a: Alert) -> AlertItem:
    return AlertItem.model_validate(a)
