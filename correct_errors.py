"""
Parse mislabeled sentiment records from a manually prepared text file and export
them to JSON for downstream auditing.
"""

import json
import re
from pathlib import Path


def extract_entries(source_text: str):
    """
    Extract rows from the Markdown-like table in the mislabeled text file.
    Expected column order: id | headline | given | validated | reason
    """
    pattern = re.compile(
        r"\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|"
    )

    for match in pattern.findall(source_text):
        id_num, headline, given, validated, reason = match
        yield {
            "id": int(id_num),
            "headline": headline.strip(),
            "given_sentiment": given.strip(),
            "validated_sentiment": validated.strip(),
            "reason": reason.strip(),
        }


def main():
    input_path = Path("data scraping") / "delica my loves.txt"
    output_path = Path("data scraping") / "corrected_sentiments.json"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    data = list(extract_entries(text))

    output_path.write_text(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"✅ {len(data)} entries saved to {output_path}")


if __name__ == "__main__":
    main()

