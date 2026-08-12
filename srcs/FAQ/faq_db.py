#!/usr/bin/env python3



def insert_if_new(collection, faq):
    if collection.find_one(faq):
        return

    collection.insert_one(faq)
