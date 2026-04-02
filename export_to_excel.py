import argparse
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from asset_inference import infer_asset_label
except ImportError:
    from tools.asset_inference import infer_asset_label

try:
    from rubrics_labeler import crypt_sentiment_guide, LABEL_TO_USER
except ImportError:
    from tools.rubrics_labeler import crypt_sentiment_guide, LABEL_TO_USER


BASE_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = BASE_DIR / "Datasets"

SENTIMENT_CLASSES = [
    "positive",
    "neutral",
    "negative",
]

ASSETS = ["BTC", "ETH", "XRP", "ALL"]
CONTENT_TYPES = ["news", "twitter", "reddit"]

COUNTRIES = [
    "United States",
    "Singapore",
    "United Arab Emirates",
    "Germany",
    "Brazil",
    "Japan",
    "Canada",
    "Australia",
]

REGULATORS = ["SEC", "CFTC", "FCA", "MAS", "ASIC", "ESMA", "Bafin", "HKMA"]

PROTOCOLS = [
    "Uniswap",
    "Aave",
    "MakerDAO",
    "Synthetix",
    "Curve",
    "Lido",
    "dYdX",
    "Balancer",
]

ONCHAIN_METRICS = [
    "active addresses",
    "exchange outflows",
    "long-term holder supply",
    "staking deposits",
    "derivatives funding rates",
    "whale accumulation",
    "gas fees",
    "hashrate",
]

MACRO_EVENTS = [
    "Fed policy shift",
    "ETF approval rumors",
    "inflation print surprise",
    "risk-on equities rally",
    "oil price slide",
    "dollar weakness",
    "jobs report miss",
    "geopolitical tension ease",
]

USE_CASES = [
    "cross-border payments",
    "tokenized treasuries",
    "stablecoin settlement",
    "DeFi lending",
    "NFT marketplaces",
    "gaming guild rewards",
    "institutional custody",
    "real-world asset rails",
]

HASH_TAGS = {
    # 3-class system: merged super positive/positive and super negative/negative
    "positive": ["#Bitcoin", "#CryptoRally", "#WAGMI", "#BullRun", "#Adoption", "#Blockchain", "#CryptoNews", "#OnChain"],
    "neutral": ["#Crypto", "#MarketWatch", "#DigitalAssets", "#Sideways"],
    "negative": ["#Volatility", "#RiskOff", "#CryptoSelloff", "#BearSignal", "#Capitulation", "#CryptoCrash", "#RedDay", "#PanicSelling"],
}

REGIONS = {
    "North America": 1.0,
    "Europe": 0.85,
    "Asia-Pacific": 1.15,
    "Latin America": 0.6,
    "Middle East": 0.55,
    "Africa": 0.4,
}

REGION_MARKETS = {
    "North America": ["US", "Canada", "Mexico"],
    "Europe": ["Germany", "France", "UK", "Switzerland"],
    "Asia-Pacific": ["Japan", "South Korea", "Singapore", "Australia"],
    "Latin America": ["Brazil", "Argentina", "Colombia", "Chile"],
    "Middle East": ["UAE", "Saudi Arabia", "Qatar"],
    "Africa": ["Nigeria", "South Africa", "Kenya"],
}

SEASONAL_EVENTS = {
    "North America": [
        "Thanksgiving retail flows", "Black Friday crypto deals", "US tax season positioning",
        "Fourth-quarter hedge fund rebalancing", "New Year portfolio rotations",
    ],
    "Europe": [
        "European Central Bank policy week", "EU MiCA rollout milestones", "Summer holiday liquidity",
        "Year-end VAT adjustments", "Brexit negotiation headlines",
    ],
    "Asia-Pacific": [
        "Lunar New Year red envelope effect", "Golden Week liquidity shifts", "Korean retail night sessions",
        "Australian fiscal year close", "Singapore FinTech Festival announcements",
    ],
    "Latin America": [
        "Brazilian election chatter", "Argentina inflation hedging", "Colombia fintech summit",
        "Carnival tourism payments", "Local remittance season",
    ],
    "Middle East": [
        "Ramadan charitable giving", "Dubai crypto expo", "Saudi Vision 2030 funding cycles",
        "Oil price budget adjustments", "Eid remittance flows",
    ],
    "Africa": [
        "Mobile money adoption drives", "Nigerian diaspora remittances", "South African mining dividends",
        "African Union tech summits", "Regional FX shortage hedging",
    ],
}

