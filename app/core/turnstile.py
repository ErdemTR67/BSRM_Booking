import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.exceptions import PublicBookingChallengeError, ServiceUnavailableError


class TurnstileVerifier:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def verify(
        self,
        token: str | None,
        *,
        remote_ip: str | None,
        idempotency_key: UUID,
        allowed_hostnames: set[str],
    ) -> None:
        if self.settings.public_booking_challenge_mode == "disabled":
            return
        if not token or len(token) > 2_048:
            raise PublicBookingChallengeError()
        secret = self.settings.turnstile_secret_key
        if secret is None:
            raise ServiceUnavailableError("The anti-abuse service is not configured.")
        body: dict[str, str] = {
            "secret": secret.get_secret_value(),
            "response": token,
            "idempotency_key": str(idempotency_key),
        }
        if remote_ip:
            body["remoteip"] = remote_ip
        request = Request(
            self.settings.turnstile_verify_url,
            data=urlencode(body).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=8) as response:  # noqa: S310
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ServiceUnavailableError("The anti-abuse service could not be reached.") from error
        if (
            result.get("success") is not True
            or result.get("hostname") not in allowed_hostnames
            or result.get("action") != self.settings.turnstile_expected_action
        ):
            raise PublicBookingChallengeError()
