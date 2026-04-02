"""
Sentiment Quantification using RoBERTa (3-class) + VADER

This module provides sentiment quantification that uses:
1. Fine-tuned RoBERTa model (3-class: negative, neutral, positive)
2. VADER sentiment analyzer
3. Weighted ensemble scoring to produce numerical sentiment scores

Legacy 5-class labels such as "super positive" / "super negative" are
automatically down-mapped to the new 3-class scheme to remain backwards
compatible with historical datasets.
"""
import warnings
import os

# Suppress ALL protobuf version warnings from TensorFlow/transformers (must be FIRST)
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.*')
warnings.filterwarnings('ignore', message='.*Protobuf gencode version.*')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow info/warnings

import pandas as pd
from typing import Dict, Any, Optional
import logging
from pathlib import Path
import sys

# Ensure shared utilities are importable
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from sentiment_utils import (
    normalize_sentiment,
    sentiment_to_score,
    score_to_sentiment,
    CANONICAL_SENTIMENTS,
)

# Import sentiment analysis libraries directly
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    print("VADER not available. Install with: pip install vaderSentiment")

try:
    from transformers import pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Transformers not available. Install with: pip install transformers torch")


class SentimentQuantifier:
    """Segregated component for numerical sentiment quantification and DF helpers."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_finetuned = False
        self.roberta_tokenizer = None
        self.roberta_model = None
        self.label_encoder = None
        self.setup_models()
    
    def setup_models(self):
        """Initialize RoBERTa and VADER sentiment analysis models"""
        self.models = {}
        
        # VADER Sentiment Analyzer
        if VADER_AVAILABLE:
            self.models['vader'] = SentimentIntensityAnalyzer()
            self.logger.info("VADER sentiment analyzer initialized")
        
        # RoBERTa Sentiment Analysis
        if TRANSFORMERS_AVAILABLE:
            try:
                # Try to load fine-tuned model first
                import os
                # Prefer model next to this file
                base_dir = os.path.dirname(__file__)
                candidates = [
                    os.path.join(base_dir, "roberta_finetuned_model"),
                    # Also try top-level 'Sentiment Analysis/roberta_finetuned_model'
                    os.path.join(os.path.dirname(base_dir), "Sentiment Analysis", "roberta_finetuned_model"),
                    # Fallback to CWD-relative for backwards compatibility
                    os.path.join(os.getcwd(), "roberta_finetuned_model"),
                ]

                fine_tuned_path = None
                for c in candidates:
                    if os.path.exists(c):
                        fine_tuned_path = c
                        break
                
                if fine_tuned_path and os.path.exists(fine_tuned_path):
                    self.logger.info("Found fine-tuned RoBERTa model, loading...")
                    from transformers import AutoTokenizer, AutoModelForSequenceClassification
                    import pickle
                    
                    # Load tokenizer and model
                    self.roberta_tokenizer = AutoTokenizer.from_pretrained(fine_tuned_path)
                    self.roberta_model = AutoModelForSequenceClassification.from_pretrained(fine_tuned_path)
                    
                    # Load label encoder
                    if os.path.exists(os.path.join(fine_tuned_path, "label_encoder.pkl")):
                        with open(os.path.join(fine_tuned_path, "label_encoder.pkl"), 'rb') as f:
                            self.label_encoder = pickle.load(f)
                        self.logger.info(f"Label encoder loaded with {len(self.label_encoder.classes_)} classes: {self.label_encoder.classes_}")
                    else:
                        self.label_encoder = None
                        self.logger.warning("No label encoder found!")
                    
                    # Don't use pipeline - use model directly for custom sentiment classes
                    self.is_finetuned = True
                    self.logger.info("Fine-tuned RoBERTa sentiment analyzer loaded.")
                else:
                    raise FileNotFoundError("Fine-tuned RoBERTa model not found! Run fine_tune_roberta.py first.")
            except Exception as e:
                self.logger.warning(f"Failed to load fine-tuned RoBERTa: {e}. Falling back to VADER-only mode.")
                self.is_finetuned = False
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment using RoBERTa and VADER models"""
        if not text or not text.strip():
            return self._get_neutral_sentiment()
        
        results = {}
        
        # VADER Analysis
        if 'vader' in self.models:
            vader_scores = self.models['vader'].polarity_scores(text)
            results['vader'] = {
                'compound': vader_scores['compound'],
                'positive': vader_scores['pos'],
                'negative': vader_scores['neg'],
                'neutral': vader_scores['neu'],
                'sentiment': self._vader_to_sentiment(vader_scores['compound'])
            }
        
        # RoBERTa Analysis - USE DIRECT MODEL INFERENCE FOR 5-CLASS SENTIMENT
        if self.is_finetuned:
            try:
                # IMPORTANT: RoBERTa has a 512-token limit
                inputs = self.roberta_tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
                
                # Get model predictions
                with torch.no_grad():
                    outputs = self.roberta_model(**inputs)
                    logits = outputs.logits
                    probs = torch.softmax(logits, dim=-1)
                    predicted_idx = torch.argmax(logits, dim=-1).item()
                    confidence = probs[0][predicted_idx].item()
                
                # Get label from encoder
                if self.label_encoder:
                    predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]
                else:
                    predicted_label = f"class_{predicted_idx}"
                
                results['roberta'] = {
                    'label': predicted_label,
                    'score': confidence,
                    'sentiment': normalize_sentiment(predicted_label)
                }
            except Exception as e:
                self.logger.warning(f"RoBERTa analysis failed: {e}")
        
        # Ensemble sentiment
        results['ensemble'] = self._ensemble_sentiment(results)
        
        return results
    
    def _vader_to_sentiment(self, compound: float) -> str:
        """Convert VADER compound score to sentiment"""
        if compound >= 0.05:
            return 'positive'
        elif compound <= -0.05:
            return 'negative'
        else:
            return 'neutral'
    
    def _ensemble_sentiment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create ensemble sentiment from RoBERTa and VADER models"""
        sentiments = []
        weights = []
        
        # VADER
        if 'vader' in results:
            sentiments.append(normalize_sentiment(results['vader']['sentiment']))
            weights.append(0.4)  # Slightly higher weight for VADER
        
        # RoBERTa
        if 'roberta' in results:
            sentiments.append(normalize_sentiment(results['roberta']['sentiment']))
            weights.append(0.6)  # Higher weight for RoBERTa
        
        if not sentiments:
            return self._get_neutral_sentiment()
        
        # Weighted voting
        sentiment_scores = {label: 0 for label in CANONICAL_SENTIMENTS}
        for sentiment, weight in zip(sentiments, weights):
            sentiment_scores[sentiment] += weight
        
        # Determine final sentiment
        final_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        confidence = sentiment_scores[final_sentiment] / sum(weights)
        
        return {
            'sentiment': final_sentiment,
            'confidence': confidence,
            'scores': sentiment_scores
        }
    
    def _get_neutral_sentiment(self) -> Dict[str, Any]:
        """Return neutral sentiment when analysis fails"""
        return {
            'sentiment': 'neutral',
            'confidence': 0.0,
            'scores': {'positive': 0, 'negative': 0, 'neutral': 1.0}
        }

    def quantify_sentiment(self, text: str) -> Dict[str, Any]:
        analysis = self.analyze_sentiment(text)

        components: Dict[str, float] = {}
        weights: Dict[str, float] = {}
        weighted_sum = 0.0
        total_weight = 0.0

        # VADER contribution
        if 'vader' in analysis:
            val = float(analysis['vader']['compound'])
            w = 0.4
            components['vader'] = val
            weights['vader'] = w
            weighted_sum += val * w
            total_weight += w

        # RoBERTa contribution
        if 'roberta' in analysis:
            rb = analysis['roberta']
            label = str(rb.get('label', '')).lower()
            score = float(rb.get('score', 0.0))
            
            # Map labels to numerical scores (legacy labels are normalized first)
            normalized = normalize_sentiment(label)
            base_value = sentiment_to_score(normalized)
            val = base_value * score
            
            w = 0.6
            components['roberta'] = val
            weights['roberta'] = w
            weighted_sum += val * w
            total_weight += w

        if total_weight == 0.0:
            return {
                'score': 0.0,
                'tier': 'neutral',
                'components': components,
                'weights': weights,
                'ensemble_label': 'neutral',
                'confidence': 0.0
            }

        base_score = max(-1.0, min(1.0, weighted_sum / total_weight))

        tier = score_to_sentiment(base_score)

        return {
            'score': float(base_score),
            'tier': tier,
            'components': components,
            'weights': weights,
            'ensemble_label': analysis['ensemble']['sentiment'] if 'ensemble' in analysis else 'neutral',
            'confidence': analysis['ensemble']['confidence'] if 'ensemble' in analysis else 0.0
        }

    def quantify_with_fluctuation(self, text: str, fluctuation_pct: float = None) -> Dict[str, Any]:
        base = self.quantify_sentiment(text)
        score = base['score']

        if fluctuation_pct is None:
            return {**base, 'adjusted_score': score, 'adjusted_tier': base['tier'], 'adjustment': 0.0, 'used_fluctuation_pct': None}

        try:
            pct = float(fluctuation_pct)
        except Exception:
            pct = 0.0

        adj_mag = min(0.3, abs(pct) / 20.0)

        if score == 0.0 or adj_mag == 0.0:
            adjusted = score
        else:
            same_direction = (score > 0 and pct > 0) or (score < 0 and pct < 0)
            factor = (1.0 + adj_mag) if same_direction else (1.0 - adj_mag)
            adjusted = max(-1.0, min(1.0, score * factor))

        adj_tier = score_to_sentiment(adjusted)

        return {**base, 'adjusted_score': float(adjusted), 'adjusted_tier': adj_tier, 'adjustment': adj_mag if adjusted != score else 0.0, 'used_fluctuation_pct': pct}

    def attach_scores_to_dataframe(self, df: pd.DataFrame, fluctuation_pct_column: str = None) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        def _compute(row):
            text = str(row.get('content', ''))
            if fluctuation_pct_column and fluctuation_pct_column in row and pd.notna(row[fluctuation_pct_column]):
                return self.quantify_with_fluctuation(text, float(row[fluctuation_pct_column]))
            return self.quantify_sentiment(text)

        quant = df.apply(_compute, axis=1)
        df = df.copy()
        df['sentiment_score'] = quant.apply(lambda x: x.get('score', 0.0))
        df['sentiment_tier'] = quant.apply(lambda x: x.get('tier', 'neutral'))
        if fluctuation_pct_column and fluctuation_pct_column in df.columns:
            df['sentiment_score_adjusted'] = quant.apply(lambda x: x.get('adjusted_score', x.get('score', 0.0)))
            df['sentiment_tier_adjusted'] = quant.apply(lambda x: x.get('adjusted_tier', x.get('tier', 'neutral')))
        return df


if __name__ == "__main__":
    # Demo with RoBERTa and VADER sentiment analysis
    print("Initializing SentimentQuantifier with RoBERTa and VADER...")
    quantifier = SentimentQuantifier()
    
    # Test texts for sentiment analysis
    test_texts = [
        "Bitcoin is experiencing a massive rally with institutional adoption increasing!",
        "Regulatory crackdown fears are causing market panic and sell-offs.",
        "The cryptocurrency market remains stable with moderate trading volume.",
        "This is amazing! Crypto is going to the moon!",
        "I'm worried about the recent market volatility and potential crashes."
    ]
    
    print("\n=== Sentiment Quantification Results ===")
    print("NOTE: Sentiment Analysis (BiLSTM) is for classification; this is Sentiment Quantification (RoBERTa+VADER) for numerical scoring.\n")
    for i, text in enumerate(test_texts, 1):
        print(f"\n{i}. Text: {text}")
        
        # Get detailed analysis
        analysis = quantifier.analyze_sentiment(text)
        print(f"   VADER: {analysis.get('vader', {}).get('sentiment', 'N/A')} (compound: {analysis.get('vader', {}).get('compound', 0):.3f})")
        print(f"   RoBERTa: {analysis.get('roberta', {}).get('sentiment', 'N/A')} (score: {analysis.get('roberta', {}).get('score', 0):.3f})")
        print(f"   Ensemble: {analysis.get('ensemble', {}).get('sentiment', 'N/A')} (confidence: {analysis.get('ensemble', {}).get('confidence', 0):.3f})")
        
        # Get quantified results
        quant_result = quantifier.quantify_sentiment(text)
        print(f"   Quantified Score: {quant_result['score']:.3f}")
        print(f"   Tier: {quant_result['tier']}")
        print(f"   Components: {quant_result['components']}")
    
    # Demo with fluctuation adjustment
    print("\n=== Fluctuation Adjustment Demo ===")
    test_text = "Bitcoin is showing strong bullish momentum!"
    print(f"Text: {test_text}")
    
    base_result = quantifier.quantify_sentiment(test_text)
    print(f"Base score: {base_result['score']:.3f} ({base_result['tier']})")
    
    # Test with positive price movement
    adj_result = quantifier.quantify_with_fluctuation(test_text, fluctuation_pct=5.0)
    print(f"With +5% price movement: {adj_result['adjusted_score']:.3f} ({adj_result['adjusted_tier']})")
    
    # Test with negative price movement
    adj_result2 = quantifier.quantify_with_fluctuation(test_text, fluctuation_pct=-3.0)
    print(f"With -3% price movement: {adj_result2['adjusted_score']:.3f} ({adj_result2['adjusted_tier']})")
    
    # Demo complete - actual training uses MongoDB directly, not snapshots
    print("\n=== Demo Complete ===")
    print("For production use:")
    print("  - Training loads data directly from MongoDB (dataset4JADC.cryptogauge)")
    print("  - Only manually labeled articles are used for training")
    print("  - Run: python asset_specific_lstm_trainer.py")


