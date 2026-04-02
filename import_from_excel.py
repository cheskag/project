import argparse
import pandas as pd
import json
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent.parent / "Datasets"


def resolve_filepath(explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit)
        if not candidate.exists():
            raise FileNotFoundError(f"Specified file '{candidate}' does not exist.")
        return candidate

    candidates = sorted(
        (p for p in DATASETS_DIR.glob("crypto_articles_ALL_for_labeling_*.xlsx") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not candidates:
        raise FileNotFoundError(
            "No dataset files matching 'crypto_articles_ALL_for_labeling_*.xlsx' were found in 'data scraping\\Datasets'."
        )

    return candidates[0]


parser = argparse.ArgumentParser(description="Extract unlabeled rows from the latest crypto articles export.")
parser.add_argument(
    "--file",
    dest="file_path",
    help="Optional explicit path to a dataset .xlsx file. If omitted, the most recently modified 'crypto_articles_ALL_for_labeling_*.xlsx' file in 'data scraping\\Datasets' is used."
)
args = parser.parse_args()

filepath = resolve_filepath(args.file_path)

print(f"Using dataset file: {filepath}")

df = pd.read_excel(filepath)

# Remove duplicate sentiment column if exists
if 'sentiment_5class' in df.columns and 'sentimen_5class' in df.columns:
    df = df.drop(columns=['sentiment_5class'])  # Keep sentimen_5class

# Check which rows need labeling (rows 1008+)
start_row = 1007  # Row 1008 in Excel (0-indexed = 1007)

# Extract rows 1008+ that are empty or need labeling
rows_to_label = []
for idx in range(start_row, len(df)):
    row = df.iloc[idx]
    current_label = row.get('sentimen_5class', '')
    
    # Check if already labeled
    if pd.isna(current_label) or str(current_label).strip() == '' or str(current_label).strip() == 'nan':
        content = str(row['content']) if pd.notna(row['content']) else ""
        headline = str(row.get('headline', '')) if pd.notna(row.get('headline', '')) else ""
        
        if content and content != 'nan':
            rows_to_label.append({
                'row_num': idx + 1,
                'content': content,
                'headline': headline if headline else None
            })

print(f"Found {len(rows_to_label)} rows that need labeling (starting from row 1008)")
print(f"\nFirst 20 rows to analyze:\n")
print("="*80)

for i, item in enumerate(rows_to_label[:20]):
    print(f"\nROW {item['row_num']}:")
    print(f"Content: {item['content'][:400]}")
    if item['headline']:
        print(f"Headline: {item['headline']}")
    print("-" * 80)

# Save to JSON for easier processing
with open('rows_to_label.json', 'w', encoding='utf-8') as f:
    json.dump(rows_to_label, f, ensure_ascii=False, indent=2)

print(f"\n\nSaved all {len(rows_to_label)} rows to 'rows_to_label.json' for analysis")

