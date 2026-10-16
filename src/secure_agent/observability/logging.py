import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from secure_agent.config import LOG_DIR


logger = logging.getLogger("secure_agent.audit")
logger.setLevel(logging.INFO)
logger.propagate = False


def configure_logging() -> None:
    if logger.handlers:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=LOG_DIR / "audit.jsonl",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    handler.setFormatter(
        logging.Formatter("%(message)s")
    )

    logger.addHandler(handler)


def audit(
    event: str,
    request_id: str,
    **fields,
) -> None:
    configure_logging()

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "request_id": request_id,
        **fields,
    }

    logger.info(
        json.dumps(record, ensure_ascii=False)
    )