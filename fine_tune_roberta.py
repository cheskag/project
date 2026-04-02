#!/usr/bin/env python3
"""
Fine-tune RoBERTa model on your labeled crypto sentiment data
This will make the model better at understanding crypto-specific sentiment
"""

import warnings
import os

# Suppress ALL protobuf version warnings from TensorFlow/transformers (must be FIRST)
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.*')
warnings.filterwarnings('ignore', message='.*Protobuf gencode version.*')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow info/warnings

import numpy as np
import pandas as pd
from transformers import RobertaTokenizer, RobertaForSequenceClassification, Trainer, TrainingArguments
from transformers import EarlyStoppingCallback
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
import torch
import torch.nn as nn
from torch.utils.data import Dataset
import pickle
import sys
from pathlib import Path
from typing import Optional, Tuple, List

# Try importing get_mongo_collection from data scraping folder
current_dir = os.path.dirname(__file__)
data_scraping_dir = os.path.join(os.path.dirname(current_dir), 'data scraping')
sys.path.insert(0, data_scraping_dir)

# Ensure sentiment utilities are importable
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from sentiment_utils import (
    CANONICAL_SENTIMENTS,
    normalize_sentiment,
    resolve_sentiment_field,
)

def get_mongo_collection_lazy():
    try:
        from Data_Scraper import get_mongo_collection  # type: ignore
        return get_mongo_collection
    except Exception as exc:
        logger.warning(f"Unable to import get_mongo_collection: {exc}")
        return None


from tqdm import tqdm
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "data scraping" / "Datasets"
DATASET_PATTERNS = [
    "crypto_articles_ALL_for_labeling_*_labeled_RUBRICS_BALANCED_DYNAMIC.xlsx",
    "crypto_articles_ALL_for_labeling_*_labeled_RUBRICS.xlsx",
    "crypto_articles_ALL_for_labeling_*_labeled_FINAL_V7_USER_FORMAT.xlsx",
    "crypto_articles_ALL_for_labeling_*_labeled_FINAL_V7.xlsx",
]
VALID_SENTIMENTS = list(CANONICAL_SENTIMENTS)
MIN_TRAIN_CONTENT_LEN = 10


class SentimentDataset(Dataset):
    """PyTorch Dataset for sentiment classification"""
    
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        # Tokenize and truncate if needed
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


def get_latest_dataset_path() -> Optional[Path]:
    candidates = []
    for pattern in DATASET_PATTERNS:
        candidates.extend(DATASETS_DIR.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_sentiment_column(df: pd.DataFrame) -> Optional[str]:
    """Determine which column contains manually labeled sentiments."""
    candidates: Tuple[str, ...] = (
        "sentiment_label",
        "sentiment",
        "sentiment_5class",
        "sentiment_tier",
    )
    for column in candidates:
        if column in df.columns:
            return column
    return None


def load_labeled_data_from_excel(max_samples=None):
    dataset_path = get_latest_dataset_path()
    if not dataset_path:
        print(f"No labeled Excel dataset found in {DATASETS_DIR}")
        return None, None, None

    try:
        df = pd.read_excel(dataset_path)
    except Exception as exc:
        print(f"Failed to read dataset {dataset_path.name}: {exc}")
        return None, None, None

    sentiment_column = resolve_sentiment_column(df)
    if sentiment_column is None or 'content' not in df.columns:
        print(f"Dataset {dataset_path.name} missing required sentiment or content columns")
        return None, None, None

    df = df.copy()
    df[sentiment_column] = df[sentiment_column].astype(str).str.strip()
    df['sentiment_label'] = df[sentiment_column].map(normalize_sentiment)
    df = df[df['sentiment_label'].isin(VALID_SENTIMENTS)]

    df['content'] = df['content'].astype(str)
    df = df[df['content'].str.strip().str.len() >= MIN_TRAIN_CONTENT_LEN]

    if df.empty:
        print(f"Dataset {dataset_path.name} has no usable labeled rows")
        return None, None, None

    if max_samples and len(df) > max_samples:
        df = df.sample(n=max_samples, random_state=42)

    texts = df['content'].tolist()
    labels = df['sentiment_label'].tolist()

    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)

    unique, counts = np.unique(labels, return_counts=True)
    print(f"Loaded {len(texts)} labeled samples from {dataset_path.name}")
    print("Label Distribution (Excel):")
    for label, count in zip(unique, counts):
        print(f"  {label}: {count}")

    return texts, encoded_labels, label_encoder