NEWS_TEMPLATES = {
    # 3-class system: merged super positive/positive and super negative/negative
    "positive": [
        # Strong positive templates (formerly "super positive")
        "{asset} rockets {percent_gain} after {institution} confirms treasury allocation; {macro_event} turns into rocket fuel for bulls",
        "{country}'s {regulator} clears {asset} for {use_case}, and {partner} rolls out nationwide integration across {region}",
        "On-chain {onchain_metric} for {asset} smashes records as {protocol} inflows surge, price eyes {price_level}",
        "{asset} ecosystem celebrates landmark deal with {partner}, unlocking {use_case} and sending sentiment into orbit",
        "{macro_event} triggers wave of demand as {asset} leads crypto majors, traders cite {onchain_metric} momentum",
        # Moderate positive templates (formerly "positive")
        "{asset} launches new {product} targeting {use_case}, teaming with {partner} to expand services across {region}",
        "{institution} pilots {asset}-backed {use_case}, helping price reclaim {price_level} during {timeframe}",
        "{asset} {protocol} performance improves with {percent_gain} yield boost, drawing steady inflows",
        "{country} firms tap {asset} for {use_case} as {regulator} outlines supportive guidelines",
        "Stable {onchain_metric} and partnership with {partner} keep {asset} grinding higher despite mixed macro backdrop",
    ],
    "neutral": [
        "{asset} holds near {price_level} while {macro_event} keeps traders cautious; {onchain_metric} signals balanced flows",
        "Market digests {institution}'s commentary on {asset}, leaving price range-bound during {timeframe}",
        "{asset} community waits for catalysts as {protocol} metrics stay flat and {use_case} adoption plateaus",
        "{country}'s hearings on {asset} regulation yield no surprises, sentiment remains steady",
        "Analysts note {onchain_metric} normalization for {asset}, framing current move as healthy consolidation",
    ],
    "negative": [
        # Moderate negative templates (formerly "negative")
        "{country}'s {regulator} issues warning on {asset} venues, sparking {percent_drop} pullback amid {macro_event}",
        "{asset} slips below {price_level} as {institution} delays launch tied to {use_case}",
        "Weak {onchain_metric} and waning {protocol} activity pressure {asset} during {timeframe}",
        "{partner} pauses rollout with {asset} citing compliance review, forcing traders defensive",
        "{macro_event} reverses risk appetite, dragging {asset} lower despite earlier {percent_gain}",
        # Strong negative templates (formerly "super negative")
        "{asset} plunges {percent_drop} after {protocol} exploit drains liquidity; {regulator} opens investigation",
        "{institution} unwinds exposure and {partner} suspends {use_case}, hammering {asset} sentiment",
        "Mass liquidations hit {asset} as {macro_event} sparks panic, price slices through {price_level}",
        "{country} rushes emergency legislation targeting {asset} trading, {onchain_metric} shows capitulation",
        "{asset} suffers cascading unwind; {regulator} subpoenas exchanges while community scrambles for footing",
    ],
}

NEWS_FOLLOW_UPS = {
    # 3-class system: merged super positive/positive and super negative/negative
    "positive": [
        # Strong positive follow-ups (formerly "super positive")
        "Spot desks track {volume_stat} inflows while sentiment index prints {sentiment_score}; strategists eye {price_level} breakout",
        "Derivatives data shows {onchain_metric} trending higher as {institution} talks up long-term adoption",
        "{partner} hints at additional {use_case} pilots and {protocol} staking demand accelerates",
        # Moderate positive follow-ups (formerly "positive")
        "Analysts point to {onchain_metric} stability and daily turnover near {volume_stat} as proof of sticky interest",
        "{institution} desks cite {macro_event} relief rally and expect grind toward {price_level}",
        "Community call notes focus on {use_case} improvements and incentive programs with {protocol}",
    ],
    "neutral": [
        "Volatility sellers keep premiums muted around {volume_stat}; funding rates hover at {funding_rate}",
        "{institution} research keeps neutral stance as on-chain flows average {volume_stat} per day",
        "Options traders price {timeframe} range between {price_level} and {secondary_price}",
    ],
    "negative": [
        # Moderate negative follow-ups (formerly "negative")
        "Market makers report {volume_stat} outflows while {onchain_metric} drifts lower and sentiment slips to {sentiment_score}",
        "{institution} risk desk notes {macro_event} still unresolved and expects tests of {price_floor}",
        "{partner} warns {use_case} expansion may slow as compliance reviews intensify",
        # Strong negative follow-ups (formerly "super negative")
        "Liquidations exceed {liquidations} in 24 hours; derivatives spreads blow out as {macro_event} shocks linger",
        "{institution} warns clients of further downside while {regulator} pressures exchanges handling {asset}",
        "Data shows {onchain_metric} collapsing, with sentiment gauge plunging to {sentiment_score}",
    ],
}

