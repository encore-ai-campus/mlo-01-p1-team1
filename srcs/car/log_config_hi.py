import logging
from pathlib import Path

def createLogger() :
    

    LOG_DIR = Path("/home/ec2-user/logs/sql")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    connection_logger = logging.getLogger("sql_connection")
    connection_logger.setLevel(logging.ERROR)
    connection_handler = logging.FileHandler(
        LOG_DIR / "sql-connection-error.log",
        encoding="utf-8"
    )
    connection_handler.setFormatter(log_format)
    connection_logger.addHandler(connection_handler)
    connection_logger.propagate = False

    query_logger = logging.getLogger("sql_query")
    query_logger.setLevel(logging.ERROR)
    query_handler = logging.FileHandler(
        LOG_DIR / "sql-query-error.log",
        encoding="utf-8"
    )
    query_handler.setFormatter(log_format)
    query_logger.addHandler(query_handler)
    query_logger.propagate = False

    return connection_logger, query_logger