def load_labeled_data_from_db(collection, max_samples=None):
    """Load labeled articles from MongoDB"""
    
    print("Loading labeled data from MongoDB...")
    
    query = {
        '$and': [
            {'content': {'$exists': True, '$ne': None, '$ne': ''}},
            {'$or': [
                {'sentiment_label': {'$exists': True, '$ne': None, '$ne': ''}},
                {'sentiment_5class': {'$exists': True, '$ne': None, '$ne': ''}},
                {'sentiment': {'$exists': True, '$ne': None, '$ne': ''}},
            ]}
        ]
    }
    
    articles = list(collection.find(query))
    
    if not articles:
        print("ERROR: No labeled articles found in database!")
        return None, None, None
    
    print(f"Found {len(articles)} articles with sentiment labels")
    
    if max_samples:
        articles = articles[:max_samples]
        print(f"Using {len(articles)} articles for training")
    
    # Extract texts and labels
    texts = []
    labels = []
    skipped_invalid_label = 0
    skipped_too_short = 0
    
    for article in tqdm(articles, desc="Loading articles"):
        content = article.get('content', '')
        label_raw = resolve_sentiment_field(article)
        
        if not content or len(str(content).strip()) < MIN_TRAIN_CONTENT_LEN:
            skipped_too_short += 1
            continue
        
        if label_raw is None:
            skipped_invalid_label += 1
            continue
        
        label = normalize_sentiment(label_raw)
        if label not in VALID_SENTIMENTS:
            skipped_invalid_label += 1
            continue
        
        texts.append(content)
        labels.append(label)
    
    print(f"\nLoaded {len(texts)} valid training examples")
    print(f"Skipped (too short < {MIN_TRAIN_CONTENT_LEN} chars): {skipped_too_short}")
    print(f"Skipped (empty/None/invalid labels): {skipped_invalid_label}")
    
    # Encode labels
    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)
    
    # Show distribution
    unique, counts = np.unique(labels, return_counts=True)
    print("\nLabel Distribution:")
    for label, count in zip(unique, counts):
        print(f"  {label}: {count}")
    
    return texts, encoded_labels, label_encoder


