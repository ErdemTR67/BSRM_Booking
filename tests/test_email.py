import re
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import Settings
from app.core.email import AppointmentConfirmationEmailSender, InvitationEmailSender


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://user:password@database.invalid/booking",
        "jwt_secret_key": "a-strong-test-secret-with-more-than-32-characters",
        "email_delivery_mode": "smtp",
        "smtp_host": "in-v3.mailjet.com",
        "smtp_port": 587,
        "smtp_username": "mailjet-api-key",
        "smtp_password": "mailjet-secret-key",
        "smtp_from_email": "booking@example.com",
        "smtp_use_tls": True,
        "invitation_expire_hours": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_invitation_email_uses_bosphoreum_html_and_plain_fallback() -> None:
    sender = InvitationEmailSender(_settings())

    message = sender.build_message(
        recipient="owner@example.com",
        tenant_name="Studio\nBosphoreum <Centre>",
        invitation_url="https://booking.example.com/accept-invitation?token=abc&source=email",
    )

    plain_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))
    assert plain_body is not None and html_body is not None
    plain = plain_body.get_content()
    html = html_body.get_content()

    assert message["Subject"] == "Invitation à rejoindre Studio Bosphoreum <Centre>"
    assert "Studio Bosphoreum <Centre>" in plain
    assert "expire dans 48 heures" in plain
    assert "Studio Bosphoreum &lt;Centre&gt;" in html
    assert "token=abc&amp;source=email" in html
    assert "font-family:'Big Caslon'" in html
    assert "Configurer mon compte" in html
    assert "border-radius:50%" in html

    colors = set(re.findall(r"#[0-9A-Fa-f]{6}", html.upper()))
    assert colors <= {"#000000", "#FFFFFF", "#4B4452", "#B1A8B9", "#9470BA", "#8074C8"}


def test_invitation_email_is_sent_through_mailjet_smtp(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    events: list[object] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            events.append(("connect", host, port, timeout))

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *args: object) -> None:
            events.append("close")

        def starttls(self) -> None:
            events.append("starttls")

        def login(self, username: str, password: str) -> None:
            events.append(("login", username, password))

        def send_message(self, message: EmailMessage) -> None:
            events.append(("send", message))

    monkeypatch.setattr("app.core.email.smtplib.SMTP", FakeSMTP)
    sender = InvitationEmailSender(_settings())

    sender.send(
        recipient="owner@example.com",
        tenant_name="Maison Bosphoreum",
        invitation_url="https://booking.example.com/accept-invitation?token=abc",
    )

    assert events[0] == ("connect", "in-v3.mailjet.com", 587, 15)
    assert events[1] == "starttls"
    assert events[2] == ("login", "mailjet-api-key", "mailjet-secret-key")
    assert events[3][0] == "send"  # type: ignore[index]
    sent_message = events[3][1]  # type: ignore[index]
    assert isinstance(sent_message, EmailMessage)
    assert sent_message["To"] == "owner@example.com"
    assert sent_message.get_body(preferencelist=("html",)) is not None
    assert events[4] == "close"


def test_appointment_confirmation_uses_bosphoreum_direction() -> None:
    message = AppointmentConfirmationEmailSender(_settings()).build_confirmation_message(
        recipient="client@example.com",
        customer_name="Marie <Client>",
        reference="BSRM-ABC123",
        tenant_name="Maison Bosphoreum",
        location_name="Bruxelles Centre",
        employee_name="Ada Lovelace",
        starts_at=datetime(2026, 8, 18, 9, 30, tzinfo=timezone.utc),
        ends_at=datetime(2026, 8, 18, 10, 15, tzinfo=timezone.utc),
        service_name="Consultation",
        price_cents=3900,
        currency="EUR",
    )
    html_body = message.get_body(preferencelist=("html",))
    plain_body = message.get_body(preferencelist=("plain",))
    assert html_body is not None and plain_body is not None
    html = html_body.get_content()
    assert "Marie &lt;Client&gt;" in html
    assert "BSRM-ABC123" in html
    assert "39,00 EUR" in html
    assert "font-family:'Big Caslon'" in html
    colors = set(re.findall(r"#[0-9A-Fa-f]{6}", html.upper()))
    assert colors <= {"#000000", "#FFFFFF", "#4B4452", "#B1A8B9", "#9470BA", "#8074C8"}
