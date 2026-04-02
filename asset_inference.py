#!/usr/bin/env python3
"""
Analyze Disagreements Between Manual and AI Labels
Helps identify where to improve rubrics_labeler or fix manual labels
"""

import pandas as pd
import sys
from pathlib import Path
from collections import Counter

# Add project root to path
# Script is in: data scraping/tools/analyze_disagreements.py
# Project root is: THESIS NANAMAN (2 levels up)
script_dir = Path(__file__).resolve().parent  # data scraping/tools
project_root = script_dir.parent.parent  # THESIS NANAMAN
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

def normalize_label(label):
    """Normalize label to 3-class system"""
    if pd.isna(label) or not label:
        return None
    label = str(label).lower().strip()
    
    # Map to 3-class
    if 'positive' in label:
        return 'positive'
    elif 'negative' in label:
        return 'negative'
    elif 'neutral' in label:
        return 'neutral'
    return None

def analyze_disagreements(dataset_path):
    """Analyze disagreements between manual and AI labels"""
    print(f"Loading dataset: {dataset_path}")
    df = pd.read_excel(dataset_path)
    
    # Find label columns
    # rubrics_labeler saves:
    # - Previous labels in: 'rubric_previous_label'
    # - New AI labels in: 'sentiment_5class'
    # Manual labels might also be in: 'sentiment_label', 'sentiment'
    
    manual_col = None
    ai_col = None
    
    # Check for rubric_previous_label (manual labels before rubrics_labeler)
    if 'rubric_previous_label' in df.columns:
        manual_col = 'rubric_previous_label'
        print("Found manual labels in: rubric_previous_label")
    else:
        # Fallback to other columns
        for col in ['sentiment_label', 'sentiment', 'sentimen_5class']:
            if col in df.columns:
                manual_col = col
                print(f"Found manual labels in: {col}")
                break
    
    # AI labels from rubrics_labeler are in sentiment_5class
    if 'sentiment_5class' in df.columns:
        ai_col = 'sentiment_5class'
        print("Found AI labels in: sentiment_5class")
    else:
        # Fallback
        for col in ['rubrics_label', 'ai_label', 'predicted_label']:
            if col in df.columns:
                ai_col = col
                print(f"Found AI labels in: {col}")
                break
    
    if not manual_col:
        print("ERROR: Could not find manual label column!")
        print(f"Available columns: {list(df.columns)}")
        return
    
    if not ai_col:
        print("ERROR: Could not find AI label column!")
        print(f"Available columns: {list(df.columns)}")
        print("\nTip: Make sure you ran rubrics_labeler.py on this dataset")
        return
    
    print(f"Manual labels: {manual_col}")
    print(f"AI labels: {ai_col}\n")
    
    # Normalize labels
    df['manual_normalized'] = df[manual_col].apply(normalize_label)
    df['ai_normalized'] = df[ai_col].apply(normalize_label)
    
    # Find disagreements
    disagreements = df[
        (df['manual_normalized'].notna()) & 
        (df['ai_normalized'].notna()) &
        (df['manual_normalized'] != df['ai_normalized'])
    ].copy()
    
    total_comparisons = len(df[(df['manual_normalized'].notna()) & (df['ai_normalized'].notna())])
    agreement_count = total_comparisons - len(disagreements)
    agreement_rate = (agreement_count / total_comparisons * 100) if total_comparisons > 0 else 0
    
    print("=" * 80)
    print("DISAGREEMENT ANALYSIS")
    print("=" * 80)
    print(f"\nTotal comparisons: {total_comparisons}")
    print(f"Agreements: {agreement_count} ({agreement_rate:.1f}%)")
    print(f"Disagreements: {len(disagreements)} ({100 - agreement_rate:.1f}%)\n")
    
    if len(disagreements) == 0:
        print("✅ Perfect agreement! No disagreements found.")
        return
    
    # Analyze disagreement patterns
    print("=" * 80)
    print("DISAGREEMENT PATTERNS")
    print("=" * 80)
    
    disagreement_matrix = pd.crosstab(
        disagreements['manual_normalized'], 
        disagreements['ai_normalized'],
        margins=True
    )
    print("\nConfusion Matrix (Manual vs AI):")
    print(disagreement_matrix)
    
    # Most common disagreement types
    print("\n" + "=" * 80)
    print("MOST COMMON DISAGREEMENTS")
    print("=" * 80)
    
    disagreement_types = []
    for _, row in disagreements.iterrows():
        manual = row['manual_normalized']
        ai = row['ai_normalized']
        disagreement_types.append(f"{manual} -> {ai}")  # Use ASCII arrow for Windows compatibility
    
    type_counts = Counter(disagreement_types)
    print("\nDisagreement patterns:")
    for pattern, count in type_counts.most_common():
        print(f"  {pattern}: {count} ({count/len(disagreements)*100:.1f}%)")
    
    # Sample disagreements for review
    print("\n" + "=" * 80)
    print("SAMPLE DISAGREEMENTS (Review these to improve system)")
    print("=" * 80)
    
    # Group by disagreement type
    for pattern in type_counts.most_common(5):
        manual_label, ai_label = pattern[0].split(' -> ')  # Use ASCII arrow
        sample = disagreements[
            (disagreements['manual_normalized'] == manual_label) &
            (disagreements['ai_normalized'] == ai_label)
        ].head(3)
        
        print(f"\n{pattern[0]} ({pattern[1]} cases):")
        for idx, row in sample.iterrows():
            headline = str(row.get('headline', '') or row.get('title', ''))[:80]
            content = str(row.get('content', ''))[:150]
            print(f"\n  Row {idx + 2}:")
            print(f"    Manual: {manual_label.upper()}")
            print(f"    AI: {ai_label.upper()}")
            print(f"    Headline: {headline}...")
            print(f"    Content: {content}...")
    
    # Save disagreements to CSV
    output_file = Path(dataset_path).parent / "disagreements_analysis.csv"
    disagreements_export = disagreements[[
        manual_col, ai_col, 'manual_normalized', 'ai_normalized',
        'headline', 'content', 'asset'
    ]].copy()
    disagreements_export['disagreement_type'] = disagreements_export.apply(
        lambda row: f"{row['manual_normalized']} -> {row['ai_normalized']}", axis=1  # Use ASCII arrow
    )
    
    try:
        disagreements_export.to_csv(output_file, index=False)
        print(f"\n" + "=" * 80)
        print(f"[OK] Saved {len(disagreements)} disagreements to: {output_file}")
        print("=" * 80)
    except PermissionError:
        # File is likely open in Excel
        print(f"\n" + "=" * 80)
        print(f"[ERROR] Could not save to: {output_file}")
        print("=" * 80)
        print("\nTIP: Close the CSV file if it's open in Excel or another program!")
        print(f"\nShowing first 20 disagreements instead:")
        print("=" * 80)
        for i, (idx, row) in enumerate(disagreements.head(20).iterrows(), 1):
            print(f"\n{i}. Row {idx + 2}:")
            print(f"   Manual: {row['manual_normalized'].upper()}")
            print(f"   AI: {row['ai_normalized'].upper()}")
            headline = str(row.get('headline', '') or row.get('title', ''))[:80]
            print(f"   Headline: {headline}...")
        if len(disagreements) > 20:
            print(f"\n... and {len(disagreements) - 20} more disagreements")
        print("\n" + "=" * 80)
    print("\nRECOMMENDATIONS:")
    print("1. Review the disagreements CSV file")
    print("2. If AI is wrong → Improve rubrics_labeler.py patterns")
    print("3. If Manual is wrong → Fix your labels")
    print("4. If both are reasonable → These are ambiguous cases (keep manual)")
    print(f"\nExpected improvement after fixing: +2-5% accuracy")

def main():
    """Main function"""
    # Find latest dataset
    # Script is in: data scraping/tools/
    # Datasets are in: data scraping/Datasets/
    script_dir = Path(__file__).resolve().parent  # data scraping/tools
    data_scraping_dir = script_dir.parent  # data scraping
    datasets_dir = data_scraping_dir / "Datasets"
    dataset_patterns = [
        "*_labeled_RUBRICS_BALANCED_DYNAMIC.xlsx",
        "*_labeled_RUBRICS.xlsx",
        "*_labeled_FINAL_V7*.xlsx",
    ]
    
    candidates = []
    for pattern in dataset_patterns:
        candidates.extend(datasets_dir.glob(pattern))
    
    # Filter out temporary Excel files
    candidates = [c for c in candidates if not c.name.startswith('~$')]
    
    if not candidates:
        print("ERROR: No dataset files found!")
        print(f"Looking in: {datasets_dir}")
        return
    
    latest_dataset = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"Using dataset: {latest_dataset.name}\n")
    
    analyze_disagreements(latest_dataset)

if __name__ == "__main__":
    main()