def fine_tune_roberta_model():
    """Fine-tune RoBERTa on your labeled data"""
    
    print("="*70)
    print("FINE-TUNING ROBERTA MODEL FOR CRYPTO SENTIMENT")
    print("="*70)
    
    # Attempt to load labeled data from latest Excel export
    texts, labels, label_encoder = load_labeled_data_from_excel()

    if texts is None or len(texts) < 50:
        print("Excel dataset unavailable or too small, attempting to load from MongoDB...")
        loader = get_mongo_collection_lazy()
        if loader is None:
            print("ERROR: Could not import get_mongo_collection from Data_Scraper")
            return
        collection = loader()
        if collection is None:
            print("ERROR: Could not connect to MongoDB")
            return
        texts, labels, label_encoder = load_labeled_data_from_db(collection)
        if texts is None or len(texts) < 50:
            print("ERROR: Need at least 50 labeled examples to fine-tune!")
            print(f"Currently have: {len(texts) if texts else 0} examples")
            return
    
    # Split data
    print("\nSplitting data into train/test...")
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"Training samples: {len(train_texts)}")
    print(f"Test samples: {len(test_texts)}")
    
    # Load tokenizer and model
    print("\nLoading pre-trained RoBERTa model...")
    # Use base RoBERTa model, not the sentiment-specific one (which has 3 classes)
    model_name = "roberta-base"
    tokenizer = RobertaTokenizer.from_pretrained(model_name)
    
    # Create model with correct number of labels for our sentiment classes
    model = RobertaForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(label_encoder.classes_),
        problem_type="single_label_classification",
        ignore_mismatched_sizes=True  # Allow different classifier size
    )
    
    print(f"Model loaded! Number of classes: {len(label_encoder.classes_)}")
    
    # Create datasets
    print("\nPreparing datasets...")
    train_dataset = SentimentDataset(train_texts, train_labels, tokenizer, max_length=512)
    test_dataset = SentimentDataset(test_texts, test_labels, tokenizer, max_length=512)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir='./roberta_finetuned_model',
        num_train_epochs=5,                    # Train for 5 epochs
        per_device_train_batch_size=8,        # Small batch size for GPU/memory
        per_device_eval_batch_size=8,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir='./roberta_logs',
        logging_steps=50,
        eval_strategy="steps",                 # Changed: evaluation_strategy -> eval_strategy
        eval_steps=200,                        # Every 200 steps
        save_strategy="steps",
        save_steps=200,
        load_best_model_at_end=True,          # Load best model at end
        metric_for_best_model="eval_f1",      # Changed: f1 -> eval_f1
        greater_is_better=True,
        fp16=False,                           # Disable if you don't have GPU
        report_to="none",                     # Disable wandb/tensorboard
        seed=42
    )
    
    # Compute metrics function
    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        
        accuracy = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average='weighted')
        
        return {
            'accuracy': accuracy,
            'f1': f1
        }
    
    # Create trainer
    print("\nCreating trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )
    
    # Train
    print("\n" + "="*70)
    print("STARTING TRAINING...")
    print("="*70)
    
    trainer.train()
    
    # Evaluate on test set
    print("\n" + "="*70)
    print("EVALUATING ON TEST SET...")
    print("="*70)
    
    eval_results = trainer.evaluate()
    
    print("\nTest Results:")
    print(f"  Accuracy: {eval_results['eval_accuracy']:.4f}")
    print(f"  F1 Score: {eval_results['eval_f1']:.4f}")
    
    # Detailed evaluation
    print("\nComputing detailed metrics...")
    test_predictions = trainer.predict(test_dataset)
    pred_labels = np.argmax(test_predictions.predictions, axis=1)
    
    print("\nClassification Report:")
    print(classification_report(test_labels, pred_labels, 
                                target_names=label_encoder.classes_))
    
    # Save model and tokenizer
    print("\nSaving fine-tuned model...")
    
    save_dir = './roberta_finetuned_model'
    trainer.save_model()
    tokenizer.save_pretrained(save_dir)
    
    # Save label encoder
    with open(f'{save_dir}/label_encoder.pkl', 'wb') as f:
        pickle.dump(label_encoder, f)
    
    print(f"\n[SUCCESS] Fine-tuned model saved to: {save_dir}")
    print("\nModel files:")
    print(f"  - {save_dir}/model files")
    print(f"  - {save_dir}/tokenizer files")
    print(f"  - {save_dir}/label_encoder.pkl")
    
    # Print instructions for using the model
    print("\n" + "="*70)
    print("HOW TO USE YOUR FINE-TUNED MODEL:")
    print("="*70)
    print("1. The fine-tuned model is saved in: roberta_finetuned_model/")
    print("2. To use it in Data_Scraper.py, update the quantifier to load this model")
    print("3. Your Data_Scraper.py already uses a quantifier - you just need to point it to this model")
    print("")
    print("Update in Data_Scraper.py:")
    print("    # Change: 'cardiffnlp/twitter-roberta-base-sentiment-latest'")
    print("    # To: './roberta_finetuned_model'")
    
    print("\n[SUCCESS] Fine-tuning complete!")
    print("="*70)


if __name__ == "__main__":
    fine_tune_roberta_model()

