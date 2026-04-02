#!/usr/bin/env python3
"""
Re-clean existing MongoDB articles
Applies the clean_article_text function to all existing articles in MongoDB
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime

# Load environment variables
load_dotenv()

# Add parent directory to path to import clean_article_text
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import clean_article_text from Data_Scraper
try:
    from Data_Scraper import clean_article_text
except ImportError:
    print("ERROR: Could not import clean_article_text from Data_Scraper.py")
    print("Make sure you're running this from the 'data scraping' directory")
    sys.exit(1)

def get_mongodb_connection():
    """Get MongoDB connection"""
    MONGO_URI = os.getenv('MONGO_URI')
    if not MONGO_URI:
        print("ERROR: MONGO_URI not found in .env file")
        sys.exit(1)
    
    try:
        client = MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=60000
        )
        client.admin.command('ping')
        print("✓ Connected to MongoDB")
        return client
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        sys.exit(1)

def reclean_articles(dry_run=True, limit=None):
    """
    Re-clean all articles in MongoDB
    
    Args:
        dry_run: If True, only show what would be cleaned (don't update)
        limit: Maximum number of articles to process (None = all)
    """
    client = get_mongodb_connection()
    
    db_name = os.getenv('MONGO_DB', 'dataset4JADC')
    coll_name = os.getenv('MONGO_COLLECTION', 'cryptogauge')
    
    db = client[db_name]
    collection = db[coll_name]
    
    print(f"\nUsing database: {db_name}")
    print(f"Using collection: {coll_name}")
    
    # Get total count
    total_count = collection.count_documents({})
    print(f"\nTotal articles in database: {total_count}")
    
    if limit:
        print(f"Processing first {limit} articles...")
        query = {}
    else:
        query = {}
    
    # Process articles
    articles = collection.find(query)
    if limit:
        articles = list(articles)[:limit]
    
    updated_count = 0
    cleaned_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}Processing articles...")
    print("=" * 80)
    
    for i, article in enumerate(articles, 1):
        try:
            article_id = article.get('_id')
            content = article.get('content', '')
            title = article.get('title', '')
            
            if not content:
                skipped_count += 1
                if i % 100 == 0:
                    print(f"Progress: {i}/{total_count if not limit else limit} (Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count})")
                continue
            
            # Clean the content
            original_length = len(content)
            cleaned_content = clean_article_text(content)
            new_length = len(cleaned_content)
            
            # Check if cleaning made a difference
            if original_length != new_length:
                cleaned_count += 1
                chars_removed = original_length - new_length
                
                if not dry_run:
                    # Update the article
                    result = collection.update_one(
                        {'_id': article_id},
                        {'$set': {
                            'content': cleaned_content,
                            'cleaned_at': datetime.utcnow()
                        }}
                    )
                    
                    if result.modified_count > 0:
                        updated_count += 1
                
                # Show progress for cleaned articles
                if cleaned_count <= 10 or cleaned_count % 50 == 0:
                    preview = title[:50] if title else "No title"
                    print(f"[{i}] {preview}...")
                    print(f"     Removed {chars_removed} chars ({original_length} → {new_length})")
            
            # Progress update every 100 articles
            if i % 100 == 0:
                print(f"Progress: {i}/{total_count if not limit else limit} (Cleaned: {cleaned_count}, Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count})")
        
        except Exception as e:
            error_count += 1
            print(f"ERROR processing article {i}: {e}")
            if error_count > 10:
                print("Too many errors. Stopping.")
                break
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total processed: {i}")
    print(f"Articles cleaned: {cleaned_count}")
    if not dry_run:
        print(f"Articles updated: {updated_count}")
    print(f"Skipped (no content): {skipped_count}")
    print(f"Errors: {error_count}")
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes were made")
        print("Run with --apply to actually update the database")
    else:
        print(f"\n✓ Successfully updated {updated_count} articles in MongoDB")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Re-clean existing MongoDB articles')
    parser.add_argument('--apply', action='store_true', help='Actually update the database (default is dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of articles to process (for testing)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("MongoDB Article Re-cleaning Tool")
    print("=" * 80)
    print("\nThis script will:")
    print("  - Remove source citations (Source: TradingView, etc.)")
    print("  - Remove references sections")
    print("  - Remove link patterns (Text | Link)")
    print("  - Remove image captions and metadata")
    print("  - Remove date ranges and boilerplate text")
    print("  - Clean up whitespace")
    
    if not args.apply:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("   Use --apply to actually update the database")
    
    print("\n" + "=" * 80)
    
    reclean_articles(dry_run=not args.apply, limit=args.limit)
    
    print("\nDone!")

if __name__ == "__main__":
    main()







