import logging
import sys


def setup_logging(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        f"%(asctime)s | %(levelname)s | {service_name} | %(message)s"
    ))
    logger.addHandler(handler)
    logger.propagate = False
    return logger