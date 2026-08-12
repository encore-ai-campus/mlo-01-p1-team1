import logging
from pathlib import Path


def createLogger():
    log_dir = Path("/home/ec2-user/logs/sql")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    connection_logger = logging.getLogger("sql_connection")
    connection_logger.setLevel(logging.ERROR)
    connection_logger.propagate = False

    query_logger = logging.getLogger("sql_query")
    query_logger.setLevel(logging.ERROR)
    query_logger.propagate = False

    if not connection_logger.handlers:
        connection_handler = logging.FileHandler(
            log_dir / "sql-connection-error.log",
            encoding="utf-8",
        )
        connection_handler.setFormatter(log_format)
        connection_logger.addHandler(connection_handler)

    if not query_logger.handlers:
        query_handler = logging.FileHandler(
            log_dir / "sql-query-error.log",
            encoding="utf-8",
        )
        query_handler.setFormatter(log_format)
        query_logger.addHandler(query_handler)

    return connection_logger, query_logger