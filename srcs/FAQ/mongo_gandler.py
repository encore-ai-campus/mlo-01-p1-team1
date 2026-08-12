#!/usr/bin/env python3



from bson.errors import InvalidDocument
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError, WriteError

from mongo_logger import connection_log, query_log, healthy_log


def save_faqs(faq_data):
    for attempt in range(2):
        client = MongoClient("mongodb://10.0.7.119:27017/")

        try:
            collection = client["crawler"]["faqs"]

            with client.start_session() as session:
                with session.start_transaction():
                    for faq in faq_data:
                        collection.insert_one(faq, session=session)

            healthy_log.info("row_count=%s", len(faq_data))
            return

        except ConnectionFailure as error:
            connection_log.error("error=%s", error)

            if attempt == 0:
                continue

            raise

        except DuplicateKeyError as error:
            query_log.error(
                "operation=insert_one | error_type=duplicate_key | error=%s",
                error
            )
            raise

        except (WriteError, InvalidDocument, TypeError, ValueError, KeyError) as error:
            query_log.error(
                "operation=insert_one | error_type=data_type_error | error=%s",
                error
            )
            raise

        finally:
            client.close()
