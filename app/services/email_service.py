"""Minimal SMTP delivery for scheduled recommendation digests."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from decimal import Decimal
from email.message import EmailMessage
from typing import Sequence

from app.core.config import Settings, settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DigestProduct:
    """Catalog-grounded display data for one recommended product."""

    title: str
    category: str
    price: Decimal
    reason: str


class EmailService:
    """Send plain-text recommendation digests when SMTP is configured."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool,
        timeout_seconds: int,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, config: Settings = settings) -> "EmailService":
        """Build an SMTP service from the application's optional settings."""
        return cls(
            host=config.smtp_host,
            port=config.smtp_port,
            username=config.smtp_username,
            password=config.smtp_password,
            from_email=config.smtp_from_email,
            use_tls=config.smtp_use_tls,
            timeout_seconds=config.smtp_timeout_seconds,
        )

    @property
    def is_configured(self) -> bool:
        """Return whether delivery has the minimum required SMTP settings."""
        return bool(self.host and self.from_email)

    def send_recommendation_digest(
        self,
        *,
        recipient_email: str,
        narrative: str,
        products: Sequence[DigestProduct],
    ) -> bool:
        """Send one catalog-grounded digest, returning false when not delivered."""
        if not self.is_configured:
            logger.warning("Scheduled recommendation email skipped: SMTP is not configured")
            return False
        if not products:
            logger.warning("Scheduled recommendation email skipped: no valid products")
            return False

        message = self._build_message(
            recipient_email=recipient_email,
            narrative=narrative,
            products=products,
        )
        smtp: smtplib.SMTP | None = None
        try:
            smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds)
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
            return True
        except (OSError, smtplib.SMTPException):
            logger.exception("Scheduled recommendation email delivery failed")
            return False
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except (OSError, smtplib.SMTPException):
                    logger.debug("SMTP connection closed without quit acknowledgement")

    def _build_message(
        self,
        *,
        recipient_email: str,
        narrative: str,
        products: Sequence[DigestProduct],
    ) -> EmailMessage:
        """Create the plain-text digest from existing recommendation data only."""
        message = EmailMessage()
        message["To"] = recipient_email
        message["From"] = self.from_email
        message["Subject"] = "Your SmartReco recommendations"
        lines = [narrative, "", "Recommended for you:", ""]
        for position, product in enumerate(products, start=1):
            lines.extend(
                [
                    f"{position}. {product.title}",
                    f"   Category: {product.category}",
                    f"   Price: {product.price:.2f}",
                    f"   Why: {product.reason}",
                    "",
                ]
            )
        message.set_content("\n".join(lines).rstrip() + "\n")
        return message