SOCIAL_TEMPLATES = {
    # 3-class system: merged super positive/positive and super negative/negative
    "positive": [
        # Strong positive templates (formerly "super positive")
        "{asset} fam we did it! up {percent_gain} on the day, institutions piling in after {macro_event} 🚀",
        "Reg clarity from {country}'s {regulator} plus {partner} integration = {asset} to the moon",
        "{asset} staking yields ripping on {protocol}, this {use_case} wave is unstoppable",
        "Whales gobbling {asset}, {onchain_metric} screaming bullish — {price_level} next?",
        "{asset} community just turned {macro_event} into pure rocket fuel. WAGMI!",
        # Moderate positive templates (formerly "positive")
        "{asset} collab with {partner} on {use_case} feels like real adoption, loving the steady grind",
        "Solid {onchain_metric} trend — holding my {asset} bags while we wait for the next catalyst",
        "{institution} dipping toes into {asset} shows TradFi is waking up",
        "{asset} upgrades on {protocol} are smooth, staking rewards creeping toward {percent_gain}",
        "Macro is messy but {asset} resilience plus {region} adoption keeps me bullish",
    ],
    "neutral": [
        "Watching {asset} chop around {price_level}; no big moves until {macro_event} settles",
        "Anyone else noticing {onchain_metric} flattening for {asset}? feels like pause before next leg",
        "{asset} convo today is all about regulation hearings — nothing crazy yet",
        "{protocol} fees calm, {asset} traders just waiting for direction",
        "Day traders stuck in range city on {asset}; patience until real volume returns",
    ],
    "negative": [
        # Moderate negative templates (formerly "negative")
        "{asset} taking heat from {country}'s {regulator} again, price fading {percent_drop}",
        "Seeing {onchain_metric} roll over and {protocol} yields slip — staying cautious on {asset}",
        "{partner} pausing {use_case} rollout is a bummer, sentiment feels heavy",
        "{macro_event} flipped the tape risk-off; {asset} bulls need fresh catalyst",
        "Volume drying up on {asset}, same old distribution vibes",
        # Strong negative templates (formerly "super negative")
        "{asset} getting wrecked! down {percent_drop} after that {protocol} exploit — brutal day",
        "{regulator} just nuked {asset} plans, exchanges freezing — this is worst-case stuff",
        "Liquidations everywhere, {asset} smashed through {price_level} like butter",
        "Feels like capitulation in {asset} land; whales dumping, {onchain_metric} in free fall",
        "{macro_event} crushed crypto and {asset} caught the worst of it — pain everywhere",
    ],
}

SOCIAL_SUFFIXES = {
    # 3-class system: merged super positive/positive and super negative/negative
    "positive": [
        # Strong positive suffixes (formerly "super positive")
        "{hash_tags} Sentiment score {sentiment_score} with inflows around {volume_stat} 🔥",
        "Community energy off the charts, {onchain_metric} up and wallets stacking. {hash_tags}",
        "{asset} dominance flexing — funding still calm at {funding_rate}. {hash_tags}",
        # Moderate positive suffixes (formerly "positive")
        "{hash_tags} Keeping eyes on {macro_event} while bids soak up dips",
        "Volume steady near {volume_stat}; builders heads down shipping. {hash_tags}",
        "{asset_lower} gang loving the slow burn, sentiment reading {sentiment_score}",
    ],
    "neutral": [
        "Feels like summer chop, {hash_tags}",
        "Open interest flat and vibes muted at {sentiment_score}. {hash_tags}",
        "Nothing wrong with consolidation — {volume_stat} turnover says market catching breath. {hash_tags}",
    ],
    "negative": [
        # Moderate negative suffixes (formerly "negative")
        "{hash_tags} Liquidity pockets thin and dealers hedging hard",
        "Funding gone negative at {funding_rate}; probs more downside unless {macro_event} flips",
        "{asset_lower} crowd needs catalyst, outflows near {volume_stat}. {hash_tags}",
        # Strong negative suffixes (formerly "super negative")
        "{hash_tags} Liquidations blew past {liquidations}, brutal tape",
        "Traders screaming risk control, sentiment index dives to {sentiment_score}. {hash_tags}",
        "Capitulation watch: {onchain_metric} cratered and perp spreads gapping. {hash_tags}",
    ],
}

