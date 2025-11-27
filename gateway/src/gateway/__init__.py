def main() -> None:
    import uvicorn

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(message)s %(name)s",
                "rename_fields": {"levelname": "severity", "asctime": "timestamp"},
            },
        },
        "handlers": {
            "default": {
                "formatter": "json",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        },
    }

    uvicorn.run(
        app="gateway.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
        log_config=log_config,
    )
