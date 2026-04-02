"""
Comprehensive Verification Script
1. Check if rubric patterns are correctly implemented in labeling script
2. Verify Excel labeling consistency with rubrics
3. Verify synthetic data augmentation correctness
"""
import pandas as pd
import re
import os
from collections import Counter

print("="*80)
print("COMPREHENSIVE VERIFICATION")
print("="*80)

# ============================================================================
# 1. VERIFY RUBRIC IMPLEMENTATION IN LABELING SCRIPT
# ============================================================================
print("\n" + "="*80)
print("1. VERIFYING RUBRIC IMPLEMENTATION IN LABELING SCRIPT")
print("="*80)

# Read the labeling script
script_path = r"data scraping\tools\final_v7_complete.py"
with open(script_path, 'r', encoding='utf-8') as f:
    script_content = f.read()

# Key patterns from rubric that should be in the script
rubric_patterns = {
    'very_negative': [
        'crash', 'dump', 'rekt', 'rug pull', 'scam', 'hacked', 'collapse',
        'liquidations top', 'biggest mistake', 'SEC sues', 'crypto ban',
        'regulatory crackdown', 'rate hike', 'hawkish Fed', 'breaks support',
        'death cross', 'whale selling', 'exchange inflows', 'upgrade bug'
    ],
    'negative': [
        'bearish', 'weak', 'pullback', 'risk', 'sell pressure', 'disappointing',
        'warning signals', 'warns', 'warning', 'regulatory warning',
        'volatility concerns', 'rejects resistance', 'overbought pullback'
    ],
    'neutral': [
        'trading at', 'reports', 'announces', 'volume stable', 'consolidating',
        'question', 'how', 'what', 'when', 'where', 'why'
    ],
    'positive': [
        'bullish', 'gaining momentum', 'recovery', 'strong fundamentals',
        'regulatory clarity', 'partnership', 'partners', 'launch', 'expands',
        'inflation hedge', 'holding support', 'institutional interest'
    ],
    'very_positive': [
        'to the moon', 'ATH soon', 'massive pump', 'HODL tight', 'lambo',
        'biggest bull catalyst', 'most crypto-obsessed', 'ultimate',
        'fuels', 'fueled', 'rocket fuel', 'breaks resistance', 'new ATH',
        'ETF approval', 'whale accumulation', 'halving', 'successful upgrade'
    ]
}

# Check if patterns are in script
print("\nChecking rubric pattern implementation:")
found_patterns = {}
missing_patterns = {}

for label, patterns in rubric_patterns.items():
    found = []
    missing = []
    for pattern in patterns:
        if pattern.lower() in script_content.lower():
            found.append(pattern)
        else:
            missing.append(pattern)
    found_patterns[label] = found
    missing_patterns[label] = missing

for label, found in found_patterns.items():
    print(f"\n{label.upper()}:")
    print(f"  [OK] Found: {len(found)}/{len(rubric_patterns[label])} patterns")
    if len(found) < len(rubric_patterns[label]):
        print(f"  [WARN] Missing: {len(missing_patterns[label])} patterns")
        if len(missing_patterns[label]) <= 5:
            print(f"     Missing: {', '.join(missing_patterns[label])}")

# ============================================================================
# 2. VERIFY EXCEL LABELING CONSISTENCY
# ============================================================================
print("\n" + "="*80)
print("2. VERIFYING EXCEL LABELING CONSISTENCY")
print("="*80)

excel_path = r"data scraping\Datasets\crypto_articles_ALL_for_labeling_20251106_110726_BALANCED_FINAL.xlsx"

