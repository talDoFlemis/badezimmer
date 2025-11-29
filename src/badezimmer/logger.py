import logging
import sys
from pythonjsonlogger.json import JsonFormatter


def setup_logger(
    logger: logging.Logger,
    level: int = logging.DEBUG,
    include_extra_fields: bool = False,
):
    """
    Configure a logger with comprehensive logging features.

    Args:
        logger: The logger instance to configure
        level: The logging level (default: DEBUG)
        include_extra_fields: Whether to include extended fields like process info
    """
    if logger.handlers:
        return

    logHandler = logging.StreamHandler(sys.stdout)

    # Define the format with all the good logging fields
    log_format = [
        "%(asctime)s",  # Timestamp
        "%(levelname)s",  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        "%(name)s",  # Logger name
        "%(funcName)s",  # Function name
        "%(filename)s",  # Source file name
        "%(lineno)d",  # Line number
        "%(message)s",  # Log message
    ]

    if include_extra_fields:
        log_format.extend(
            [
                "%(process)d",  # Process ID
                "%(processName)s",  # Process name
                "%(thread)d",  # Thread ID
                "%(threadName)s",  # Thread name
            ]
        )

    # Create JSON formatter with timestamp format
    formatter = JsonFormatter(
        " ".join(log_format),
        timestamp=True,
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "funcName": "function",
            "filename": "file",
            "lineno": "line",
            "processName": "process_name",
            "threadName": "thread_name",
        },
    )

    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    logger.setLevel(level)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
