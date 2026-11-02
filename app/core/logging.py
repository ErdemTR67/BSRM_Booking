import logging
from contextvars import ContextVar, Token


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def configure_logging(*, debug: bool) -> None:
    root_logger = logging.getLogger()
    handler = next(
        (
            existing
            for existing in root_logger.handlers
            if getattr(existing, "_bsrm_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler._bsrm_handler = True  # type: ignore[attr-defined]
        handler.addFilter(RequestContextFilter())
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
            )
        )
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)


def set_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)
