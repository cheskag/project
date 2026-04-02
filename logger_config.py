import logging
import os
from logging.handlers import RotatingFileHandler


def _ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def setup_logger(name: str = "scraper", filename: str = "scraper.log") -> logging.Logger:
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    _ensure_dir(logs_dir)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_path = os.path.join(logs_dir, filename)
    file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(console)

    return logger


def log_security_event(message: str) -> None:
    logger = setup_logger(name="security", filename="security.log")
    logger.warning(message)


def log_scraping_activity(message: str) -> None:
    logger = setup_logger(name="scraper", filename="scraper.log")
    logger.info(message)





