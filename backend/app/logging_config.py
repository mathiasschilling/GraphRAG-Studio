import logging
from logging import Logger


def setup_logging() -> Logger:
    """Configure basic logging for the service and return a shared logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    return logging.getLogger("graphrag")
