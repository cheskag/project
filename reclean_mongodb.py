#!/usr/bin/env python3
"""
MongoDB Migration Script: 5-class to 3-class Sentiment Labels

This script migrates existing sentiment_5class labels from the 5-class system
(super negative, negative, neutral, positive, super positive) to the new 3-class
system (negative, neutral, positive).

IMPORTANT: This script does NOT delete any data. It only updates the sentiment_5class
field to map legacy labels to the new canonical labels.

Mapping:
- "super negative" → "negative"
- "negative" → "negative" (no change)
- "neutral" → "neutral" (no change)
- "positive" → "positive" (no change)
- "super positive" → "positive"
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime

# Load environment variables
script_dir = Path(__file__).resolve().parent.parent
project_root = script_dir.parent
for env_path in [
    script_dir / ".env",
    project_root / ".env",
    Path.cwd() / ".env",
]:
    try:
        load_dotenv(dotenv_path=str(env_path), override=False)
    except Exception:
        pass

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB', 'dataset4JADC')
MONGO_COLLECTION_NAME = os.getenv('MONGO_COLLECTION', 'cryptogauge')

if not MONGO_URI:
    raise ValueError("MONGO_URI not found in environment variables")

# Label mapping: 5-class → 3-class
LABEL_MAPPING = {
    'super negative': 'negative',
    'super_negative': 'negative',
    'very_negative': 'negative',
    'very negative': 'negative',
    'extremely_negative': 'negative',
    'extremely negative': 'negative',
    'negative': 'negative',  # No change
    'neutral': 'neutral',    # No change
    'positive': 'positive',  # No change
    'super positive': 'positive',
    'super_positive': 'positive',
    'very_positive': 'positive',
    'very positive': 'positive',
    'extremely_positive': 'positive',
    'extremely positive': 'positive',
}

def migrate_sentiment_labels():
    """Migrate sentiment_5class labels from 5-class to 3-class system"""
    
    print("="*70)
    print("MONGODB SENTIMENT LABEL MIGRATION: 5-class → 3-class")
    print("="*70)
    print(f"Database: {MONGO_DB_NAME}")
    print(f"Collection: {MONGO_COLLECTION_NAME}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    try:
        # Connect to MongoDB
        client = MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            tls=True,
            tlsAllowInvalidCertificates=True,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        client.admin.command('ping')
        print("[SUCCESS] Connected to MongoDB")
        
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION_NAME]
        
        # Find all documents with sentiment_5class field
        query = {'sentiment_5class': {'$exists': True, '$ne': None, '$ne': ''}}
        total_docs = collection.count_documents(query)
        print(f"[INFO] Found {total_docs} documents with sentiment_5class field")
        
        if total_docs == 0:
            print("[INFO] No documents to migrate. Exiting.")
            return
        
        # Count labels before migration
        print("\n[INFO] Current label distribution:")
        pipeline = [
            {'$match': query},
            {'$group': {'_id': '$sentiment_5class', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        before_counts = {item['_id']: item['count'] for item in collection.aggregate(pipeline)}
        for label, count in before_counts.items():
            print(f"  {label}: {count}")
        
        # Perform migration
        print("\n[INFO] Starting migration...")
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process in batches
        batch_size = 1000
        cursor = collection.find(query, batch_size=batch_size)
        
        for doc in cursor:
            try:
                old_label = str(doc.get('sentiment_5class', '')).strip().lower()
                
                if not old_label:
                    skipped_count += 1
                    continue
                
                # Check if label needs migration
                new_label = LABEL_MAPPING.get(old_label, old_label)
                
                # Only update if label changed
                if new_label != old_label:
                    result = collection.update_one(
                        {'_id': doc['_id']},
                        {
                            '$set': {
                                'sentiment_5class': new_label,
                                'migrated_at': datetime.utcnow(),
                                'migration_note': f'Migrated from 5-class "{old_label}" to 3-class "{new_label}"'
                            }
                        }
                    )
                    if result.modified_count > 0:
                        migrated_count += 1
                        if migrated_count % 100 == 0:
                            print(f"  Migrated {migrated_count} documents...")
                else:
                    skipped_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"  [ERROR] Failed to migrate document {doc.get('_id')}: {e}")
        
        # Count labels after migration
        print("\n[INFO] Label distribution after migration:")
        after_counts = {item['_id']: item['count'] for item in collection.aggregate(pipeline)}
        for label, count in sorted(after_counts.items()):
            print(f"  {label}: {count}")
        
        # Summary
        print("\n" + "="*70)
        print("MIGRATION SUMMARY")
        print("="*70)
        print(f"Total documents processed: {total_docs}")
        print(f"Documents migrated: {migrated_count}")
        print(f"Documents skipped (already 3-class): {skipped_count}")
        print(f"Errors: {error_count}")
        print(f"Completed: {datetime.now().isoformat()}")
        print("="*70)
        
        if migrated_count > 0:
            print("\n[SUCCESS] Migration completed successfully!")
            print(f"[INFO] {migrated_count} documents updated to 3-class sentiment labels")
        else:
            print("\n[INFO] No documents required migration (all already in 3-class format)")
        
        client.close()
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This script will update sentiment_5class labels in MongoDB")
    print("   Legacy 'super positive' → 'positive'")
    print("   Legacy 'super negative' → 'negative'")
    print("   No data will be deleted, only labels will be updated.\n")
    
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Migration cancelled.")
        sys.exit(0)
    
    migrate_sentiment_labels()



