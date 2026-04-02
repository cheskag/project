"""
Lightweight validation utilities.

If Pydantic is available, use it. Otherwise, provide permissive fallbacks so
runtime is not blocked.
"""

from typing import Any, Dict

try:
    from pydantic import BaseModel, Field
    from typing import Optional

    class ArticleSchema(BaseModel):
        # Make most fields optional with sensible defaults to avoid blocking saves
        url: Optional[str] = Field(default=None)
        title: Optional[str] = Field(default=None)
        content: Optional[str] = Field(default=None)
        source: Optional[str] = Field(default=None)
        asset: str = Field(default='ALL')

    def _detect_asset(sanitized: Dict[str, Any]) -> str:
        text = " ".join([
            str(sanitized.get('title') or ''),
            str(sanitized.get('content') or ''),
            str(sanitized.get('url') or ''),
            str(sanitized.get('source') or ''),
        ]).lower()
        # Heuristic detection
        if any(k in text for k in [' bitcoin', 'btc ', 'btc,', 'btc.', '/btc', 'bitcoin.com', 'bitcoin ']):
            return 'BTC'
        if any(k in text for k in [' ethereum', 'eth ', 'eth,', 'eth.', '/eth', 'ethereum.org', 'ethereum ']):
            return 'ETH'
        if any(k in text for k in [' xrp', ' ripple', '/xrp', 'xrp ', 'xrp,', 'xrp.']):
            return 'XRP'
        return 'ALL'

    def validate_article_data(data: Dict[str, Any]) -> tuple[bool, Dict[str, Any], str | None]:
        # Provide defaults before validation
        sanitized: Dict[str, Any] = dict(data or {})
        # Minimal required content: either content or title must exist
        content_val = sanitized.get('content') or ''
        title_val = sanitized.get('title') or ''
        if not content_val and title_val:
            sanitized['content'] = title_val
        # Asset detection (trainer relies on asset)
        detected = _detect_asset(sanitized)
        sanitized['asset'] = (sanitized.get('asset') or detected or 'ALL').upper()
        if sanitized['asset'] not in ['BTC', 'ETH', 'XRP', 'ALL']:
            sanitized['asset'] = detected or 'ALL'
        try:
            model = ArticleSchema(**sanitized)
            return True, model.model_dump(), None
        except Exception as e:
            return False, {}, str(e)

except Exception:
    # Fallbacks when Pydantic is not installed
    class ArticleSchema:  # type: ignore
        pass

    def validate_article_data(data: Dict[str, Any]) -> tuple[bool, Dict[str, Any], str | None]:
        # Minimal sanity checks and heuristics
        sanitized: Dict[str, Any] = dict(data or {})
        content_val = sanitized.get('content') or ''
        title_val = sanitized.get('title') or ''
        if not content_val and title_val:
            sanitized['content'] = title_val
        if not sanitized.get('asset'):
            sanitized['asset'] = 'ALL'
        return True, sanitized, None








