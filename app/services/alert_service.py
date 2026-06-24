from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert

DISCORD_EMBED_COLORS = {
    "NEW_POSITION": 0x2ECC71,
    "POSITION_INCREASE": 0x3498DB,
    "POSITION_DECREASE": 0xE67E22,
    "FULL_EXIT": 0xE74C3C,
}


async def poll_unnotified_alerts(db: AsyncSession) -> list[Alert]:
    stmt = (
        select(Alert)
        .where(Alert.notified_at.is_(None))
        .where(Alert.delivery_attempts < 3)
        .order_by(Alert.detected_at.asc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def classify_action(shares_before: float | None, shares_after: float | None) -> str | None:
    before = float(shares_before or 0)
    after = float(shares_after or 0)

    if before == 0 and after > 0:
        return "NEW_POSITION"
    if after > before:
        return "POSITION_INCREASE"
    if after < before and after > 0:
        return "POSITION_DECREASE"
    if after == 0 and before > 0:
        return "FULL_EXIT"
    return None


def _format_action(action: str, price: float) -> str:
    labels = {
        "NEW_POSITION": f"BUY (New Position @ ${price:.4f})",
        "POSITION_INCREASE": f"BUY (Increase @ ${price:.4f})",
        "POSITION_DECREASE": f"SELL (Decrease @ ${price:.4f})",
        "FULL_EXIT": f"SELL (Full Exit @ ${price:.4f})",
    }
    return labels.get(action, action)


async def send_discord_alert(alert: Alert, webhook_url: str) -> bool:
    color = DISCORD_EMBED_COLORS.get(str(alert.action), 0x95A5A6)

    embed = {
        "embeds": [{
            "title": "🚨 Smart Money Alert",
            "color": color,
            "fields": [
                {
                    "name": "Trader",
                    "value": f"`{alert.wallet[:10]}...{alert.wallet[-4:]}`",
                    "inline": True,
                },
                {
                    "name": "Score",
                    "value": str(alert.wallet_score),
                    "inline": True,
                },
                {
                    "name": "Category",
                    "value": alert.category,
                    "inline": True,
                },
                {
                    "name": "Action",
                    "value": _format_action(str(alert.action), float(alert.price)),
                    "inline": True,
                },
                {
                    "name": "Market",
                    "value": alert.market_question,
                    "inline": False,
                },
                {
                    "name": "Price",
                    "value": f"${float(alert.price):.4f}",
                    "inline": True,
                },
                {
                    "name": "Position Size",
                    "value": f"${float(alert.position_size):,.2f}",
                    "inline": True,
                },
            ],
            "footer": {"text": "Polymarket Smart Money Tracker"},
            "timestamp": alert.detected_at.isoformat(),
        }]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(webhook_url, json=embed)
            return resp.status_code in (200, 204)
        except httpx.RequestError:
            return False


async def mark_notified(alert_id: str, success: bool, db: AsyncSession) -> None:
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        return
    if success:
        alert.notified_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    else:
        alert.delivery_attempts = (alert.delivery_attempts or 0) + 1  # type: ignore[assignment]
    await db.commit()
