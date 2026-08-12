#!/usr/bin/env python3


import logging
import os

LOG_FILE = "/home/ec2-user/logs/request/crawling-error.log"


def get_logger():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger("crawler")

    if not logger.handlers:
        logger.setLevel(logging.ERROR)

        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )

        logger.addHandler(file_handler)

    return logger
