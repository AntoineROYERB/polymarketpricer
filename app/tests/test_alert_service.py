"""Unit tests for the alert delivery service (pure functions + mocked HTTP/DB)."""
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import respx
from httpx import ConnectError, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert
from app.services.alert_service import (
    DISCORD_EMBED_COLORS,
    _format_action,
    build_discord_embed,
    classify_action,
    mark_notified,
    poll_unnotified_alerts,
    send_discord_alert,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEBHOOK_URL = "https://discord.com/api/webhooks/test/test"


def make_alert(**overrides: Any) -> Alert:
    """Build a minimal Alert instance with sensible defaults."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "wallet": "0x1234567890abcdef1234567890abcdef12345678",
        "market_id": "market_001",
        "market_question": "Will BTC reach $100k by EOY?",
        "action": "NEW_POSITION",
        "price": 0.7500,
        "position_size": 5000.00,
        "wallet_score": 85.5,
        "category": "crypto",
        "detected_at": datetime.now(timezone.utc),
        "notified_at": None,
        "delivery_attempts": 0,
    }
    defaults.update(overrides)
    return Alert(**defaults)


def make_mock_db(alert: Alert | None = None) -> AsyncMock:
    """Create an AsyncSession mock that returns the given alert on scalar queries."""
    session = AsyncMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [alert] if alert else []
    mock_result.scalar_one_or_none.return_value = alert

    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    return session


# ===========================================================================
# classify_action  (pure function)
# ===========================================================================

class TestClassifyAction:
    def test_new_position_from_none(self) -> None:
        assert classify_action(None, 100.0) == "NEW_POSITION"

    def test_new_position_from_zero(self) -> None:
        assert classify_action(0, 100.0) == "NEW_POSITION"

    def test_position_increase(self) -> None:
        assert classify_action(50.0, 100.0) == "POSITION_INCREASE"

    def test_position_decrease(self) -> None:
        assert classify_action(100.0, 50.0) == "POSITION_DECREASE"

    def test_full_exit(self) -> None:
        assert classify_action(100.0, 0) == "FULL_EXIT"

    def test_no_change_zero(self) -> None:
        assert classify_action(0, 0) is None

    def test_no_change_equal(self) -> None:
        assert classify_action(100.0, 100.0) is None

    def test_no_change_all_none(self) -> None:
        assert classify_action(None, None) is None

    def test_no_change_none_zero(self) -> None:
        assert classify_action(None, 0) is None

    def test_no_change_zero_none(self) -> None:
        assert classify_action(0, None) is None

    def test_decrease_from_none_not_possible(self) -> None:
        assert classify_action(None, 50.0) == "NEW_POSITION"

    def test_negative_values(self) -> None:
        assert classify_action(-10, -5) == "POSITION_INCREASE"
        assert classify_action(-5, -10) is None


# ===========================================================================
# _format_action  (pure function)
# ===========================================================================

class TestFormatAction:
    def test_new_position(self) -> None:
        result = _format_action("NEW_POSITION", 0.5)
        assert result == "BUY (New Position @ $0.5000)"

    def test_position_increase(self) -> None:
        result = _format_action("POSITION_INCREASE", 0.7500)
        assert result == "BUY (Increase @ $0.7500)"

    def test_position_decrease(self) -> None:
        result = _format_action("POSITION_DECREASE", 0.2500)
        assert result == "SELL (Decrease @ $0.2500)"

    def test_full_exit(self) -> None:
        result = _format_action("FULL_EXIT", 1.2340)
        assert result == "SELL (Full Exit @ $1.2340)"

    def test_unknown_action_fallback(self) -> None:
        result = _format_action("UNKNOWN", 0.5)
        assert result == "UNKNOWN"

    def test_price_formatting_precision(self) -> None:
        result = _format_action("NEW_POSITION", 0.123456)
        assert "0.1235" in result

    def test_large_price(self) -> None:
        result = _format_action("FULL_EXIT", 99999.9999)
        assert result == "SELL (Full Exit @ $99999.9999)"


# ===========================================================================
# build_discord_embed  (pure function)
# ===========================================================================

class TestBuildDiscordEmbed:
    def test_basic_embed_shape(self) -> None:
        alert = make_alert(action="NEW_POSITION", category="crypto")
        embed = build_discord_embed(alert)
        assert "embeds" in embed
        assert len(embed["embeds"]) == 1
        e = embed["embeds"][0]
        assert e["title"] == "🚨 Smart Money Alert"
        assert e["color"] == DISCORD_EMBED_COLORS["NEW_POSITION"]
        fields = {f["name"]: f["value"] for f in e["fields"]}
        assert "Trader" in fields
        assert "Action" in fields

    def test_embed_with_follow_info(self) -> None:
        alert = make_alert()
        follow_info = {"label": "Test Whale", "followed_at": datetime.now(timezone.utc)}
        embed = build_discord_embed(alert, follow_info=follow_info)
        e = embed["embeds"][0]
        assert "You Follow This Trader" in e["title"]
        assert "Test Whale" in e["fields"][0]["value"]

    def test_embed_with_copy_suggestion(self) -> None:
        alert = make_alert()
        copy_suggestion = {"auto_copy_enabled": True, "details": ["Mode: 5% proportional"]}
        embed = build_discord_embed(alert, copy_suggestion=copy_suggestion)
        e = embed["embeds"][0]
        fields = {f["name"]: f["value"] for f in e["fields"]}
        assert "Copy Suggestion" in fields

    def test_embed_color_by_action(self) -> None:
        for action, expected_color in DISCORD_EMBED_COLORS.items():
            alert = make_alert(action=action)
            embed = build_discord_embed(alert)
            assert embed["embeds"][0]["color"] == expected_color

    def test_unknown_action_color_fallback(self) -> None:
        alert = make_alert(action="UNKNOWN_ACTION")
        embed = build_discord_embed(alert)
        assert embed["embeds"][0]["color"] == 0x95A5A6


# ===========================================================================
# send_discord_alert  (HTTP via respx)
# ===========================================================================

class TestSendDiscordAlert:
    @pytest.mark.asyncio
    async def test_success_204(self) -> None:
        alert = make_alert()
        embed = build_discord_embed(alert)
        async with respx.mock:
            route = respx.post(WEBHOOK_URL).mock(return_value=Response(204))
            result = await send_discord_alert(embed, WEBHOOK_URL)
        assert result is True
        assert route.called

    @pytest.mark.asyncio
    async def test_success_200(self) -> None:
        alert = make_alert()
        embed = build_discord_embed(alert)
        async with respx.mock:
            route = respx.post(WEBHOOK_URL).mock(return_value=Response(200))
            result = await send_discord_alert(embed, WEBHOOK_URL)
        assert result is True
        assert route.called

    @pytest.mark.asyncio
    async def test_http_500(self) -> None:
        alert = make_alert()
        embed = build_discord_embed(alert)
        async with respx.mock:
            route = respx.post(WEBHOOK_URL).mock(return_value=Response(500))
            result = await send_discord_alert(embed, WEBHOOK_URL)
        assert result is False
        assert route.called

    @pytest.mark.asyncio
    async def test_http_400(self) -> None:
        alert = make_alert()
        embed = build_discord_embed(alert)
        async with respx.mock:
            route = respx.post(WEBHOOK_URL).mock(return_value=Response(400))
            result = await send_discord_alert(embed, WEBHOOK_URL)
        assert result is False
        assert route.called

    @pytest.mark.asyncio
    async def test_network_timeout(self) -> None:
        alert = make_alert()
        embed = build_discord_embed(alert)
        async with respx.mock:
            route = respx.post(WEBHOOK_URL).mock(
                side_effect=ConnectError("Connection timeout"),
            )
            result = await send_discord_alert(embed, WEBHOOK_URL)
        assert result is False
        assert route.called

    @pytest.mark.asyncio
    async def test_payload_shape(self) -> None:
        """Verify the JSON payload sent to Discord matches expected structure."""
        alert = make_alert(action="NEW_POSITION", category="crypto")
        embed = build_discord_embed(alert)
        captured: dict[str, Any] = {}

        async with respx.mock:
            async def capture(request: Request) -> Response:
                captured["json"] = json.loads(request.content)
                return Response(204)

            respx.post(WEBHOOK_URL).mock(side_effect=capture)
            await send_discord_alert(embed, WEBHOOK_URL)

        payload = captured["json"]
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1
        e = payload["embeds"][0]
        assert e["title"] is not None
        assert e["color"] == DISCORD_EMBED_COLORS["NEW_POSITION"]
        fields = {f["name"]: f["value"] for f in e["fields"]}
        assert "Trader" in fields
        assert "Action" in fields
        assert "BUY (New Position" in fields["Action"]

    @pytest.mark.asyncio
    async def test_color_by_action(self) -> None:
        """Each action type should use the correct embed color."""
        async with respx.mock:
            for action, expected_color in DISCORD_EMBED_COLORS.items():
                alert = make_alert(action=action)
                embed = build_discord_embed(alert)
                captured: dict[str, Any] = {}

                async def capture(req: Request, _c: dict[str, Any] = captured) -> Response:
                    _c["json"] = json.loads(req.content)
                    return Response(204)

                route = respx.post(WEBHOOK_URL).mock(side_effect=capture)
                await send_discord_alert(embed, WEBHOOK_URL)
                assert captured["json"]["embeds"][0]["color"] == expected_color
                route.reset()

    @pytest.mark.asyncio
    async def test_unknown_action_color(self) -> None:
        alert = make_alert(action="UNKNOWN_ACTION")
        embed = build_discord_embed(alert)
        captured: dict[str, Any] = {}

        async with respx.mock:
            async def capture(req: Request) -> Response:
                captured["json"] = json.loads(req.content)
                return Response(204)

            respx.post(WEBHOOK_URL).mock(side_effect=capture)
            await send_discord_alert(embed, WEBHOOK_URL)

        assert captured["json"]["embeds"][0]["color"] == 0x95A5A6


# ===========================================================================
# poll_unnotified_alerts
# ===========================================================================

class TestPollUnnotifiedAlerts:
    @pytest.mark.asyncio
    async def test_returns_alerts(self) -> None:
        alert = make_alert()
        db = make_mock_db(alert)
        results = await poll_unnotified_alerts(db)
        assert len(results) == 1
        assert results[0] is alert
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_when_no_alerts(self) -> None:
        db = make_mock_db()
        results = await poll_unnotified_alerts(db)
        assert results == []

    @pytest.mark.asyncio
    async def test_sql_filter_notified_at_is_null(self) -> None:
        db = make_mock_db()
        await poll_unnotified_alerts(db)
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "notified_at" in compiled
        assert "NULL" in compiled.upper()

    @pytest.mark.asyncio
    async def test_sql_filter_delivery_attempts(self) -> None:
        db = make_mock_db()
        await poll_unnotified_alerts(db)
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "delivery_attempts" in compiled

    @pytest.mark.asyncio
    async def test_ordering_and_limit(self) -> None:
        db = make_mock_db()
        await poll_unnotified_alerts(db)
        call_stmt = db.execute.call_args[0][0]
        compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "ORDER BY" in compiled
        assert "detected_at" in compiled
        assert "LIMIT" in compiled.upper()
        assert "20" in compiled


# ===========================================================================
# mark_notified
# ===========================================================================

class TestMarkNotified:
    @pytest.mark.asyncio
    async def test_success_sets_notified_at(self) -> None:
        alert = make_alert()
        db = make_mock_db(alert)
        await mark_notified(str(alert.id), success=True, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
        call_args = db.execute.call_args
        stmt = str(call_args[0][0].compile())
        assert "UPDATE" in stmt.upper()
        assert "notified_at" in stmt

    @pytest.mark.asyncio
    async def test_failure_increments_delivery_attempts(self) -> None:
        alert = make_alert(delivery_attempts=0)
        db = make_mock_db(alert)
        await mark_notified(str(alert.id), success=False, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
        call_args = db.execute.call_args
        stmt = str(call_args[0][0].compile())
        assert "UPDATE" in stmt.upper()
        assert "delivery_attempts" in stmt

    @pytest.mark.asyncio
    async def test_failure_increments_twice(self) -> None:
        alert = make_alert(delivery_attempts=2)
        db = make_mock_db(alert)
        await mark_notified(str(alert.id), success=False, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_noop_when_alert_not_found(self) -> None:
        db = make_mock_db()
        await mark_notified(str(uuid4()), success=True, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_correct_uuid_filter(self) -> None:
        alert_id = uuid4()
        alert = make_alert(id=alert_id)
        db = make_mock_db(alert)
        await mark_notified(str(alert_id), success=True, db=db)
        call_args = db.execute.call_args
        assert call_args is not None
        stmt = call_args[0][0]
        sql = str(stmt.compile())
        assert "UPDATE" in sql.upper()
        assert "WHERE" in sql


# ===========================================================================
# Edge cases: combined scenarios
# ===========================================================================

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_mark_notified_after_send_success(self) -> None:
        alert = make_alert(delivery_attempts=0, notified_at=None)
        embed = build_discord_embed(alert)
        db = make_mock_db(alert)

        async with respx.mock:
            respx.post(WEBHOOK_URL).mock(return_value=Response(204))
            success = await send_discord_alert(embed, WEBHOOK_URL)

        assert success is True

        await mark_notified(str(alert.id), success=True, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
        call_args = db.execute.call_args
        stmt = str(call_args[0][0].compile())
        assert "UPDATE" in stmt.upper()
        assert "notified_at" in stmt

    @pytest.mark.asyncio
    async def test_retry_after_failure(self) -> None:
        alert = make_alert(delivery_attempts=0, notified_at=None)
        embed = build_discord_embed(alert)
        db = make_mock_db(alert)

        async with respx.mock:
            respx.post(WEBHOOK_URL).mock(return_value=Response(500))
            success = await send_discord_alert(embed, WEBHOOK_URL)

        assert success is False

        await mark_notified(str(alert.id), success=False, db=db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
        call_args = db.execute.call_args
        stmt = str(call_args[0][0].compile())
        assert "UPDATE" in stmt.upper()
        assert "delivery_attempts" in stmt
