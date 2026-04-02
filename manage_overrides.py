
#!/usr/bin/env python3
"""
Flexible importer for labeled/augmented Excel into MongoDB.

Supports two modes automatically based on columns present:
1) Update mode (when _id present): updates existing docs by _id
2) Insert/upsert mode (no _id): inserts new docs into target collection,
   upserting on url when available (to avoid duplicates)

Targets DB/collection from environment variables:
- MONGO_URI (required)
- MONGO_DB (default: dataset4JADC)
- MONGO_COLLECTION (default: Trainingsets)
"""

import os
import pandas as pd
import pymongo
from bson import ObjectId
from datetime import datetime
import urllib.parse
from dotenv import load_dotenv

def import_labels_from_excel(excel_filename=None):
    """Import sentiment labels from Excel back to MongoDB"""
    
    # If no filename provided, find the most recent Excel file
    if excel_filename is None:
        import glob
        import os

        # Discover files from a single canonical location: data scraping\Datasets
        current_dir_files = (
            glob.glob('crypto_articles_*.xlsx') +
            glob.glob('labeled_articles_*.xlsx') +
            glob.glob('crypto_articles_ALL_for_labeling_*.xlsx')
        )
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
        datasets_dir = os.path.join(project_root, 'data scraping', 'Datasets')

        def collect(dir_path):
            if not os.path.isdir(dir_path):
                return []
            return (
                glob.glob(os.path.join(dir_path, 'crypto_articles_*.xlsx')) +
                glob.glob(os.path.join(dir_path, 'labeled_articles_*.xlsx')) +
                glob.glob(os.path.join(dir_path, 'crypto_articles_ALL_for_labeling_*.xlsx'))
            )

        excel_files = current_dir_files + collect(datasets_dir)

        if not excel_files:
            print("No Excel files found. Please run export_to_excel.py first (outputs to data scraping/Datasets)")
            return

        # Sort by modification time (most recent first)
        excel_filename = max(excel_files, key=os.path.getmtime)
        print(f"Using file: {excel_filename}")
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_filename)
        
        # Check if asset column exists
        if 'asset' in df.columns:
            print("Asset information found in Excel file")
        else:
            print("Warning: Asset column not found in Excel file")
        
        print(f"Loaded {len(df)} articles from Excel")
        
        # Connect to MongoDB - Load from environment variables
        # Load multiple potential .env locations without overriding explicit envs
        for env_path in [
            os.path.join(project_root, ".env"),
            os.path.join(os.path.dirname(__file__), ".env"),
        ]:
            try:
                load_dotenv(env_path, override=False)
            except Exception:
                pass

        MONGO_URI = os.getenv('MONGO_URI')
        if not MONGO_URI:
            raise ValueError("MONGO_URI not found in environment variables. Please set MONGO_URI in your .env file.")
        # Default to production dataset (dataset4JADC.cryptogauge); can be overridden by env
        MONGO_DB = os.getenv('MONGO_DB', 'dataset4JADC')
        MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'cryptogauge')

        client = pymongo.MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        
        print("Connected to MongoDB")
        
        # Remove columns that shouldn't be imported
        ignore_columns = ['instructions', '_sort_order']
        for col in ignore_columns:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        updated_count = 0
        inserted_count = 0
        errors = []
        
        # Normalize column names for flexible imports
        cols = {c: c for c in df.columns}
        def get_first(*names):
            for n in names:
                if n in df.columns:
                    return n
            return None

        col_id = get_first('_id')
        col_content = get_first('content', 'text', 'article', 'body')
        col_headline = get_first('headline', 'title')
        col_url = get_first('url', 'link')
        col_asset = get_first('asset')
        col_sent = get_first('sentiment_5class', 'label', 'sentiment_label')
        col_scraped = get_first('scraped_at', 'date_published', 'published_at')
        col_source = get_first('source')

        # Update/Insert MongoDB with ALL changes from Excel
        for index, row in df.iterrows():
            try:
                if col_id and pd.notna(row[col_id]):
                    # UPDATE MODE by _id
                    article_id = ObjectId(str(row[col_id]).strip())
                    update_fields = {}
                    for column in df.columns:
                        if column == col_id:
                            continue
                        value = row[column]
                        if pd.isna(value):
                            update_fields[column] = None
                        elif isinstance(value, str) and value.strip() == '':
                            update_fields[column] = ''
                        else:
                            update_fields[column] = value
                    # Manual label normalization to 3-class system
                    if col_sent and update_fields.get(col_sent):
                        sentiment = str(update_fields[col_sent]).strip().lower()
                        # Map legacy 5-class labels to 3-class
                        label_map = {
                            'super_negative': 'negative', 'super negative': 'negative',
                            'very_negative': 'negative', 'very negative': 'negative',
                            'extremely_negative': 'negative', 'extremely negative': 'negative',
                            'super_positive': 'positive', 'super positive': 'positive',
                            'very_positive': 'positive', 'very positive': 'positive',
                            'extremely_positive': 'positive', 'extremely positive': 'positive',
                            'negative': 'negative', 'neutral': 'neutral', 'positive': 'positive'
                        }
                        sentiment = label_map.get(sentiment, sentiment)
                        valid_sentiments = ['negative', 'neutral', 'positive']
                        if sentiment not in valid_sentiments:
                            errors.append(f"Row {index+2}: Invalid sentiment '{sentiment}' for _id {row[col_id]}")
                            continue
                        update_fields['sentiment_5class'] = sentiment
                        update_fields['labeled_at'] = datetime.now()
                        update_fields['labeled_by'] = 'manual_excel_import'
                    # Try update by _id first
                    result = collection.update_one({"_id": article_id}, {"$set": update_fields})
                    if result.matched_count > 0:
                        updated_count += 1
                        if (index + 1) % 100 == 0:
                            print(f"  Updated {index + 1}/{len(df)} rows...")
                    else:
                        # Fallback: upsert by URL, preserve original _id for traceability
                        url_key = col_url and row.get(col_url)
                        if url_key and pd.notna(url_key) and str(url_key).strip():
                            doc = {**update_fields}
                            doc['original_id'] = str(row[col_id])
                            res = collection.update_one({'url': str(url_key).strip()}, {'$setOnInsert': doc}, upsert=True)
                            if res.upserted_id is not None:
                                inserted_count += 1
                            else:
                                updated_count += 1
                        else:
                            errors.append(f"Row {index+2}: _id {row[col_id]} not found and no URL to upsert; skipped")
                else:
                    # INSERT/UPSERT MODE
                    doc = {}
                    # Core text fields
                    content_val = (str(row[col_content]).strip() if col_content and pd.notna(row.get(col_content)) else '')
                    headline_val = (str(row[col_headline]).strip() if col_headline and pd.notna(row.get(col_headline)) else '')
                    if not content_val and not headline_val:
                        errors.append(f"Row {index+2}: Missing content/headline; skipped")
                        continue
                    doc['content'] = content_val or headline_val
                    if headline_val:
                        doc['headline'] = headline_val

                    # Labels
                    if not col_sent or pd.isna(row.get(col_sent)) or str(row.get(col_sent)).strip() == '':
                        errors.append(f"Row {index+2}: Missing sentiment_5class; skipped")
                        continue
                    sentiment = str(row[col_sent]).strip().lower()
                    # Map legacy 5-class labels to 3-class system
                    label_map = {
                        'super_negative': 'negative', 'super negative': 'negative',
                        'very_negative': 'negative', 'very negative': 'negative',
                        'extremely_negative': 'negative', 'extremely negative': 'negative',
                        'super_positive': 'positive', 'super positive': 'positive',
                        'very_positive': 'positive', 'very positive': 'positive',
                        'extremely_positive': 'positive', 'extremely positive': 'positive',
                        'super pos': 'positive', 'super neg': 'negative',
                        'negative': 'negative', 'neutral': 'neutral', 'positive': 'positive'
                    }
                    sentiment = label_map.get(sentiment, sentiment)
                    valid_sentiments = ['negative', 'neutral', 'positive']
                    if sentiment not in valid_sentiments:
                        errors.append(f"Row {index+2}: Invalid sentiment '{sentiment}'; skipped")
                        continue
                    doc['sentiment_5class'] = sentiment

                    # Asset
                    asset_val = (str(row[col_asset]).strip().upper() if col_asset and pd.notna(row.get(col_asset)) else 'ALL')
                    if asset_val not in ['BTC','ETH','XRP','ALL']:
                        asset_val = 'ALL'
                    doc['asset'] = asset_val

                    # Metadata
                    if col_url and pd.notna(row.get(col_url)):
                        doc['url'] = str(row[col_url]).strip()
                    if col_source and pd.notna(row.get(col_source)):
                        doc['source'] = str(row[col_source]).strip()
                    if col_scraped and pd.notna(row.get(col_scraped)):
                        try:
                            dt = pd.to_datetime(row[col_scraped])
                            doc['scraped_at'] = dt.to_pydatetime()
                        except Exception:
                            pass
                    doc['labeled_at'] = datetime.now()
                    doc['labeled_by'] = 'excel_import'

                    # Upsert on url if available, else insert
                    if 'url' in doc and doc['url']:
                        res = collection.update_one({ 'url': doc['url'] }, { '$setOnInsert': doc }, upsert=True)
                        # matched but not upserted → existed; treat as updated
                        if res.upserted_id is not None:
                            inserted_count += 1
                        else:
                            updated_count += 1
                    else:
                        collection.insert_one(doc)
                        inserted_count += 1
                    
            except Exception as e:
                errors.append(f"Row {index+2}: Error updating _id {row['_id']}: {str(e)}")
        
        print(f"\n{'='*70}")
        print(f"IMPORT SUMMARY")
        print(f"{'='*70}")
        print(f"Total rows in Excel: {len(df)}")
        print(f"Successfully updated: {updated_count}")
        print(f"Successfully inserted: {inserted_count}")
        print(f"Failed updates: {len(errors)}")
        
        if errors:
            print(f"\n[WARNING]  ERRORS:")
            for error in errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
        
        if (updated_count + inserted_count) > 0:
            print(f"\n[SUCCESS] SUCCESS: {updated_count} articles updated in MongoDB")
            print(f"   And {inserted_count} new articles inserted!")
            
            # Count labeled articles
            labeled_count = collection.count_documents({'sentiment_5class': {'$exists': True, '$nin': ['', None, 'N/A', 'n/a']}})
            print(f"\nTotal labeled articles in MongoDB: {labeled_count}")
        else:
            print(f"\n[ERROR] No articles were updated. Please check the errors above.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    import sys
    excel_path = sys.argv[1] if len(sys.argv) > 1 else None
    import_labels_from_excel(excel_path)

