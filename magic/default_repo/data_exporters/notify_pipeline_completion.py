if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
import httpx
import os
import time

from default_repo.utils.db_helpers import DATABASE_URL

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

CATEGORY_EMOJI = {
    "politics": "\U0001F5F3",
    "crypto": "\U0001F4B0",
    "sports": "\u26BD",
    "economics": "\U0001F4CA",
    "technology": "\U0001F4BB",
    "ai": "\U0001F916",
    "geopolitics": "\U0001F30D",
    "entertainment": "\U0001F3AC",
}

CATEGORY_LABEL = {
    "politics": "Politics",
    "crypto": "Crypto",
    "sports": "Sports",
    "economics": "Economics",
    "technology": "Technology",
    "ai": "AI",
    "geopolitics": "Geopolitics",
    "entertainment": "Entertainment",
}


def _resolve_pipeline_start(kwargs: dict) -> float:
    pipeline_run = kwargs.get("pipeline_run")
    if pipeline_run is not None:
        started_at = getattr(pipeline_run, "started_at", None)
        if started_at is not None:
            return started_at.timestamp()
    execution_date = kwargs.get("execution_date")
    if execution_date is not None:
        return execution_date.timestamp()
    return time.time()


def _resolve_since(kwargs: dict) -> datetime:
    pipeline_run = kwargs.get("pipeline_run")
    if pipeline_run is not None:
        started_at = getattr(pipeline_run, "started_at", None)
        if started_at is not None:
            if isinstance(started_at, (int, float)):
                return datetime.fromtimestamp(started_at, tz=timezone.utc)
            return started_at
    execution_date = kwargs.get("execution_date")
    if execution_date is not None:
        if isinstance(execution_date, (int, float)):
            return datetime.fromtimestamp(execution_date, tz=timezone.utc)
        return execution_date
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _short_addr(wallet: str) -> str:
    return f"{wallet[:10]}...{wallet[-4:]}"


def _build_content(
    start_time: float,
    since: datetime,
    engine,
) -> str:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    with engine.connect() as conn:
        new_wallets = conn.execute(
            text("SELECT COUNT(*) FROM wallets WHERE first_seen >= :since"),
            {"since": since},
        ).scalar() or 0

        new_markets = conn.execute(
            text("SELECT COUNT(*) FROM markets WHERE created_at >= :since"),
            {"since": since},
        ).scalar() or 0

        total_wallets = conn.execute(
            text("SELECT COUNT(*) FROM wallets WHERE is_tracked = true")
        ).scalar() or 0

        total_markets = conn.execute(
            text("SELECT COUNT(*) FROM markets")
        ).scalar() or 0

        rows = conn.execute(
            text("""
                WITH top_per_category AS (
                    SELECT DISTINCT ON (ca.category)
                        ca.category,
                        ca.wallet,
                        wa.wallet_score,
                        w.label
                    FROM category_analytics ca
                    JOIN wallet_analytics wa
                        ON wa.wallet = ca.wallet
                        AND wa.snapshot_date = ca.snapshot_date
                    LEFT JOIN wallets w ON w.wallet = ca.wallet
                    WHERE ca.snapshot_date = CURRENT_DATE
                        AND wa.wallet_score IS NOT NULL
                    ORDER BY ca.category, wa.wallet_score DESC
                )
                SELECT
                    tw.category,
                    tw.wallet,
                    tw.wallet_score,
                    tw.label,
                    m.question AS market_question
                FROM top_per_category tw
                LEFT JOIN LATERAL (
                    SELECT m.question
                    FROM trades t
                    JOIN markets m ON m.id = t.market_id
                    WHERE t.wallet = tw.wallet
                        AND m.mapped_category = tw.category
                    ORDER BY t.timestamp DESC
                    LIMIT 1
                ) m ON true
                ORDER BY tw.category
            """),
        ).mappings().all()

    lines = [
        "\U0001F680 Orchestration Pipeline Completed",
        "",
        f"\U0001F4C5 Timestamp: {timestamp}",
        f"\u2705 Status: Success (\u23F1 {minutes}m {seconds}s)",
        "",
        "\U0001F4CA Data Update",
        f"\u2022 New wallets added: {new_wallets:,}",
        f"\u2022 New markets added: {new_markets:,}",
        f"\u2022 Total wallets tracked: {total_wallets:,}",
        f"\u2022 Total markets tracked: {total_markets:,}",
        "",
    ]

    if rows:
        lines.append("\U0001F3C6 Top Wallets by Category")
        lines.append("")
        for row in rows:
            cat = row["category"]
            emoji = CATEGORY_EMOJI.get(cat, "\U0001F4CB")
            label = CATEGORY_LABEL.get(cat, cat.capitalize())
            display = row["label"] or _short_addr(row["wallet"])
            score = float(row["wallet_score"])
            score_fmt = f"**{score:.1f}**" if score >= 95 else f"{score:.1f}"
            question = row.get("market_question")
            if question and len(question) > 120:
                question = question[:117] + "..."
            question = question or "Recently active in this category"

            lines.append(f"{emoji} {label}")
            lines.append(f"\u2022 Wallet: `{display}`")
            lines.append(f"\u2022 Wallet Score: {score_fmt}")
            lines.append(f"\u2022 Market: \"{question}\"")
            lines.append("\u2022 Platform: Polymarket")
            lines.append("")
    else:
        lines.append("\U0001F3C6 Top Wallets by Category")
        lines.append("")
        lines.append("No category data available for this run.")
        lines.append("")

    n_cats = len(rows)
    lines.append(
        f"\u2705 Pipeline completed successfully across {n_cats} categories. "
        f"Tracking {total_wallets:,} wallets and {total_markets:,} markets."
    )

    msg = "\n".join(lines)

    if len(msg) > 1900:
        msg = msg[:1897] + "..."

    return msg


@data_exporter
def export_data(data, **kwargs) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set \u2014 skipping notification")
        return

    start_time = _resolve_pipeline_start(kwargs)
    since = _resolve_since(kwargs)

    engine = create_engine(DATABASE_URL)
    try:
        content = _build_content(start_time, since, engine)

        payload = {"content": content}
        resp = httpx.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10.0)
        if resp.status_code in (200, 204):
            print("Pipeline completion notification sent to Discord")
        else:
            print(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")
    except httpx.RequestError as e:
        print(f"Failed to send Discord notification: {e}")
    except Exception as e:
        print(f"Error building notification: {e}")
    finally:
        engine.dispose()


@test
def test_output(*args) -> None:
    pass