SENTIMENT_SCORE_RANGES = {
    # 3-class system only: positive, neutral, negative
    "positive": (60, 95),  # Combined range for all positive sentiment (was super positive + positive)
    "neutral": (45, 60),
    "negative": (8, 45),   # Combined range for all negative sentiment (was super negative + negative)
}

FUNDING_RATE_RANGES = {
    # 3-class system only: positive, neutral, negative
    "positive": (0.0002, 0.0016),  # Combined range (was super positive + positive)
    "neutral": (-0.0001, 0.0002),
    "negative": (-0.0015, -0.0002),  # Combined range (was super negative + negative)
}

PERCENT_GAIN_RANGES = {
    # 3-class system only: positive, neutral, negative
    "positive": (4, 38),  # Combined range (was super positive + positive)
    "neutral": (0.5, 4),
    "negative": (0.1, 2.5),  # Combined range (was super negative + negative)
}

PERCENT_DROP_RANGES = {
    # 3-class system only: positive, neutral, negative
    "positive": (0.5, 4),  # Combined range (was super positive + positive)
    "neutral": (1, 6),
    "negative": (6, 45),  # Combined range (was super negative + negative)
}

ASSET_PRICE_BANDS = {
    "BTC": (25000, 78000),
    "ETH": (1200, 6200),
    "XRP": (0.25, 2.2),
    "ALL": (0.5, 4200),
}

NOISE_EMOJIS = ["🔥", "🚀", "📈", "📉", "🤔", "😅"]
NOISE_TRAILERS = [
    "Analysts are double-checking the flows.",
    "Traders in Telegram are buzzing already.",
    "Desk chatter says more headlines are coming.",
    "Observers warn volatility may persist.",
]
NOISE_FILLERS = [
    "Seriously.",
    "No joke.",
    "Just saying.",
    "FYI.",
]


def normalize_label(value: str | float | None) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().lower()


def apply_noise(text: str, sentiment: str, content_type: str, context: dict, noise_prob: float) -> str:
    if noise_prob <= 0 or random.random() > noise_prob:
        return text

    mutated = text
    asset = context.get("asset", "")

    if content_type != "news" and random.random() < 0.5:
        mutated = f"{mutated} {random.choice(NOISE_EMOJIS)}"

    if asset and random.random() < 0.35:
        replacement = random.choice([asset.lower(), asset.capitalize(), asset])
        mutated = mutated.replace(asset, replacement)

    if random.random() < 0.3:
        mutated = mutated.replace(" and ", " & ")

    if content_type == "news" and random.random() < 0.4:
        trailer = random.choice(NOISE_TRAILERS)
        if not mutated.endswith((".", "!", "?")):
            mutated += "."
        mutated = f"{mutated} {trailer}"
    elif content_type != "news" and random.random() < 0.3:
        filler = random.choice(NOISE_FILLERS)
        mutated = f"{mutated} {filler}"

    return " ".join(mutated.split())


def choose_template(sentiment: str, content_type: str) -> str:
    if content_type == "news":
        return random.choice(NEWS_TEMPLATES[sentiment])
    return random.choice(SOCIAL_TEMPLATES[sentiment])


def random_partner() -> str:
    partners = [
        "BlackRock",
        "Visa",
        "Mastercard",
        "Fidelity",
        "Circle",
        "Stripe",
        "PayPal",
        "Microsoft",
    ]
    return random.choice(partners)


def random_regulator() -> str:
    return random.choice(REGULATORS)


def random_institution() -> str:
    institutions = [
        "Goldman Sachs",
        "JPMorgan",
        "Citadel",
        "State Street",
        "BNP Paribas",
        "Deutsche Bank",
        "Morgan Stanley",
        "Blackstone",
    ]
    return random.choice(institutions)


