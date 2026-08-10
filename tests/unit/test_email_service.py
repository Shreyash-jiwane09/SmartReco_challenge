"""Focused tests for standard-library SMTP recommendation digest delivery."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from app.services import email_service
from app.services.email_service import DigestProduct, EmailService


def _service(**overrides: object) -> EmailService:
    values = {
        "host": "smtp.example.com",
        "port": 587,
        "username": "mailer",
        "password": "secret",
        "from_email": "recommendations@example.com",
        "use_tls": True,
        "timeout_seconds": 10,
    }
    values.update(overrides)
    return EmailService(**values)


def _products() -> list[DigestProduct]:
    return [
        DigestProduct(
            title="Agentic AI Fundamentals",
            category="AI",
            price=Decimal("79.00"),
            reason="Matches your recent agentic AI interest.",
        )
    ]


def test_email_service_builds_and_sends_a_catalog_grounded_digest(monkeypatch) -> None:
    smtp = Mock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: smtp)

    delivered = _service().send_recommendation_digest(
        recipient_email="learner@example.com",
        narrative="A tailored path for your interests.",
        products=_products(),
    )

    assert delivered is True
    smtp.starttls.assert_called_once_with()
    smtp.login.assert_called_once_with("mailer", "secret")
    smtp.send_message.assert_called_once()
    smtp.quit.assert_called_once_with()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "learner@example.com"
    assert message["From"] == "recommendations@example.com"
    assert message["Subject"] == "Your SmartReco recommendations"
    assert "A tailored path for your interests." in message.get_content()
    assert "Agentic AI Fundamentals" in message.get_content()
    assert "Category: AI" in message.get_content()
    assert "Price: 79.00" in message.get_content()


def test_email_service_skips_tls_and_login_when_not_configured(monkeypatch) -> None:
    smtp = Mock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: smtp)

    delivered = _service(use_tls=False, username="", password="").send_recommendation_digest(
        recipient_email="learner@example.com",
        narrative="Narrative.",
        products=_products(),
    )

    assert delivered is True
    smtp.starttls.assert_not_called()
    smtp.login.assert_not_called()
    smtp.send_message.assert_called_once()


def test_email_service_skips_delivery_when_smtp_is_not_configured(monkeypatch) -> None:
    smtp_factory = Mock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", smtp_factory)

    delivered = _service(host="", from_email="").send_recommendation_digest(
        recipient_email="learner@example.com",
        narrative="Narrative.",
        products=_products(),
    )

    assert delivered is False
    smtp_factory.assert_not_called()


def test_email_service_logs_smtp_errors_without_raising(monkeypatch, caplog) -> None:
    smtp = Mock()
    smtp.send_message.side_effect = email_service.smtplib.SMTPException("unavailable")
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: smtp)

    delivered = _service().send_recommendation_digest(
        recipient_email="learner@example.com",
        narrative="Narrative.",
        products=_products(),
    )

    assert delivered is False
    assert "delivery failed" in caplog.text
    assert "secret" not in caplog.text
