import logging

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        output_processors = [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
    else:
        output_processors = [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=[*shared_processors, *output_processors],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)