def random_sector() -> str:
    sectors = [
        "DeFi",
        "NFT",
        "payments",
        "staking",
        "layer-2",
        "tokenization",
        "infrastructure",
    ]
    return random.choice(sectors)


def random_product() -> str:
    products = [
        "staking dashboard",
        "DeFi bridge",
        "compliance toolkit",
        "smart wallet",
        "governance module",
        "yield optimizer",
    ]
    return random.choice(products)


def random_volume_stat() -> str:
    unit = random.choice(["M", "M", "M", "B"])
    if unit == "B":
        value = random.uniform(0.3, 1.8)
    else:
        value = random.uniform(18, 420)
    return f"${value:.1f}{unit}"


def random_liquidations() -> str:
    value = random.uniform(120, 980)
    return f"${value:.0f}M"


def random_sentiment_score(sentiment: str) -> str:
    low, high = SENTIMENT_SCORE_RANGES[sentiment]
    return str(random.randint(low, high))


def random_funding_rate(sentiment: str) -> str:
    low, high = FUNDING_RATE_RANGES[sentiment]
    value = random.uniform(low, high)
    return f"{value:+.2%}"


def random_percent_gain(sentiment: str) -> str:
    low, high = PERCENT_GAIN_RANGES[sentiment]
    return f"{random.uniform(low, high):.1f}%"


def random_percent_drop(sentiment: str) -> str:
    low, high = PERCENT_DROP_RANGES[sentiment]
    return f"{random.uniform(low, high):.1f}%"


def sample_price_value(asset: str) -> float:
    low, high = ASSET_PRICE_BANDS.get(asset, ASSET_PRICE_BANDS["ALL"])
    return random.uniform(low, high)


def format_price_value(value: float) -> str:
    if value >= 10:
        return f"${int(round(value)):,}"
    elif value >= 1:
        return f"${value:,.2f}"
    else:
        return f"${value:,.4f}"


def random_secondary_price(base_value: float) -> str:
    return format_price_value(base_value * random.uniform(0.9, 1.12))


def random_price_floor(base_value: float) -> str:
    return format_price_value(base_value * random.uniform(0.6, 0.9))


def random_hash_tags(sentiment: str) -> str:
    tags = random.sample(HASH_TAGS[sentiment], k=2)
    return " ".join(tags)


def weighted_region_choice() -> str:
    regions, weights = zip(*REGIONS.items())
    return random.choices(regions, weights=weights, k=1)[0]


def random_market_for_region(region: str) -> str:
    return random.choice(REGION_MARKETS.get(region, REGION_MARKETS["North America"]))


def random_seasonal_event(region: str) -> str:
    return random.choice(SEASONAL_EVENTS.get(region, SEASONAL_EVENTS["North America"]))


def random_onchain_metric() -> str:
    return random.choice(ONCHAIN_METRICS)


def random_macro_event() -> str:
    return random.choice(MACRO_EVENTS)


def random_protocol() -> str:
    return random.choice(PROTOCOLS)


def random_use_case() -> str:
    return random.choice(USE_CASES)


def random_country() -> str:
    return random.choice(COUNTRIES)


def random_timeframe() -> str:
    return random.choice([
        "this week",
        "over the past 48 hours",
        "during the London session",
        "ahead of the New York open",
        "into the weekend",
    ])


def build_context(sentiment: str, asset: str, seed_quote: str | None) -> dict:
    region = weighted_region_choice()
    base_price_value = sample_price_value(asset)
    context = {
        "asset": asset,
        "asset_lower": asset.lower(),
        "partner": random_partner(),
        "institution": random_institution(),
        "sector": random_sector(),
        "region": region,
        "market": random_market_for_region(region),
        "seasonal_event": random_seasonal_event(region),
        "product": random_product(),
        "regulator": random_regulator(),
        "country": random_country(),
        "percent_gain": random_percent_gain(sentiment),
        "percent_drop": random_percent_drop(sentiment),
        "price_level": format_price_value(base_price_value),
        "secondary_price": random_secondary_price(base_price_value),
        "price_floor": random_price_floor(base_price_value),
        "onchain_metric": random_onchain_metric(),
        "macro_event": random_macro_event(),
        "use_case": random_use_case(),
        "protocol": random_protocol(),
        "timeframe": random_timeframe(),
        "volume_stat": random_volume_stat(),
        "liquidations": random_liquidations(),
        "sentiment_score": random_sentiment_score(sentiment),
        "funding_rate": random_funding_rate(sentiment),
        "hash_tags": random_hash_tags(sentiment),
        "real_quote": seed_quote.strip() if seed_quote else "",
    }
    return context