if os.path.exists(excel_path):
    print(f"\nLoading: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Check label column
    label_col = 'sentiment_5class'
    if label_col not in df.columns:
        label_col = 'sentimen_5class'
    
    if label_col in df.columns:
        # Get label distribution
        labels = df[label_col].fillna('').astype(str).str.strip()
        label_counts = labels.value_counts()
        
        print(f"\nLabel Distribution:")
        for label, count in label_counts.items():
            if label:
                print(f"  {label}: {count}")
        
        # Check for invalid labels
        valid_labels = {'super negative', 'negative', 'neutral', 'positive', 'super positive'}
        invalid_labels = set(labels.unique()) - valid_labels - {''}
        
        if invalid_labels:
            print(f"\n[WARN] INVALID LABELS FOUND:")
            for invalid in invalid_labels:
                count = (labels == invalid).sum()
                print(f"  '{invalid}': {count} occurrences")
        else:
            print(f"\n[OK] All labels are valid!")
        
        # Sample check: Verify labels match content sentiment
        print(f"\n\nSampling 20 random rows for manual verification:")
        sample_df = df.sample(min(20, len(df)), random_state=42)
        
        for idx, row in sample_df.iterrows():
            try:
                headline = str(row.get('headline', ''))[:60].encode('ascii', 'ignore').decode('ascii')
                content = str(row.get('content', ''))[:80].encode('ascii', 'ignore').decode('ascii')
                label = str(row.get(label_col, ''))
                print(f"\nRow {idx}:")
                print(f"  Label: {label}")
                print(f"  Headline: {headline}...")
                print(f"  Content: {content}...")
            except Exception as e:
                print(f"\nRow {idx}: [Error displaying content: {e}]")
    else:
        print(f"[WARN] Label column '{label_col}' not found!")
        print(f"Available columns: {list(df.columns)}")
else:
    print(f"[WARN] Excel file not found: {excel_path}")

# ============================================================================
# 3. VERIFY SYNTHETIC DATA AUGMENTATION
# ============================================================================
print("\n" + "="*80)
print("3. VERIFYING SYNTHETIC DATA AUGMENTATION")
print("="*80)

if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
    
    # Check for synthetic data markers
    if 'source' in df.columns:
        sources = df['source'].fillna('').astype(str)
        synthetic_mask = sources.str.contains('synthetic', case=False, na=False)
        synthetic_count = synthetic_mask.sum()
        original_count = len(df) - synthetic_count
        
        print(f"\nData Source Breakdown:")
        print(f"  Original: {original_count} ({original_count/len(df)*100:.1f}%)")
        print(f"  Synthetic: {synthetic_count} ({synthetic_count/len(df)*100:.1f}%)")
        
        # Check synthetic data distribution
        if synthetic_count > 0:
            synthetic_df = df[synthetic_mask]
            if label_col in synthetic_df.columns:
                synthetic_labels = synthetic_df[label_col].value_counts()
                print(f"\nSynthetic Data Label Distribution:")
                for label, count in synthetic_labels.items():
                    print(f"  {label}: {count}")
            
            # Check content types
            if 'content_type' in synthetic_df.columns:
                content_types = synthetic_df['content_type'].value_counts()
                print(f"\nSynthetic Content Types:")
                for ctype, count in content_types.items():
                    print(f"  {ctype}: {count}")
            
            # Sample synthetic data
            print(f"\n\nSampling 5 synthetic rows for verification:")
            synthetic_sample = synthetic_df.sample(min(5, len(synthetic_df)), random_state=42)
            for idx, row in synthetic_sample.iterrows():
                try:
                    headline = str(row.get('headline', ''))[:60].encode('ascii', 'ignore').decode('ascii')
                    label = str(row.get(label_col, ''))
                    content_type = str(row.get('content_type', ''))
                    print(f"\n  Label: {label} | Type: {content_type}")
                    print(f"  Headline: {headline}...")
                except Exception as e:
                    print(f"\n  [Error displaying content: {e}]")
        
        # Check for duplicates
        print(f"\n\nChecking for duplicates...")
        df['content_hash'] = df.apply(lambda row: 
            hash(f"{str(row.get('headline', ''))}{str(row.get('content', ''))}"), 
            axis=1)
        duplicates = df.duplicated(subset=['content_hash'], keep='first').sum()
        print(f"  Duplicates found: {duplicates}")
        if duplicates == 0:
            print(f"  [OK] No duplicates!")
        else:
            print(f"  [WARN] {duplicates} duplicate rows found")
    
    # Check balance
    if label_col in df.columns:
        labels = df[label_col].fillna('').astype(str).str.strip()
        label_counts = labels.value_counts()
        
        print(f"\n\nFinal Balance Check:")
        target_count = label_counts.max() if len(label_counts) > 0 else 0
        balanced = True
        for label, count in label_counts.items():
            if label:
                diff = abs(count - target_count)
                pct_diff = (diff / target_count * 100) if target_count > 0 else 0
                status = "[OK]" if pct_diff < 1 else "[WARN]"
                print(f"  {status} {label}: {count} (target: {target_count}, diff: {diff}, {pct_diff:.1f}%)")
                if pct_diff > 1:
                    balanced = False
        
        if balanced:
            print(f"\n[OK] Dataset is balanced!")
        else:
            print(f"\n[WARN] Dataset is not perfectly balanced")

# ============================================================================
# 4. VERIFY RUBRIC PATTERNS IN ACTUAL DATA
# ============================================================================
print("\n" + "="*80)
print("4. VERIFYING RUBRIC PATTERNS IN ACTUAL DATA")
print("="*80)

if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
    
    if label_col in df.columns and 'content' in df.columns:
        # Check if labels match expected patterns
        print("\nChecking label-content consistency...")
        
        # Sample rows for each label
        for label in ['super negative', 'negative', 'neutral', 'positive', 'super positive']:
            label_df = df[df[label_col].astype(str).str.strip() == label]
            if len(label_df) > 0:
                sample = label_df.sample(min(3, len(label_df)), random_state=42)
                print(f"\n{label.upper()} samples:")
                for idx, row in sample.iterrows():
                    try:
                        content = str(row.get('content', ''))[:100].encode('ascii', 'ignore').decode('ascii')
                        headline = str(row.get('headline', ''))[:60].encode('ascii', 'ignore').decode('ascii')
                        print(f"  - {headline}...")
                        print(f"    {content}...")
                    except Exception as e:
                        print(f"  - [Error displaying content: {e}]")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)

