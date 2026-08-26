from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert
from app.db.models_follow import WalletFollow

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


async def get_follow_info_for_embed(
    db: AsyncSession, wallet: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Look up if wallet is followed (by any user_id) and compute copy suggestion."""
    result = await db.execute(
        select(WalletFollow)
        .where(
            WalletFollow.wallet == wallet,
            WalletFollow.active.is_(True),
        )
        .order_by(WalletFollow.followed_at.desc())
        .limit(1)
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        return None, None, ""

    follow_info = {
        "label": follow.label,
        "followed_at": follow.followed_at,
    }

    category_str = ""
    cat_result = await db.execute(
        text("""
            SELECT category, follow_score, recommendation
            FROM wallet_category_follow_scores
            WHERE wallet = :wallet
              AND snapshot_date = (SELECT MAX(snapshot_date) FROM wallet_category_follow_scores)
            ORDER BY follow_score DESC
            LIMIT 2
        """),
        {"wallet": wallet},
    )
    cat_rows = cat_result.all()
    if cat_rows:
        parts = []
        for r in cat_rows:
            m = r._mapping
            parts.append(f"{m['category']} ({m['recommendation']}, {float(m['follow_score']):.2f})")
        category_str = " | ".join(parts)

    copy_suggestion: dict[str, Any] | None = None
    if follow.auto_copy_enabled:
        copy_suggestion = {"auto_copy_enabled": True, "details": []}
        if follow.copy_mode == "proportional":
            pct = float(follow.copy_value) * 100
            copy_suggestion["details"].append(f"Mode: {pct:.1f}% proportional")
        elif follow.copy_mode == "fixed":
            copy_suggestion["details"].append(f"Mode: ${follow.copy_value} fixed")
        if follow.category_filter:
            cats = ", ".join(follow.category_filter)
            copy_suggestion["details"].append(f"Filter: {cats}")
        else:
            copy_suggestion["details"].append("Filter: All categories")

    return follow_info, copy_suggestion, category_str


def build_discord_embed(
    alert: Alert,
    follow_info: dict[str, Any] | None = None,
    copy_suggestion: dict[str, Any] | None = None,
    category_str: str = "",
) -> dict[str, Any]:
    color = DISCORD_EMBED_COLORS.get(str(alert.action), 0x95A5A6)

    fields: list[dict[str, Any]] = []

    if follow_info:
        title = "🚀 Smart Money Alert — You Follow This Trader!"
        trader_value = (
            f"`{alert.wallet[:10]}...{alert.wallet[-4:]}` (Score: {alert.wallet_score})\n"
            f"Label: {follow_info['label'] or 'N/A'}\n"
            f"Following since: {follow_info['followed_at'].strftime('%Y-%m-%d')}"
        )
        if category_str:
            trader_value += f"\n{category_str}"
        fields.append({"name": "Trader", "value": trader_value, "inline": False})
    else:
        fields.append({
            "name": "Trader",
            "value": f"`{alert.wallet[:10]}...{alert.wallet[-4:]}` (Score: {alert.wallet_score})",
            "inline": False,
        })

    fields.append({
        "name": "Action",
        "value": (
            f"**{_format_action(str(alert.action), float(alert.price))}** — {alert.category}\n"
            f"Market: {alert.market_question}\n"
            f"Price: `${float(alert.price):.4f}` | Size: `${float(alert.position_size):,.2f}`"
        ),
        "inline": False,
    })

    if copy_suggestion:
        auto_copy_status = "ON" if copy_suggestion["auto_copy_enabled"] else "OFF"
        fields.append({
            "name": "Copy Suggestion",
            "value": (
                f"Auto-copy: {auto_copy_status}\n"
                f"{' | '.join(copy_suggestion['details'])}"
            ),
            "inline": False,
        })

    return {
        "embeds": [{
            "title": title if follow_info else "🚨 Smart Money Alert",
            "color": color,
            "fields": fields,
            "footer": {"text": "Polymarket Smart Money Tracker"},
            "timestamp": alert.detected_at.isoformat(),
        }]
    }


async def send_discord_alert(embed: dict[str, Any], webhook_url: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(webhook_url, json=embed)
            return resp.status_code in (200, 204)
        except httpx.RequestError:
            return False


async def mark_notified(alert_id: str, success: bool, db: AsyncSession) -> None:
    if success:
        stmt = (
            update(Alert)
            .where(Alert.id == alert_id)
            .values(notified_at=datetime.now(timezone.utc))
        )
    else:
        stmt = (
            update(Alert)
            .where(Alert.id == alert_id)
            .values(delivery_attempts=Alert.delivery_attempts + 1)
        )
    await db.execute(stmt)
    await db.commit()