def render_template(template: str, context: dict) -> str:
    return template.format(**context)


def generate_synthetic_row(
    sentiment: str,
    existing_texts: set[str],
    seed_pool: dict[str, list[str]],
    noise_prob: float,
) -> dict | None:
    attempts = 0
    while attempts < 24:
        attempts += 1
        content_type = random.choice(CONTENT_TYPES)
        asset = random.choice(ASSETS)
        seed_quote = None
        if seed_pool.get(sentiment):
            seed_quote = random.choice(seed_pool[sentiment])
        context = build_context(sentiment, asset, seed_quote)
        template = choose_template(sentiment, "news" if content_type == "news" else "social")
        primary = render_template(template, context).strip()

        if content_type == "news":
            follow_template = random.choice(NEWS_FOLLOW_UPS[sentiment])
            follow_up = render_template(follow_template, context).strip()
            if context["real_quote"]:
                real_fragment = context["real_quote"]
                if not real_fragment.endswith((".", "!", "?")):
                    real_fragment += "."
                follow_up = f"{follow_up} Real-market note: {real_fragment}"
            if not primary.endswith((".", "!", "?")):
                primary += "."
            if not follow_up.endswith((".", "!", "?")):
                follow_up += "."
            text = f"{primary} {follow_up}"
        else:
            suffix_template = random.choice(SOCIAL_SUFFIXES[sentiment])
            suffix = render_template(suffix_template, context).strip()
            if context["real_quote"]:
                snippet = context["real_quote"]
                if len(snippet) > 180:
                    snippet = snippet[:177].rstrip() + "..."
                suffix = f"{suffix} | {snippet}"
            text = f"{primary} {suffix}".strip()

        text = apply_noise(text, sentiment, content_type, context, noise_prob)
        content_key = text.lower()
        if content_key in existing_texts:
            continue

        if content_type == "news":
            headline_candidate = text.split(".", 1)[0].strip()
            headline = headline_candidate[:1].upper() + headline_candidate[1:]
        else:
            headline = text

        inferred_asset, _mentions = infer_asset_label(headline, text, asset)
        asset_upper = (inferred_asset or asset or "ALL").upper()

        rubric_internal = crypt_sentiment_guide(text, headline, asset_upper)
        rubric_user = LABEL_TO_USER.get(rubric_internal, rubric_internal)
        if normalize_label(rubric_user) != normalize_label(sentiment):
            continue

        existing_texts.add(content_key)

        now = datetime.now(UTC).replace(tzinfo=None)
        jitter = timedelta(minutes=random.randint(0, 60 * 24))
        record_id = uuid.uuid4().hex

        row = {
            "_id": record_id,
            "headline": headline,
            "content": text,
            "sentiment_5class": sentiment,
            "sentiment_confidence": round(random.uniform(0.85, 0.99), 3),
            "lstm_sentiment": np.nan,
            "lstm_confidence": np.nan,
            "lstm_polarity": np.nan,
            "quantifier_confidence": np.nan,
            "quantifier_polarity": np.nan,
            "quantifier_method": "synthetic",
            "validation_status": "synthetic_generated",
            "asset": asset_upper,
            "source": f"synthetic_{content_type}",
            "date_published": now - jitter,
            "url": f"synthetic://{record_id}",
            "scraped_at": now,
            "migrated_at": now,
            "labeled_at": now,
        }

        return row

    return None


