import logging
from pythonjsonlogger.json import JsonFormatter


def setup_logger():
    logger = logging.getLogger()
    if logger.handlers:
        return
    logHandler = logging.StreamHandler()
    formatter = JsonFormatter()
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.DEBUG)
