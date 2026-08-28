# Phase 5 — Follow & Paper Trading — Enhanced Discord Alerts

> **Goal**: When a followed wallet triggers an alert, enrich the Discord notification with follow status and copy-trade suggestion.
> **AI Agent Instructions**: Modify `app/services/alert_service.py` — extend `_format_discord_embed()` to detect followed wallets and append copy suggestion fields.

---

## Current Alert Embed

Currently the Discord embed looks like:

```
🚀 Smart Money Alert
Trader: 0x1234...5678
Score: 89
Category: Politics
Action: BUY YES
Market: Will candidate X win?
Price: 0.42
Position Size: $12,000
```

## Enhanced Alert Embed (Followed Wallet)

When the alert.wallet is being followed by the user:

```
🚀 Smart Money Alert — You Follow This Trader!

👤 Trader: 0x1234...5678 (Score: 89)
   Label: Politics whale
   Followed since: 2026-06-20
   🏆 Best categories: Politics (FOLLOW, 0.92), Crypto (WATCH, 0.45)

📊 Action: **BUY YES**
   Market: Will candidate X win?
   Price: $0.42
   Position Size: $12,000

📋 **Copy Suggestion**
   Auto-copy: ✅ ON (5% proportional)
   Suggested amount: **$600** at $0.42
   Category filter: Politics, Crypto ✓
```

Colour coding:
- Green (`0x00FF00`) — NEW_POSITION
- Blue (`0x3498DB`) — POSITION_INCREASE
- Orange (`0xF39C12`) — POSITION_DECREASE
- Red (`0xE74C3C`) — FULL_EXIT

When wallet is **not** followed: same embed as current (no changes).

---

## Implementation

### Extended Embed Builder

```python
# In app/services/alert_service.py

async def _format_discord_embed(
    alert: Alert,
    follow_info: Optional[dict] = None,
    copy_suggestion: Optional[dict] = None,
) -> dict:
    """Build Discord embed with optional follow and copy info."""

    colors = {
        "NEW_POSITION": 0x00FF00,
        "POSITION_INCREASE": 0x3498DB,
        "POSITION_DECREASE": 0xF39C12,
        "FULL_EXIT": 0xE74C3C,
        "TRADE_BUY": 0x00FF00,
        "TRADE_SELL": 0xE74C3C,
        "FIRST_MOVER": 0x9B59B6,
    }

    embed = {
        "title": "🚀 Smart Money Alert",
        "color": colors.get(alert.action, 0x808080),
        "fields": [],
        "timestamp": alert.detected_at.isoformat(),
    }

    # ── Follow info block ────────────────────────────────────────────
    if follow_info:
        embed["title"] = "🚀 Smart Money Alert — You Follow This Trader!"
        embed["fields"].append({
            "name": "👤 Trader",
            "value": (
                f"`{alert.wallet[:6]}...{alert.wallet[-4:]}` (Score: {alert.wallet_score:.0f})\n"
                f"📌 Label: {follow_info['label'] or 'N/A'}\n"
                f"📅 Following since: {follow_info['followed_at'].strftime('%Y-%m-%d')}"
            ),
            "inline": False,
        })
    else:
        embed["fields"].append({
            "name": "👤 Trader",
            "value": f"`{alert.wallet[:6]}...{alert.wallet[-4:]}` (Score: {alert.wallet_score:.0f})",
            "inline": False,
        })

    # ── Action block ─────────────────────────────────────────────────
    embed["fields"].append({
        "name": "📊 Action",
        "value": (
            f"**{alert.action}** — {alert.category}\n"
            f"📈 {alert.market_question}\n"
            f"💰 Price: `${alert.price}` | Size: `${alert.position_size:,.0f}`"
        ),
        "inline": False,
    })

    # ── Copy suggestion block ────────────────────────────────────────
    if copy_suggestion:
        auto_copy_status = "✅ ON" if copy_suggestion["auto_copy_enabled"] else "❌ OFF"
        embed["fields"].append({
            "name": "📋 Copy Suggestion",
            "value": (
                f"Auto-copy: {auto_copy_status}\n"
                f"{' | '.join(copy_suggestion['details'])}"
            ),
            "inline": False,
        })

    return embed
```

### Category Scores in Embed

When building the embed, also include the wallet's top category scores:

```python
async def _get_top_category_scores(db: AsyncSession, wallet: str) -> str:
    """Get wallet's top 2 category follow scores as a formatted string."""
    result = await db.execute(
        text("""
            SELECT category, follow_score, recommendation
            FROM wallet_category_follow_scores
            WHERE wallet = :wallet
              AND snapshot_date = CURRENT_DATE
            ORDER BY follow_score DESC
            LIMIT 2
        """),
        {"wallet": wallet},
    )
    rows = result.all()
    if not rows:
        return ""
    parts = []
    for r in rows:
        emoji = "🟢" if r.recommendation == "FOLLOW" else "🟡" if r.recommendation == "WATCH" else "🔴"
        parts.append(f"{r.category} ({emoji} {r.recommendation}, {float(r.follow_score):.2f})")
    return " | ".join(parts)
```

Then add the category scores line to the Trader field in the embed:

```python
category_str = await _get_top_category_scores(db, alert.wallet)
if category_str:
    trader_value += f"\n🏆 {category_str}"
```

### Follow Info & Copy Suggestion Lookup

```python
async def _get_follow_info(
    db: AsyncSession, wallet: str
) -> tuple[Optional[dict], Optional[dict]]:
    """
    Look up if wallet is followed and compute copy suggestion.
    Returns (follow_info, copy_suggestion) or (None, None).
    """
    from app.db.models import WalletFollow

    result = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == "default",
            WalletFollow.wallet == wallet,
            WalletFollow.active == True,
        )
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        return None, None

    follow_info = {
        "label": follow.label,
        "followed_at": follow.followed_at,
    }

    copy_suggestion = None
    if follow.auto_copy_enabled:
        copy_suggestion = {
            "auto_copy_enabled": True,
            "details": [],
        }

        if follow.copy_mode == "proportional":
            pct = float(follow.copy_value) * 100
            copy_suggestion["details"].append(f"📐 Mode: {pct:.1f}% proportional")
        elif follow.copy_mode == "fixed":
            copy_suggestion["details"].append(f"📐 Mode: ${follow.copy_value} fixed")

        if follow.category_filter:
            cats = ", ".join(follow.category_filter)
            copy_suggestion["details"].append(f"🎯 Filter: {cats} ✓")
        else:
            copy_suggestion["details"].append("🎯 Filter: All categories")

    return follow_info, copy_suggestion
```

### Modified Alert Delivery Loop

Update `alert_delivery_loop` in `app/services/alert_service.py` to include follow info:

```python
async def poll_unnotified_alerts(db: AsyncSession):
    """Poll for unnotified alerts and deliver with enhanced follow info."""
    while True:
        try:
            result = await db.execute(
                text("""
                    SELECT * FROM alerts
                    WHERE notified_at IS NULL
                      AND delivery_attempts < 3
                    ORDER BY detected_at
                    LIMIT 20
                """)
            )
            alerts = result.all()

            for alert in alerts:
                follow_info, copy_suggestion = await _get_follow_info(db, alert.wallet)
                embed = await _format_discord_embed(alert, follow_info, copy_suggestion)

                # Send Discord
                if settings.DISCORD_WEBHOOK_URL:
                    await send_discord_alert(embed, settings.DISCORD_WEBHOOK_URL)

                # Broadcast WebSocket
                await manager.broadcast_alert({
                    "type": "alert",
                    "payload": alert_to_dict(alert, follow_info, copy_suggestion),
                })

                # Mark notified
                await mark_notified(db, alert.id)

        except Exception as e:
            logger.error(f"Alert delivery error: {e}")
        await asyncio.sleep(settings.ALERT_POLL_INTERVAL_SECONDS)
```

---

## WebSocket Payload Extension

Extend the WebSocket alert payload with optional follow/copy fields:

```json
{
  "type": "alert",
  "payload": {
    "id": "uuid",
    "wallet": "0x1234...abcd",
    "action": "NEW_POSITION",
    "market_question": "Will candidate X win?",
    "price": 0.42,
    "position_size": 12000,
    "wallet_score": 89,
    "category": "Politics",
    "follow_info": {
      "label": "Politics whale",
      "followed_at": "2026-06-20T00:00:00Z"
    },
    "copy_suggestion": {
      "auto_copy_enabled": true,
      "details": ["Mode: 5% proportional", "Filter: Politics ✓"]
    }
  }
}
```

---

## Files to Modify

| Action | Path |
|--------|------|
| EDIT | `app/services/alert_service.py` — add `_get_follow_info`, `_get_top_category_scores`, extend `_format_discord_embed`, update delivery loop |

---

## Verification

```bash
# 1. Follow a wallet
curl -X POST "http://localhost:8000/api/v1/follow/0xrealwallet...addr"

# 2. Wait for an alert from that wallet
# Check Discord for enhanced embed with "You Follow This Trader!" title

# 3. Verify non-followed wallets still show standard embed
```