def resolve_input_path(explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit)
        if not candidate.exists():
            raise FileNotFoundError(f"Specified input file '{candidate}' does not exist.")
        if candidate.name.startswith('~$'):
            raise ValueError("Provided file appears to be an Excel lock file (starts with '~$'). Please close the workbook and select the actual dataset.")
        return candidate

    candidates = sorted(
        (
            p for p in DATASETS_DIR.glob("*labeled_RUBRICS.xlsx")
            if p.is_file() and not p.name.startswith('~$') and "BALANCED" not in p.stem
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not candidates:
        raise FileNotFoundError(
            "No labeled dataset files were found. Provide a path with --file."
        )

    return candidates[0]


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic samples so every sentiment matches the largest class."
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        help="Input labeled dataset (.xlsx). Defaults to the most recent labeled export."
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        help="Optional output path. Defaults to '<input>_BALANCED_DYNAMIC.xlsx'."
    )
    parser.add_argument(
        "--noise-prob",
        dest="noise_prob",
        type=float,
        default=0.0,
        help="Probability (0-1) of injecting light phrasing noise into synthetic samples.",
    )

    args = parser.parse_args()

    input_path = resolve_input_path(args.file_path)
    print(f"Using labeled dataset: {input_path}")

    df = pd.read_excel(input_path)

    if "sentiment_5class" not in df.columns:
        raise ValueError("Input file must contain a 'sentiment_5class' column.")

    df = df.drop_duplicates(subset=['content'], keep='first').reset_index(drop=True)

    counts = df["sentiment_5class"].value_counts().to_dict()
    print("Current sentiment distribution:")
    for sentiment in SENTIMENT_CLASSES:
        count = counts.get(sentiment, 0)
        print(f"  {sentiment:>13}: {count}")

    target = max(counts.values())
    print(f"\nTarget count per class (max): {target}")

    existing_texts = set(df["content"].dropna().astype(str).str.lower())
    noise_prob = max(0.0, min(args.noise_prob, 1.0))

    def prepare_seed(text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:280]

    seed_pool: dict[str, list[str]] = {}
    for sentiment in SENTIMENT_CLASSES:
        seed_series = df[df["sentiment_5class"] == sentiment]["content"].dropna()
        seeds = [prepare_seed(s) for s in seed_series.astype(str) if s.strip()]
        if len(seeds) > 200:
            seeds = random.sample(seeds, 200)
        seed_pool[sentiment] = seeds

    synthetic_rows = []

    for sentiment in SENTIMENT_CLASSES:
        current = counts.get(sentiment, 0)
        needed = max(0, target - current)
        if needed == 0:
            continue

        print(f"Generating {needed} synthetic samples for '{sentiment}'")
        generated = 0
        attempts = 0
        max_attempts = max(needed * 16, 32)
        while generated < needed and attempts < max_attempts:
            attempts += 1
            row = generate_synthetic_row(sentiment, existing_texts, seed_pool, noise_prob)
            if row is None:
                continue
            synthetic_rows.append(row)
            generated += 1
        if generated < needed:
            print(
                f"  Warning: only generated {generated} of {needed} samples for '{sentiment}'. "
                "Consider increasing noise or reviewing templates."
            )

    if synthetic_rows:
        synth_df = pd.DataFrame(synthetic_rows)
        df = pd.concat([df, synth_df], ignore_index=True)

    df = df.drop_duplicates(subset=['content'], keep='first').reset_index(drop=True)
    existing_texts = set(df['content'].dropna().astype(str).str.lower())

    while True:
        counts = df['sentiment_5class'].value_counts().to_dict()
        deficits = {sent: target - counts.get(sent, 0) for sent in SENTIMENT_CLASSES}
        deficits = {sent: need for sent, need in deficits.items() if need > 0}
        if not deficits:
            break
        for sentiment, needed in deficits.items():
            generated = 0
            attempts = 0
            while generated < needed and attempts < needed * 6:
                attempts += 1
                row = generate_synthetic_row(sentiment, existing_texts, seed_pool, noise_prob)
                if row is None:
                    continue
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                generated += 1
        df = df.drop_duplicates(subset=['content'], keep='first').reset_index(drop=True)
        existing_texts = set(df['content'].dropna().astype(str).str.lower())

    df = df.drop_duplicates(subset=['content'], keep='first').reset_index(drop=True)

    final_counts = df["sentiment_5class"].value_counts().to_dict()
    print("\nFinal sentiment distribution:")
    for sentiment in SENTIMENT_CLASSES:
        count = final_counts.get(sentiment, 0)
        print(f"  {sentiment:>13}: {count}")

    output_path = Path(args.output_path) if args.output_path else input_path.with_name(
        input_path.stem + "_BALANCED_DYNAMIC.xlsx"
    )

    df.to_excel(output_path, index=False)
    print(f"\nSaved balanced dataset to: {output_path}")


if __name__ == "__main__":
    main()

