from __future__ import annotations

import re
from typing import Optional, Sequence, Tuple

__all__ = [
    "COIN_KEYWORDS",
    "MAJOR_ASSET_SET",
    "MARKET_WIDE_TERMS",
    "extract_asset_mentions",
    "infer_asset_label",
]

# Canonical asset keywords and tickers (extendable)
COIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "BTC": (
        "bitcoin",
        "btc",
        "satoshi",
        "satoshis",
        "sats",
        "bitcoin etf",
        "spot bitcoin",
        "btc price",
        "btc spot",
    ),
    "ETH": (
        "ethereum",
        "eth",
        "ether",
        "eth2",
        "eth 2.0",
        "eth staking",
        "eth price",
        "ethereum mainnet",
        "ethereum blockchain",
        "\u039e",
    ),
    "XRP": (
        "xrp",
        "ripple",
        "xrpl",
        "xrp ledger",
        "ripple labs",
        "ripplenet",
        "ripple network",
        "xrp token",
        "ripples",
        "banker's coin",
        "bankers coin",
        "banker\u2019s coin",
    ),
    "DOGE": ("dogecoin", "doge"),
    "SOL": ("solana", "sol"),
    "ADA": ("cardano", "ada"),
    "BNB": ("binance coin", "bnb"),
    "DOT": ("polkadot", "dot"),
    "AVAX": ("avalanche", "avax"),
    "MATIC": ("polygon", "matic"),
    "LTC": ("litecoin", "ltc"),
    "SHIB": ("shiba inu", "shib"),
    "ARB": ("arbitrum", "arb"),
    "OP": ("optimism", "op token", "optimism token"),
    "LINK": ("chainlink", "link"),
    "APT": ("aptos", "apt"),
    "ATOM": ("cosmos", "atom"),
    "ETC": ("ethereum classic", "etc"),
    "HBAR": ("hedera", "hbar"),
    "PEPE": ("pepe",),
    "WBTC": ("wrapped bitcoin", "wbtc"),
    "STETH": ("staked eth", "steth"),
}

MAJOR_ASSET_SET = frozenset({"BTC", "ETH", "XRP"})

MARKET_WIDE_TERMS: tuple[str, ...] = (
    "crypto market",
    "cryptocurrency market",
    "digital asset market",
    "broader crypto market",
    "entire crypto market",
    "whole crypto market",
    "overall crypto market",
    "all of crypto",
    "the crypto market",
    "crypto markets",
    "digital asset space",
    "crypto space",
    "crypto industry",
    "virtual asset market",
    "digital asset sector",
    "crypto sector",
    "cryptocurrency sector",
)


def _compile_coin_patterns() -> dict[str, tuple[re.Pattern, ...]]:
    compiled: dict[str, tuple[re.Pattern, ...]] = {}
    for asset, keywords in COIN_KEYWORDS.items():
        patterns: list[re.Pattern] = []
        for keyword in keywords:
            escaped = re.escape(keyword)
            pattern = re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)
            patterns.append(pattern)
        compiled[asset] = tuple(patterns)
    return compiled


COIN_PATTERN_MAP = _compile_coin_patterns()


def extract_asset_mentions(headline: str, content: str) -> tuple[tuple[str, ...], bool]:
    """
    Scan headline+content for known coin keywords.

    Returns:
        ordered_assets: tuple of unique asset tickers in order of first appearance
        has_market_term: True if text references the entire market
    """

    combined = f"{headline or ''} {content or ''}".lower()
    hits: list[tuple[int, str]] = []

    for asset, patterns in COIN_PATTERN_MAP.items():
        earliest: Optional[int] = None
        for pattern in patterns:
            match = pattern.search(combined)
            if match:
                location = match.start()
                if earliest is None or location < earliest:
                    earliest = location
        if earliest is not None:
            hits.append((earliest, asset))

    hits.sort(key=lambda item: item[0])
    ordered_assets: list[str] = []
    for _, asset in hits:
        if asset not in ordered_assets:
            ordered_assets.append(asset)

    has_market_term = any(term in combined for term in MARKET_WIDE_TERMS)
    return tuple(ordered_assets), has_market_term


def infer_asset_label(
    headline: str,
    content: str,
    existing_asset: str = "",
) -> tuple[str, tuple[str, ...]]:
    """
    Infer the best-fit asset label based on first mention precedence.

    Returns:
        preferred_asset: uppercase ticker or "ALL"/""
        mentions: tuple of ordered asset mentions (uppercase tickers)
    """

    mentions, has_market_term = extract_asset_mentions(headline, content)
    mention_set = set(mentions)
    existing_clean = (existing_asset or "").strip().upper()

    candidate = existing_clean

    non_major_mentions = tuple(asset for asset in mentions if asset not in MAJOR_ASSET_SET)

    if not mentions:
        candidate = "ALL"
    elif non_major_mentions:
        candidate = "ALL"
    elif MAJOR_ASSET_SET.issubset(mention_set):
        candidate = "ALL"
    elif has_market_term:
        candidate = "ALL"
    elif mentions:
        candidate = mentions[0]

    if candidate not in MAJOR_ASSET_SET and candidate != "ALL":
        candidate = "ALL"

    return candidate, mentions



