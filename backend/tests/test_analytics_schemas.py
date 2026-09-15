from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AnalyticsEventRequest, FeedbackRequest


def test_analytics_rejects_unapproved_or_sensitive_property() -> None:
    with pytest.raises(ValidationError):
        AnalyticsEventRequest(
            event_id=uuid4(),
            event_name="answer_accepted",
            session_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
            properties={"answer_text": "不应进入埋点"},
        )


def test_feedback_requires_valid_score_and_fixed_choices() -> None:
    with pytest.raises(ValidationError):
        FeedbackRequest(
            satisfaction_score=6,
            payment_willingness="willing",
            tags=[],
            completion_type="completed",
        )


def test_feedback_accepts_reviewed_product_fields() -> None:
    value = FeedbackRequest(
        satisfaction_score=4,
        payment_willingness="depends_on_price",
        tags=["追问有深度"],
        comment="希望响应更快",
        completion_type="ended_early",
    )
    assert value.satisfaction_score == 4
