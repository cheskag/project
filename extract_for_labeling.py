#!/usr/bin/env python3
"""
Simple script to export MongoDB articles to Excel for manual labeling
"""

import pymongo
import pandas as pd
import urllib.parse
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv


def export_articles_to_excel():
    """Export articles from MongoDB to Excel for labeling"""
    
    # Connect to MongoDB - Load from environment variables
    # Auto-load .env from project root and data scraping folder
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    for env_path in [
        os.path.join(project_root, ".env"),
        os.path.join(os.path.dirname(project_root), ".env"),
        os.path.join(project_root, "data scraping", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]:
        try:
            load_dotenv(env_path, override=True)
        except Exception:
            pass

    MONGO_URI = os.getenv('MONGO_URI')
    if not MONGO_URI:
        raise ValueError("MONGO_URI not found in environment variables. Please set MONGO_URI in your .env file.")
    
    def sanitize_uri(uri: str) -> str:
        try:
            parsed = urllib.parse.urlparse(uri)
            host = parsed.hostname or ""
            return f"{parsed.scheme}://{host}"
        except Exception:
            return "<hidden>"
    
    print(f"Connecting to MongoDB host: {sanitize_uri(MONGO_URI)}")
    
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db_name = os.getenv('MONGO_DB', 'dataset4JADC')
        coll_name = os.getenv('MONGO_COLLECTION')
        if not coll_name:
            # Fall back to the primary dataset collection
            coll_name = 'cryptogauge'
        db = client[db_name]
        collection = db[coll_name]
        print(f"Using database '{db_name}', collection '{coll_name}'")
        if coll_name != 'cryptogauge':
            print("WARNING: MONGO_COLLECTION is set to", coll_name, "(expected 'cryptogauge').")
        
        print("Connected to MongoDB successfully")
        
        # Get ALL articles (both labeled and unlabeled)
        # This allows you to review/edit existing labels AND add new ones
        articles = list(collection.find())
        
        if not articles:
            print("No articles found")
            return
        
        # Count labeled vs unlabeled
        labeled_count = sum(1 for a in articles if a.get('sentiment_5class'))
        unlabeled_count = len(articles) - labeled_count
        
        print(f"Found {len(articles)} total articles")
        print(f"  - Already labeled: {labeled_count}")
        print(f"  - Need labeling: {unlabeled_count}")
        
        # Create DataFrame with ALL fields from MongoDB
        df = pd.DataFrame(articles)

        def _normalize_text(value):
            if value is None:
                return ""
            text = unicodedata.normalize("NFKC", str(value))
            text = re.sub(r"\s+", " ", text.strip())
            return text.lower()

        content_series = df["content"] if "content" in df.columns else pd.Series([""] * len(df))
        headline_series = df["headline"] if "headline" in df.columns else pd.Series([""] * len(df))

        df["_normalized_content"] = content_series.apply(_normalize_text)
        df["_normalized_headline"] = headline_series.apply(_normalize_text)
        
        # Ensure sentiment_5class column exists
        if 'sentiment_5class' not in df.columns:
            df['sentiment_5class'] = ''
        else:
            df['sentiment_5class'] = df['sentiment_5class'].fillna('')
        
        # Convert _id to string for Excel compatibility
        df['_id'] = df['_id'].astype(str)
        
        # Get all existing columns
        all_columns = df.columns.tolist()
        
        # Define priority columns (group ALL sentiment fields together for easy reading)
        priority_columns = [
            '_id', 'headline', 'content',
            'sentiment_5class',  # YOUR MANUAL LABEL - the ONLY one you need to edit
            
        # GROUP 1: Model Confidence Summary
        'sentiment_confidence', # Primary model confidence (0-1)
            
            # GROUP 2: BiLSTM Model Results (crypto-specific model)
            'lstm_sentiment',      # BiLSTM's 5-class prediction
            'lstm_confidence',     # BiLSTM's confidence (0-1)
            'lstm_polarity',      # BiLSTM's polarity score (-1 to +1)
            
            # GROUP 3: RoBERTa Quantifier Results (general-purpose model)
            'quantifier_confidence',     # RoBERTa's confidence (0-1)
            'quantifier_polarity',      # RoBERTa's polarity (-1 to +1)
            'quantifier_method',         # Quantifier source
            
            # GROUP 4: How models agreed/disagreed
            'validation_status',   # How the final sentiment was decided
            
            # Metadata (at the end)
            'asset', 'source', 'date_published', 'url'
        ]
        
        # Hide unnecessary fields (duplicates, unused, internal)
        columns_to_hide = [
            'sentiment_label',     # Duplicate of sentiment_5class
            'sentiment_existing',  # Legacy/unused
            'labeled_by',          # Internal tracking
            'sentiment_score',     # Duplicate of confidence
            'unique_id',           # Internal ID
            'content_hash',        # Internal deduplication
            'language',            # Always 'en'
            'type',                # Always 'news'
            'timestamp',           # Duplicate of date_published
        ]
        
        # Create final column order: priority first, then remaining columns (excluding hidden ones)
        reordered_columns = []
        for col in priority_columns:
            if col in all_columns:
                reordered_columns.append(col)
        
        # Add remaining columns at the end (except hidden ones)
        for col in all_columns:
            if col not in priority_columns and col not in columns_to_hide:
                reordered_columns.append(col)
        
        df = df[reordered_columns]
        
        # Sort: Put LABELED items FIRST (at top), then unlabeled items
        # This lets you see your work at the top and continue from where you left off
        df['_sort_order'] = df['sentiment_5class'].apply(lambda x: 0 if x and x != '' else 1)
        df = df.sort_values('_sort_order').drop(['_sort_order', '_normalized_content', '_normalized_headline'], axis=1)
        
        # Save to Excel in the unified folder: data scraping\Datasets (create if missing)
        datasets_dir = os.path.join(project_root, "data scraping", "Datasets")
        os.makedirs(datasets_dir, exist_ok=True)

        filename = os.path.join(datasets_dir, f'crypto_articles_ALL_for_labeling_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
        df.to_excel(filename, index=False)
        
        print(f"\n{'='*70}")
        print(f"SUCCESS: Exported {len(df)} articles to Excel")
        print(f"{'='*70}")
        print(f"\nFile: {filename}")
        print(f"\nExported Data:")
        print(f"  - Total articles: {len(df)}")
        print(f"  - Already labeled: {labeled_count}")
        print(f"  - Need labeling: {unlabeled_count}")
        
        # Guide removed for brevity
        
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    export_articles_to_excel()
