#!/usr/bin/env python3
"""
Deduplicate MongoDB articles by normalized content/headline.
Normalizes existing documents, removes duplicates, and enforces unique indexes.
"""

import os
import re
import unicodedata
import hashlib
from datetime import datetime

import pymongo
from bson import ObjectId
from dotenv import load_dotenv


def load_env():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    for env_path in [
        os.path.join(project_root, ".env"),
        os.path.join(os.path.dirname(project_root), ".env"),
        os.path.join(project_root, "data scraping", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]:
        try:
            load_dotenv(env_path, override=False)
        except Exception:
            pass


def normalize_text(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text.strip())
    return text.lower()


def ensure_normalized_fields(collection):
    target_fields = [
        "normalized_content_hash",
        "normalized_headline_hash",
    ]
    missing_query = {
        "$or": [{field: {"$exists": False}} for field in target_fields]
    }
    cursor = collection.find(missing_query, {"content": 1, "headline": 1})
    updated = 0
    for doc in cursor:
        normalized_content = normalize_text(doc.get("content", ""))
        normalized_headline = normalize_text(doc.get("headline", ""))
        updates = {}
        if normalized_content:
            updates["normalized_content_hash"] = hashlib.md5(
                normalized_content.encode("utf-8")
            ).hexdigest()
        else:
            updates["normalized_content_hash"] = ""
        if normalized_headline:
            updates["normalized_headline_hash"] = hashlib.md5(
                normalized_headline.encode("utf-8")
            ).hexdigest()
        else:
            updates["normalized_headline_hash"] = ""
        collection.update_one({"_id": doc["_id"]}, {"$set": updates})
        updated += 1
    return updated


def delete_duplicates(collection):
    pipeline = [
        {"$match": {"normalized_content_hash": {"$exists": True, "$ne": ""}}},
        {
            "$group": {
                "_id": "$normalized_content_hash",
                "ids": {"$push": "$_id"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]

    duplicate_groups = list(collection.aggregate(pipeline, allowDiskUse=True))
    if not duplicate_groups:
        return 0

    removed = 0
    for group in duplicate_groups:
        ids = group["ids"]
        docs = list(collection.find({"_id": {"$in": ids}}))
        if not docs:
            continue

        docs.sort(key=lambda d: d.get("scraped_at") or d.get("date_published") or d["_id"])
        keep_id = docs[0]["_id"]
        delete_ids = [doc["_id"] for doc in docs[1:]]

        if delete_ids:
            result = collection.delete_many({"_id": {"$in": delete_ids}})
            removed += result.deleted_count
            print(
                f"Removed {result.deleted_count} duplicates for hash {group['_id']} "
                f"(kept {keep_id})"
            )

    return removed


def ensure_indexes(collection):
    collection.create_index([("url", 1)], name="unique_url", unique=True)
    collection.create_index(
        [("content_hash", 1)], name="unique_content_hash", unique=True
    )
    collection.create_index(
        [("normalized_content_hash", 1)],
        name="unique_normalized_content_hash",
        unique=True,
    )


def main():
    load_env()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not configured in environment.")

    db_name = os.getenv("MONGO_DB", "dataset4JADC")
    coll_name = os.getenv("MONGO_COLLECTION", "cryptogauge")

    client = pymongo.MongoClient(mongo_uri)
    collection = client[db_name][coll_name]

    print(f"Connected to MongoDB: {db_name}.{coll_name}")

    updated = ensure_normalized_fields(collection)
    print(f"Updated {updated} documents missing normalized hashes.")

    removed = delete_duplicates(collection)
    print(f"Removed {removed} duplicate documents.")

    ensure_indexes(collection)
    print("Unique indexes ensured.")

    client.close()
    print("Done.")


if __name__ == "__main__":
    main()

