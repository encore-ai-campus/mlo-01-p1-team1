#!/usr/bin/env python3


import logging
import os


def make_logger(name, path, level):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    logger.addHandler(handler)

    return logger


connection_log = make_logger(
    "mongo_connection",
    "/home/ec2-user/logs/sql/sql-connection-error.log",
    logging.ERROR
)

query_log = make_logger(
    "mongo_query",
    "/home/ec2-user/logs/sql/sql-query-error.log",
    logging.ERROR
)

healthy_log = make_logger(
    "mongo_healthy",
    "/home/ec2-user/logs/health-check/healthy.log",
    logging.INFO
)
