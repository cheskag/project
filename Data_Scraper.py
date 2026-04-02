#!/usr/bin/env python3
"""
Continuous Crypto News Scraper - Fixed Version
Scrapes actual news articles, not just price data
"""

import os
import sys
import time
import random
import hashlib
import json
import logging
import threading
import weakref
import gc
import psutil
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Callable, List
from enum import Enum
from collections import deque, defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import signal
from dataclasses import dataclass
from enum import Enum as PyEnum

ACCESS_BLOCK_PATTERNS: tuple[str, ...] = (
    "this website is using a security service to protect itself from online attacks",
    "cloudflare ray id",
    "performance & security by cloudflare",
    "access denied",
    "blocked because of suspicious activity",
    "security solution",
    "malformed data",
    "your ip:",
)

# Shared asset inference utilities
try:
    from tools.asset_inference import infer_asset_label
except ImportError:
    tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
    if tools_path not in sys.path:
        sys.path.append(tools_path)
    from asset_inference import infer_asset_label  # type: ignore

# Load environment variables from .env file (SECURITY: Load credentials from .env, not hardcoded)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("SUCCESS: Loaded environment variables from .env file")
except ImportError:
    print("WARNING: python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"WARNING: Could not load .env file: {e}")

# Import Pydantic validation (SECURITY: Validates all scraped data)
try:
    from validation import validate_article_data, ArticleSchema
    VALIDATION_ENABLED = True
    print("SUCCESS: Pydantic validation enabled")
except ImportError as e:
    VALIDATION_ENABLED = False
    print(f"WARNING: Pydantic validation disabled: {e}")
except Exception as e:
    VALIDATION_ENABLED = False
    print(f"WARNING: Could not load validation module: {e}")

# Import comprehensive logging (SECURITY: Audit trail and monitoring)
try:
    from logger_config import setup_logger, log_security_event, log_scraping_activity
    scraper_logger = setup_logger("crypto_scraper", "scraper.log")
    LOGGING_ENABLED = True
    print("SUCCESS: Comprehensive logging enabled")
except ImportError as e:
    LOGGING_ENABLED = False
    print(f"WARNING: Logging disabled: {e}")
except Exception as e:
    LOGGING_ENABLED = False
    print(f"WARNING: Could not load logging module: {e}")

# Import shutdown manager (replaces global state)
shutdown_manager = None
shutdown_requested = False

# Cached ChromeDriver path to avoid repeated downloads
CHROMEDRIVER_PATH: Optional[str] = None
CHROMEDRIVER_LOCK = threading.Lock()

try:
    from shutdown_manager import get_shutdown_manager
    shutdown_manager = get_shutdown_manager()
    # Shutdown manager loaded silently
except ImportError:
    # Using legacy shutdown handler
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        """Handle Ctrl+C gracefully (legacy)"""
        global shutdown_requested
        shutdown_requested = True
        print("\n\nSHUTDOWN SIGNAL RECEIVED (Ctrl+C)")
        print("Stopping scraper gracefully...")
    
    signal.signal(signal.SIGINT, signal_handler)

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# MongoDB imports
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError

# Date parsing
import re
import urllib.parse
from dateutil import parser as date_parser

# Sentiment analysis
try:
    # First try normal import (same directory or installed package)
    from lstm_sentiment_analyzer import LSTMSentimentAnalyzer
except ModuleNotFoundError:
    # Try loading from custom folder named 'Sentiment Analysis'
    # Check sibling folder under data scraping
    _sent_dir = os.path.join(os.path.dirname(__file__), 'Sentiment Analysis')
    if os.path.isdir(_sent_dir):
        if _sent_dir not in sys.path:
            sys.path.insert(0, _sent_dir)
        try:
            from lstm_sentiment_analyzer import LSTMSentimentAnalyzer  # type: ignore
        except Exception as _e:
            print(f"WARNING: Could not import LSTMSentimentAnalyzer from 'Sentiment Analysis': {_e}")
            # Minimal fallback to keep runtime working
            class LSTMSentimentAnalyzer:  # type: ignore
                def __init__(self):
                    self.is_trained = False
                def load_model(self, base_path: str):
                    self.is_trained = False
                def predict_sentiment(self, text: str):
                    return {"sentiment": "neutral", "confidence": 0.5, "polarity": 0.0}
    else:
        # Try top-level 'Sentiment Analysis' folder one directory up
        _sent_dir_top = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Sentiment Analysis')
        if os.path.isdir(_sent_dir_top):
            if _sent_dir_top not in sys.path:
                sys.path.insert(0, _sent_dir_top)
            try:
                from lstm_sentiment_analyzer import LSTMSentimentAnalyzer  # type: ignore
            except Exception as _e:
                print(f"WARNING: Could not import LSTMSentimentAnalyzer from top-level 'Sentiment Analysis': {_e}")
                class LSTMSentimentAnalyzer:  # type: ignore
                    def __init__(self):
                        self.is_trained = False
                    def load_model(self, base_path: str):
                        self.is_trained = False
                    def predict_sentiment(self, text: str):
                        return {"sentiment": "neutral", "confidence": 0.5, "polarity": 0.0}
        else:
            print("WARNING: 'Sentiment Analysis' folder not found; using neutral fallback")
            class LSTMSentimentAnalyzer:  # type: ignore
                def __init__(self):
                    self.is_trained = False
                def load_model(self, base_path: str):
                    self.is_trained = False
                def predict_sentiment(self, text: str):
                    return {"sentiment": "neutral", "confidence": 0.5, "polarity": 0.0}


# ============================================================================
# ENHANCED PERFORMANCE SYSTEMS
# ============================================================================

class CircuitState(PyEnum):
    """Circuit Breaker states"""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, failing fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service is back

@dataclass
class HealthMetrics:
    """Health monitoring metrics"""
    timestamp: datetime
    memory_usage_mb: float
    memory_percent: float
    cpu_percent: float
    active_threads: int
    cache_size: int
    retry_count: int
    success_rate: float
    sources_processed: int
    articles_found: int
    errors_count: int

class CircuitBreaker:
    """Circuit Breaker pattern for robust error handling"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60, half_open_max_calls: int = 3):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0
        self._lock = threading.RLock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise Exception(f"Circuit breaker is OPEN - {self.timeout - (time.time() - self.last_failure_time):.1f}s remaining")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise Exception("Circuit breaker HALF_OPEN - max calls exceeded")
                self.half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.half_open_calls = 0
    
    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        with self._lock:
            return {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'last_failure_time': self.last_failure_time,
                'half_open_calls': self.half_open_calls
            }

class HealthMonitor:
    """Comprehensive health monitoring system"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.start_time = datetime.now(timezone.utc)
        self.total_cycles = 0
        self.total_articles = 0
        self.total_errors = 0
        self._lock = threading.RLock()
    
    def record_metrics(self, 
                      memory_manager: 'MemoryManager',
                      smart_cache: 'SmartCache',
                      retry_manager: 'IntelligentRetryManager',
                      sources_processed: int = 0,
                      articles_found: int = 0,
                      errors_count: int = 0):
        """Record current system metrics"""
        with self._lock:
            memory_usage = memory_manager.get_memory_usage()
            
            metrics = HealthMetrics(
                timestamp=datetime.now(timezone.utc),
                memory_usage_mb=memory_usage['rss_mb'],
                memory_percent=memory_usage['percent'],
                cpu_percent=psutil.cpu_percent(),
                active_threads=threading.active_count(),
                cache_size=smart_cache.size(),
                retry_count=sum(retry_manager.retry_stats.values()),
                success_rate=self._calculate_success_rate(),
                sources_processed=sources_processed,
                articles_found=articles_found,
                errors_count=errors_count
            )
            
            self.metrics_history.append(metrics)
            self.total_cycles += 1
            self.total_articles += articles_found
            self.total_errors += errors_count
    
    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate"""
        if not self.metrics_history:
            return 0.0
        
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
        if not recent_metrics:
            return 0.0
        
        total_sources = sum(m.sources_processed for m in recent_metrics)
        total_articles = sum(m.articles_found for m in recent_metrics)
        
        if total_sources == 0:
            return 0.0
        
        return total_articles / total_sources
    
    def get_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        with self._lock:
            if not self.metrics_history:
                return {'status': 'NO_DATA', 'message': 'No metrics recorded yet'}
            
            latest = self.metrics_history[-1]
            uptime = datetime.now(timezone.utc) - self.start_time
            
            # Calculate trends
            if len(self.metrics_history) >= 5:
                recent_avg_memory = sum(m.memory_usage_mb for m in list(self.metrics_history)[-5:]) / 5
                older_avg_memory = sum(m.memory_usage_mb for m in list(self.metrics_history)[-10:-5]) / 5
                memory_trend = "INCREASING" if recent_avg_memory > older_avg_memory else "STABLE"
            else:
                memory_trend = "INSUFFICIENT_DATA"
            
            return {
                'status': 'HEALTHY' if latest.memory_percent < 80 and latest.cpu_percent < 90 else 'WARNING',
                'uptime_hours': uptime.total_seconds() / 3600,
                'total_cycles': self.total_cycles,
                'total_articles': self.total_articles,
                'total_errors': self.total_errors,
                'current_metrics': {
                    'memory_usage_mb': latest.memory_usage_mb,
                    'memory_percent': latest.memory_percent,
                    'cpu_percent': latest.cpu_percent,
                    'active_threads': latest.active_threads,
                    'cache_size': latest.cache_size,
                    'success_rate': latest.success_rate
                },
                'trends': {
                    'memory_trend': memory_trend,
                    'success_rate': latest.success_rate
                },
                'alerts': self._generate_alerts(latest)
            }
    
    def _generate_alerts(self, latest: HealthMetrics) -> List[str]:
        """Generate health alerts based on current metrics"""
        alerts = []
        
        if latest.memory_percent > 90:
            alerts.append(f"HIGH_MEMORY: {latest.memory_percent:.1f}%")
        
        if latest.cpu_percent > 95:
            alerts.append(f"HIGH_CPU: {latest.cpu_percent:.1f}%")
        
        if latest.active_threads > 20:
            alerts.append(f"HIGH_THREAD_COUNT: {latest.active_threads}")
        
        if latest.success_rate < 0.1:
            alerts.append(f"LOW_SUCCESS_RATE: {latest.success_rate:.1%}")
        
        return alerts
    
    def get_performance_summary(self) -> str:
        """Get formatted performance summary"""
        report = self.get_health_report()
        
        if report['status'] == 'NO_DATA':
            return "No performance data available yet"
        
        summary = f"""
[HEALTH] HEALTH MONITOR REPORT
{'='*50}
Status: {report['status']}
Uptime: {report['uptime_hours']:.1f} hours
Cycles: {report['total_cycles']}
Articles: {report['total_articles']}
Errors: {report['total_errors']}

[METRICS] CURRENT METRICS:
Memory: {report['current_metrics']['memory_usage_mb']:.1f}MB ({report['current_metrics']['memory_percent']:.1f}%)
CPU: {report['current_metrics']['cpu_percent']:.1f}%
Threads: {report['current_metrics']['active_threads']}
Cache: {report['current_metrics']['cache_size']} items
Success Rate: {report['current_metrics']['success_rate']:.1%}

[TRENDS] CURRENT TRENDS:
Memory: {report['trends']['memory_trend']}
Success Rate: {report['trends']['success_rate']:.1%}
"""
        
        if report['alerts']:
            summary += f"\n[ALERTS] WARNINGS:\n"
            for alert in report['alerts']:
                summary += f"   {alert}\n"
        
        return summary

class SmartCache:
    """LRU Cache with TTL and memory management"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.access_times = {}
        self.access_order = deque()
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self.cache:
                # Check TTL
                if time.time() - self.access_times[key] < self.ttl:
                    # Update access time and order
                    self.access_times[key] = time.time()
                    if key in self.access_order:
                        self.access_order.remove(key)
                    self.access_order.append(key)
                    return self.cache[key]
                else:
                    self._evict(key)
            return None
    
    def set(self, key: str, value: Any):
        with self._lock:
            # Evict if at capacity
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[key] = value
            self.access_times[key] = time.time()
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
    
    def _evict(self, key: str):
        """Evict specific key"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            if key in self.access_order:
                self.access_order.remove(key)
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if self.access_order:
            lru_key = self.access_order.popleft()
            self._evict(lru_key)
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        return len(self.cache)

class IntelligentRetryManager:
    """Advanced retry mechanism with exponential backoff and jitter"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = 2.0
        self.retry_stats = defaultdict(int)
    
    def retry_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Retry sync function with intelligent backoff"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    print(f"Retry succeeded on attempt {attempt + 1}")
                return result
            except Exception as e:
                last_exception = e
                self.retry_stats[type(e).__name__] += 1
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, e)
                    print(f"Retry {attempt + 1}/{self.max_retries} after {delay:.2f}s: {e}")
                    time.sleep(delay)
                else:
                    print(f"All retries failed: {e}")
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int, exception: Exception) -> float:
        """Calculate delay with exponential backoff and jitter"""
        base_delay = self.base_delay * (self.backoff_multiplier ** attempt)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.3) * base_delay
        
        # Cap at max delay
        delay = min(base_delay + jitter, self.max_delay)
        
        # Special handling for specific exceptions
        if isinstance(exception, TimeoutException):
            delay *= 1.5  # Longer delay for timeouts
        elif "WebDriver" in str(type(exception)):
            delay *= 2.0  # Even longer for WebDriver issues
        
        return delay

class MemoryManager:
    """Advanced memory management with monitoring"""
    
    def __init__(self, max_memory_mb: int = 1024, cleanup_threshold: float = 0.75):
        self.max_memory_mb = max_memory_mb
        self.cleanup_threshold = cleanup_threshold
        self.operation_count = 0
        self.memory_history = deque(maxlen=100)
        self.cache_registry = weakref.WeakValueDictionary()
        self._monitor_thread = threading.Thread(target=self._monitor_memory, daemon=True)
        self._monitor_thread.start()
        
        print("Memory manager initialized")
    
    def register_cache(self, cache_name: str, cache_obj: Any):
        """Register cache for monitoring"""
        self.cache_registry[cache_name] = cache_obj
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get detailed memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024,
            'cached_mb': sum(getattr(cache, 'size', lambda: 0)() for cache in self.cache_registry.values()) / 1024 / 1024
        }
    
    def should_cleanup(self) -> bool:
        """Check if cleanup is needed"""
        memory_usage = self.get_memory_usage()
        return memory_usage['percent'] > (self.cleanup_threshold * 100)
    
    def cleanup_memory(self) -> Dict[str, int]:
        """Comprehensive memory cleanup"""
        cleanup_stats = {
            'caches_cleared': 0,
            'objects_collected': 0,
            'memory_freed_mb': 0
        }
        
        memory_before = self.get_memory_usage()
        
        # Clear registered caches
        for cache_name, cache_obj in self.cache_registry.items():
            if hasattr(cache_obj, 'clear'):
                cache_obj.clear()
                cleanup_stats['caches_cleared'] += 1
        
        # Force garbage collection
        collected = gc.collect()
        cleanup_stats['objects_collected'] = collected
        
        memory_after = self.get_memory_usage()
        cleanup_stats['memory_freed_mb'] = memory_before['rss_mb'] - memory_after['rss_mb']
        
        print(f"Memory cleanup: {cleanup_stats}")
        return cleanup_stats
    
    def _monitor_memory(self):
        """Background memory monitoring"""
        while True:
            try:
                if self.should_cleanup():
                    print("High memory usage detected - performing cleanup")
                    self.cleanup_memory()
                
                # Record memory history
                memory_usage = self.get_memory_usage()
                self.memory_history.append({
                    'timestamp': datetime.now(timezone.utc),
                    'rss_mb': memory_usage['rss_mb'],
                    'percent': memory_usage['percent']
                })
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Memory monitoring error: {e}")
                time.sleep(60)

# Initialize enhanced systems
smart_cache = SmartCache(max_size=2000, ttl=600)  # 10 minutes TTL
retry_manager = IntelligentRetryManager(max_retries=3, base_delay=1.0, max_delay=30.0)
memory_manager = MemoryManager(max_memory_mb=1024, cleanup_threshold=0.75)
health_monitor = HealthMonitor(max_history=100)

# Circuit breakers for different operations
driver_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=120)  # Driver operations
mongodb_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)  # Database operations
scraping_circuit_breaker = CircuitBreaker(failure_threshold=10, timeout=300)  # General scraping

# Register cache with memory manager
memory_manager.register_cache('main_cache', smart_cache)

# Initialize LSTM analyzer
lstm_analyzer = LSTMSentimentAnalyzer()  # Initialize sentiment analyzer

# Initialize RoBERTa Quantifier
try:
    # Try legacy in-folder package first
    from quantification.sentiment_quantifier import SentimentQuantifier  # type: ignore
    quantifier = SentimentQuantifier()
    print("RoBERTa Quantifier initialized")
except Exception:
    # Try from relocated top-level 'Sentiment Quantification' folder
    _sq_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Sentiment Quantification')
    if os.path.isdir(_sq_dir) and _sq_dir not in sys.path:
        sys.path.insert(0, _sq_dir)
    try:
        from sentiment_quantifier import SentimentQuantifier  # type: ignore
        quantifier = SentimentQuantifier()
        print("RoBERTa Quantifier initialized (top-level)")
    except Exception as e:
        print(f"WARNING: RoBERTa Quantifier not available: {e}")
        quantifier = None

# Initialize VADER Analyzer globally (for short text quantification)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    vader_analyzer = SentimentIntensityAnalyzer()
    
    # Enhance VADER with crypto-specific terms
    crypto_positive = {
        'moon': 4.0, 'mooning': 4.5, 'mooned': 4.0, 'moon-ready': 4.0,
        'bull': 3.0, 'bullish': 3.5, 'bullrun': 4.0, 'bullmarket': 3.5,
        'ATH': 4.0, 'all-time-high': 4.0, 'pump': 3.5, 'rally': 3.5,
        'surge': 3.5, 'soar': 4.0, 'breakout': 3.5, 'hodl': 3.0,
        'diamond hands': 3.0, 'stacking': 2.5, 'gains': 3.5, 'profit': 3.0,
        'green': 3.5, 'green candle': 3.5, 'winner': 3.5, 'lambo': 3.5,
        'adoption': 3.0, 'partnership': 2.5, 'excited': 3.0, 'WAGMI': 3.0
    }
    crypto_negative = {
        'crash': -4.0, 'crashing': -4.0, 'dump': -3.5, 'bear': -3.0,
        'bearish': -3.5, 'rekt': -3.5, 'bloodbath': -4.5, 'loss': -3.0,
        'red': -3.0, 'red candle': -3.0, 'scam': -4.5, 'rug': -4.5,
        'rug pull': -4.5, 'honeypot': -4.0, 'exit scam': -4.5, 'hack': -4.0,
        'exploit': -4.0, 'attack': -3.5, 'FUD': -2.5, 'fear': -3.0,
        'risky': -2.0, 'volatile': -2.5, 'failure': -3.5, 'doomed': -4.0,
        'NGMI': -2.5, 'weak hands': -2.0
    }
    vader_analyzer.lexicon.update(crypto_positive)
    vader_analyzer.lexicon.update(crypto_negative)
    print("VADER Analyzer initialized with crypto-specific terms")
except Exception as e:
    print(f"WARNING: VADER Analyzer not available: {e}")
    vader_analyzer = None

# MongoDB connection - Loaded from environment variables
# SECURITY: Credentials loaded from .env file, not hardcoded
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    print("ERROR: MONGO_URI not found in environment variables.")
    print("Please set MONGO_URI in your .env file.")
    raise ValueError("MONGO_URI not found in environment variables. Please set MONGO_URI in your .env file.")
else:
    print("SUCCESS: Using MONGO_URI from environment variables")

# Persistent bookmark state (per-source next page)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scraper_state.json')

def load_scraper_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"State load error: {e}")
    return {}

def save_scraper_state(state: dict) -> None:
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"State save error: {e}")

def get_next_page_bookmark(source_name: str) -> int:
    state = load_scraper_state()
    try:
        page = int(state.get(source_name, {}).get('next_page', 1))
        return page if page >= 1 else 1
    except Exception:
        return 1

def set_next_page_bookmark(source_name: str, next_page: int) -> None:
    state = load_scraper_state()
    if source_name not in state:
        state[source_name] = {}
    state[source_name]['next_page'] = int(max(1, next_page))
    state[source_name]['updated_at'] = datetime.utcnow().isoformat() + 'Z'
    save_scraper_state(state)

def set_last_scrape_time(source_name: str, items_found: int) -> None:
    """Track when source was last scraped and if it was successful"""
    state = load_scraper_state()
    if source_name not in state:
        state[source_name] = {}
    
    state[source_name]['last_scrape_time'] = datetime.now(timezone.utc).isoformat()
    
    if items_found > 0:
        state[source_name]['last_success_time'] = datetime.now(timezone.utc).isoformat()
        state[source_name]['last_success_count'] = items_found
    else:
        state[source_name]['last_failure_time'] = datetime.now(timezone.utc).isoformat()
    
    save_scraper_state(state)

def should_scrape_source(source_name: str) -> tuple[bool, str]:
    """
    Determine if source should be scraped this cycle based on recent activity
    Returns: (should_scrape: bool, reason: str)
    """
    state = load_scraper_state()
    source_state = state.get(source_name, {})
    
    # Always scrape if never scraped before
    if 'last_scrape_time' not in source_state:
        return True, "Never scraped before"
    
    try:
        last_scrape = datetime.fromisoformat(source_state['last_scrape_time'].replace('Z', '+00:00'))
        time_since_scrape = (datetime.now(timezone.utc) - last_scrape).total_seconds() / 60  # minutes
        
        # Get last success time
        last_success_time = source_state.get('last_success_time')
        if last_success_time:
            last_success = datetime.fromisoformat(last_success_time.replace('Z', '+00:00'))
            time_since_success = (datetime.now(timezone.utc) - last_success).total_seconds() / 60
        else:
            time_since_success = float('inf')
        
        # FIXED SCHEDULING RULES - MORE AGGRESSIVE DATA COLLECTION:
        
        # Rule 1: If found content recently (< 2 min ago), skip for 2 minutes only
        if time_since_success < 2:
            return False, f"Found content {time_since_success:.0f}m ago - checking again in {2-time_since_success:.0f}m"
        
        # Rule 2: If last scrape was < 1 minute ago (regardless of result), skip
        if time_since_scrape < 1:
            return False, f"Scraped {time_since_scrape:.0f}m ago - waiting {1-time_since_scrape:.0f}m"
        
        # REMOVED Rule 3: Don't penalize sources with no recent content - keep checking frequently
        
        # All conditions passed - scrape this source
        return True, f"Ready to scrape (last: {time_since_scrape:.0f}m ago)"
        
    except Exception as e:
        # On any error, allow scraping
        return True, f"Error checking schedule: {e}"

# OPTIMIZED SPEED: Faster scraping without affecting accuracy
PAGE_LOAD_TIMEOUT = int(os.getenv('PAGE_LOAD_TIMEOUT', '10'))  # OPTIMIZED: 10s (reduced from 15s)
IMPLICIT_WAIT = int(os.getenv('IMPLICIT_WAIT', '1'))  # OPTIMIZED: 1s (reduced from 3s) - still enough for elements
SLEEP_BETWEEN_SOURCES = float(os.getenv('SLEEP_BETWEEN_SOURCES', '2'))  # OPTIMIZED: 2s (reduced from 5s) - avoids detection while faster
SLEEP_BETWEEN_CYCLES = float(os.getenv('SLEEP_BETWEEN_CYCLES', '3'))  # OPTIMIZED: 3s (reduced from 5s)
SLEEP_TWITTER_BETWEEN = float(os.getenv('SLEEP_TWITTER_BETWEEN', '20'))  # OPTIMIZED: 20s (reduced from 30s) - still safe for API limits

# Volume controls - FIXED FOR MAXIMUM DATA COLLECTION
# Increased pages to prevent early exits and collect more data
MAX_PAGES_PER_SOURCE = int(os.getenv('MAX_PAGES_PER_SOURCE', '15'))  # FIXED: Increased to 15 pages for more data
MAX_ELEMENTS_PER_PAGE = int(os.getenv('MAX_ELEMENTS_PER_PAGE', '75'))  # FIXED: Increased to 75 elements per page
MAX_TWITTER_PAGES = int(os.getenv('MAX_TWITTER_PAGES', '5'))  # Twitter API pagination


# UA rotation to avoid bot detection - using latest real Chrome versions
USER_AGENTS = [
    # AGGRESSIVE SPEED FIX: Expanded user agent pool for better anti-detection
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]

# Global deny substrings applied to all sites
GLOBAL_DENY_SUBSTRINGS = [
    '/about', '/privacy', '/terms', '/cookies',
    '/newsletter', '/subscribe', '/sponsored', '/press', '/advertise',
    '/jobs', '/careers', '/contact', '/consent', '/preferences',
    '/rss', '/sitemap', '/feed', '/api',
    '/submit', '/request', '/partners', '/mentions', '/editorial-policy',
    '/login', '/register', '/signin', '/signup',
    # Non-article paths (site pages, not content)
    '/about', '/privacy', '/terms', '/cookies',
    '/price/', '/prices', '/rankings', '/category/', '/tag/',
    '/author/', '/authors/', '/bonus-hunter/', '/top-picks/',
    '/special-edition/', '/crypto-bonus/', '/price-indexes/', '/price-prediction/',
    
    # Empty category listing pages (not actual articles) - relaxed to allow whitelisted guides/press
    # '/type/learn/', '/type/guest-expert/', '/type/press-release/',
    
    # Product pages (casinos, betting - not crypto news)
    '/casino/', '/betting/',
    
    # Event/conf pages (not articles)
    '/events/', '/webinar/', '/conference/',
]

# Early de-dup cache (in-memory)
MAX_SEEN_URLS = int(os.getenv('MAX_SEEN_URLS', '10000'))
# LRU Cache for seen URLs - automatically evicts oldest when full
SEEN_URLS = OrderedDict()

def remember_url(url: str) -> None:
    """Add URL to LRU cache, evicting oldest if cache is full"""
    try:
        if url in SEEN_URLS:
            # Move to end (most recently used)
            SEEN_URLS.move_to_end(url)
            return
        
        # Add new URL
        SEEN_URLS[url] = None
        
        # Evict oldest entries if cache exceeds limit
        while len(SEEN_URLS) > MAX_SEEN_URLS:
            SEEN_URLS.popitem(last=False)  # Remove oldest (FIFO)
    except Exception:
        pass

def is_url_seen(url: str) -> bool:
    """Check if URL is in cache and update its position (LRU)"""
    if url in SEEN_URLS:
        SEEN_URLS.move_to_end(url)  # Mark as recently used
        return True
    return False

# Source prioritization (removed blocking - all sources should be tried)

# Success rate tracking
SUCCESS_RATES = {}

def track_success(source_name: str, success: bool) -> float:
    """PHASE 4: Success tracking with detailed metrics"""
    global SUCCESS_RATES
    
    if source_name not in SUCCESS_RATES:
        SUCCESS_RATES[source_name] = {"success": 0, "total": 0, "last_success": None, "consecutive_failures": 0}
    
    SUCCESS_RATES[source_name]["total"] += 1
    if success:
        SUCCESS_RATES[source_name]["success"] += 1
        SUCCESS_RATES[source_name]["last_success"] = datetime.now(timezone.utc)
        SUCCESS_RATES[source_name]["consecutive_failures"] = 0
    else:
        SUCCESS_RATES[source_name]["consecutive_failures"] += 1
    
    rate = SUCCESS_RATES[source_name]["success"] / SUCCESS_RATES[source_name]["total"]
    return rate

def prioritize_sources(sources: list) -> list:
    """Prioritize sources based on success rate"""
    # All sources are tried equally - no blocking
    return sources

def should_skip_source(source_name: str) -> bool:
    """Check if source should be skipped due to repeated failures - ULTRA LENIENT"""
    if source_name not in SUCCESS_RATES:
        return False
    
    stats = SUCCESS_RATES[source_name]
    total_attempts = stats["total"]
    success_count = stats["success"]
    
    # ULTRA LENIENT: Need at least 50 attempts before making decisions
    if total_attempts < 50:
        return False
    
    success_rate = success_count / total_attempts
    
    # Only skip if success rate is below 0.5% after 100+ attempts
    if total_attempts >= 100 and success_rate < 0.005:
        return True
    
    return False

def is_quality_content(text: str, title: str) -> bool:
    """MAXIMUM DATA COLLECTION: Accept almost everything (be lenient on titles)"""

    # MINIMAL REQUIREMENTS: Only reject extremely short content
    if len(text) < 10:
        return False

    # ONLY reject obvious spam - MAXIMUM LENIENCY
    obvious_spam = ["click here", "sign up now", "buy now", "scam", "fraud", "fake"]
    
    content_lower = (text + " " + title).lower()
    if any(spam in content_lower for spam in obvious_spam):
        return False

    # ACCEPT EVERYTHING ELSE - MAXIMUM DATA COLLECTION
    return True

def log_scraping_stats():
    """Log current scraping statistics"""
    if not SUCCESS_RATES:
        return
        
    total_sources = len(SUCCESS_RATES)
    working_sources = sum(1 for s in SUCCESS_RATES.values() if s["success"] > 0)
    
    print(f"\n=== SCRAPING STATISTICS ===")
    print(f"Total sources: {total_sources}")
    print(f"Working sources: {working_sources}")
    if total_sources > 0:
        print(f"Overall success rate: {working_sources/total_sources:.2%}")
    
    for source, stats in SUCCESS_RATES.items():
        rate = stats["success"] / stats["total"]
        print(f"  {source}: {rate:.2%} ({stats['success']}/{stats['total']})")

# Adaptive rate limiting - automatic backoff when blocked
SOURCE_BACKOFF_STATE = {}  # Tracks consecutive blocks per source
SKIPPED_SOURCES = set()  # Track sources that should be skipped for current session
LOW_PRIORITY_SOURCES = set()  # Track sources that should be scraped last

def get_adaptive_wait_time(source_name: str, is_blocked: bool = False) -> float:
    """
    Get adaptive wait time based on blocking history
    Automatically increases wait when blocked, resets on success
    TEMPORARILY SKIPS sources that are blocked for 1 hour
    """
    global SOURCE_BACKOFF_STATE, SKIPPED_SOURCES, LOW_PRIORITY_SOURCES
    
    if source_name not in SOURCE_BACKOFF_STATE:
        SOURCE_BACKOFF_STATE[source_name] = {
            'consecutive_blocks': 0,
            'last_block_time': None,
            'base_wait': SLEEP_BETWEEN_SOURCES
        }
    
    state = SOURCE_BACKOFF_STATE[source_name]
    
    # Check if source is temporarily skipped due to recent blocking
    if source_name in SKIPPED_SOURCES and state.get('last_block_time'):
        # Check if 1 hour has passed since last block
        time_since_block = (datetime.now(timezone.utc) - state['last_block_time']).total_seconds()
        if time_since_block < 3600:  # 1 hour = 3600 seconds
            remaining_minutes = int((3600 - time_since_block) / 60)
            return 0  # Skip immediately
        else:
            # 1 hour passed, remove from skip list and reset
            SKIPPED_SOURCES.discard(source_name)
            state['consecutive_blocks'] = 0
            print(f"  RETRY: {source_name} - 1 hour passed since blocking, will retry now")
    
    if is_blocked:
        # Increment block counter
        state['consecutive_blocks'] += 1
        state['last_block_time'] = datetime.now(timezone.utc)
        
        # Mark as low priority after 3 blocks (will be scraped last)
        if state['consecutive_blocks'] >= 3 and source_name not in LOW_PRIORITY_SOURCES:
            LOW_PRIORITY_SOURCES.add(source_name)
            print(f"  WARNING: {source_name} marked as LOW PRIORITY - blocked {state['consecutive_blocks']} times")
            print(f"     (Will be scraped last in queue)")
        
        # SKIP for 1 hour if blocked 5+ times
        if state['consecutive_blocks'] >= 5:
            SKIPPED_SOURCES.add(source_name)
            LOW_PRIORITY_SOURCES.discard(source_name)  # Remove from low priority if totally skipped
            print(f"  SKIPPING {source_name} for 1 hour - blocked {state['consecutive_blocks']} times")
            return 0
        
        # OPTIMIZED: Shorter backoff times for faster recovery
        backoff_levels = [10, 20, 40]  # OPTIMIZED: Reduced from [15, 30, 60] to [10, 20, 40] (still safe for rate limits)
        block_index = min(state['consecutive_blocks'] - 1, len(backoff_levels) - 1)
        wait_time = backoff_levels[block_index]
        
        print(f"  AUTO-BACKOFF: {source_name} blocked {state['consecutive_blocks']}/5 times - waiting {wait_time}s")
        return wait_time
    else:
        # Success - reset backoff gradually
        if state['consecutive_blocks'] > 0:
            state['consecutive_blocks'] = max(0, state['consecutive_blocks'] - 1)
            
            # Remove from low priority if successfully scraped
            if source_name in LOW_PRIORITY_SOURCES and state['consecutive_blocks'] == 0:
                LOW_PRIORITY_SOURCES.remove(source_name)
                print(f"  SUCCESS: {source_name} REMOVED from low priority - successfully scraped!")
            elif state['consecutive_blocks'] == 0:
                print(f"  BACKOFF RESET: {source_name} - back to normal speed")
        
        return state['base_wait']

def detect_blocking(driver, page_title: str = None, status_code: int = None) -> tuple[bool, str]:
    """
    Detect if we're being blocked or rate limited
    Returns: (is_blocked: bool, block_type: str)
    """
    try:
        # Check page title
        if not page_title:
            try:
                page_title = driver.title.lower()
            except:
                page_title = ""
        
        # Common blocking indicators in page title
        block_indicators = [
            'blocked', 'access denied', 'forbidden', 'captcha', 
            'cloudflare', 'attention required', 'just a moment',
            'rate limit', 'too many requests', '403', '429',
            'security check', 'human verification', 'are you a robot'
        ]
        
        for indicator in block_indicators:
            if indicator in page_title:
                return True, f"title:{indicator}"
        
        # Check page source for blocking patterns
        try:
            page_source = driver.page_source.lower()
            source_block_patterns = [
                'cloudflare', 'cf-browser-verification',
                'captcha', 'recaptcha', 'hcaptcha',
                'access denied', 'forbidden',
                'rate limit exceeded', 'too many requests',
                'please wait', 'try again later'
            ]
            
            for pattern in source_block_patterns:
                if pattern in page_source[:5000]:  # Check first 5000 chars only
                    return True, f"source:{pattern}"
        except:
            pass
        
        # Check status code if provided
        if status_code and status_code in [403, 429, 503]:
            return True, f"status:{status_code}"
        
        return False, "none"
        
    except Exception:
        return False, "error_detecting"

def init_cycle_stats(sources: list) -> None:
    global SCRAPE_STATS
    SCRAPE_STATS = {s['name']: {
        'saved': 0,
        'skipped_duplicate': 0,
        'skipped_nonarticle': 0,
        'skipped_external': 0,
        'errors': 0,
        'pages': 0,
        'page_time_total': 0.0,
    } for s in sources}

def inc_stat(source_name: str, key: str, amount: int = 1) -> None:
    try:
        if source_name in SCRAPE_STATS:
            SCRAPE_STATS[source_name][key] = SCRAPE_STATS[source_name].get(key, 0) + amount
    except Exception:
        pass

def note_page_time(source_name: str, seconds: float) -> None:
    try:
        if source_name in SCRAPE_STATS:
            SCRAPE_STATS[source_name]['pages'] = SCRAPE_STATS[source_name].get('pages', 0) + 1
            SCRAPE_STATS[source_name]['page_time_total'] = SCRAPE_STATS[source_name].get('page_time_total', 0.0) + float(seconds)
    except Exception:
        pass

def write_cycle_stats(cycle_number: int) -> None:
    try:
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'scraper_log_{date_str}.jsonl')
        # Compute derived metrics
        summary = {
            'cycle': cycle_number,
            'timestamp_utc': datetime.now(timezone.utc).isoformat() + 'Z',
            'stats': {}
        }
        for site, data in SCRAPE_STATS.items():
            pages = max(1, data.get('pages', 1))
            avg_page_time = data.get('page_time_total', 0.0) / float(pages)
            summary['stats'][site] = {
                'saved': data.get('saved', 0),
                'skipped_duplicate': data.get('skipped_duplicate', 0),
                'skipped_nonarticle': data.get('skipped_nonarticle', 0),
                'skipped_external': data.get('skipped_external', 0),
                'errors': data.get('errors', 0),
                'pages': data.get('pages', 0),
                'avg_page_time_s': round(avg_page_time, 3),
            }
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(summary, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"Stats write error: {e}")

def log_error(site: str, url: str, error_type: str, message: str) -> None:
    try:
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'scraper_errors_{date_str}.jsonl')
        entry = {
            'timestamp_utc': datetime.now(timezone.utc).isoformat() + 'Z',
            'site': site,
            'url': url,
            'error_type': error_type,
            'message': str(message)[:500]
        }
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        inc_stat(site, 'errors', 1)
    except Exception:
        pass

def get_mongodb_connection():
    """Get MongoDB connection with enhanced pooling"""
    try:
        # Cache the client to avoid per-save reconnect overhead
        global _mongo_client
        if '_mongo_client' in globals() and _mongo_client is not None:
            # Verify the client is usable; recreate if closed/broken
            try:
                _mongo_client.admin.command('ping')
                return _mongo_client
            except Exception:
                try:
                    _mongo_client.close()
                except Exception:
                    pass
                _mongo_client = None

        _mongo_client = MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            serverSelectionTimeoutMS=30000,  # Increased for reliability
            connectTimeoutMS=30000,          # Increased for reliability
            socketTimeoutMS=60000,           # Increased for reliability
            maxPoolSize=100,                 # Higher connection pool for performance
            minPoolSize=10,                  # Maintain more minimum connections
            maxIdleTimeMS=60000,             # Longer idle time
            retryWrites=True,                # Enable retry writes
            retryReads=True,                 # Enable retry reads
            heartbeatFrequencyMS=10000,      # More frequent heartbeat
            maxConnecting=20                 # Allow more concurrent connections
        )
        # Validate connectivity once
        _mongo_client.admin.command('ping')
        print("MongoDB connection established")
        return _mongo_client
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        # Add specific handling for network timeouts
        if "timeout" in str(e).lower() or "network" in str(e).lower():
            print("[INFO] Network timeout detected - MongoDB connection will retry automatically")
        return None


def ensure_indexes() -> bool:
    """Ensure unique indexes exist to prevent duplicates across multiple runners."""
    client = None
    try:
        client = get_mongodb_connection()
        if client is None:
            return False
        db = client['dataset4JADC']
        collection = db['cryptogauge']
        # Idempotent: create_index will no-op if already present with same spec/name
        collection.create_index([('url', 1)], name='unique_url', unique=True)
        collection.create_index([('content_hash', 1)], name='unique_content_hash', unique=True)
        collection.create_index([('normalized_content_hash', 1)], name='unique_normalized_content_hash', unique=True)
        return True
    except Exception as e:
        print(f"Index creation error: {e}")
        return False
    finally:
        # Do not close cached client; keep pool alive
        pass


_mongo_client = None
_mongo_collection = None
_mongo_indexes_ensured = False

def get_mongo_collection():
    """Get cached Mongo collection with indexes ensured."""
    global _mongo_collection, _mongo_indexes_ensured
    if _mongo_collection is not None:
        return _mongo_collection

    client = get_mongodb_connection()
    if not client:
        return None
    db = client['dataset4JADC']
    _mongo_collection = db['cryptogauge']

    if not _mongo_indexes_ensured:
        try:
            _mongo_collection.create_index([('url', 1)], name='unique_url', unique=True)
            _mongo_collection.create_index([('content_hash', 1)], name='unique_content_hash', unique=True)
            _mongo_collection.create_index([('normalized_content_hash', 1)], name='unique_normalized_content_hash', unique=True)
            _mongo_indexes_ensured = True
        except Exception:
            # Best-effort; indexes are also ensured at startup
            pass

    return _mongo_collection

def assign_asset_label(headline: str, content: str, existing_asset: str = "") -> tuple[str, tuple[str, ...]]:
    """
    Infer a primary asset label for the scraped article.

    Returns:
        asset_code: uppercase ticker or 'ALL'
        mentions: ordered tuple of tickers mentioned in the text
    """

    inferred_asset, mentions = infer_asset_label(headline or "", content or "", existing_asset or "")
    candidate = (inferred_asset or existing_asset or "").strip().upper()

    if not candidate:
        candidate = "ALL"

    return candidate, mentions


def is_crypto_related(text: str) -> bool:
    """Check if text is crypto-related - Optimized for speed and accuracy"""
    crypto_keywords = [
        # === Core Crypto Essentials ===
        'crypto', 'cryptocurrency', 'blockchain', 'defi', 'nft', 'web3', 'digital asset',

        # === Major Cryptocurrencies (market leaders that affect overall sentiment) ===
        'bitcoin', 'btc', 'ethereum', 'eth', 'xrp', 'ripple', 'xrp ledger', 'xrpl',  # Your target coins + XRP specifics
        'ripple labs', 'ripple partnership',  # XRP-specific additions
        'solana', 'sol', 'cardano', 'ada', 'polygon', 'matic',  # Major altcoins that move markets
        'dogecoin', 'doge', 'litecoin', 'ltc',  # Popular coins with market impact
        
        # === Modern High-Impact Coins (viral, institutional, or large market cap) ===
        'shiba inu', 'shib', 'pepe', 'bonk', 'floki', 'wojak', 'doge killer',  # Memecoins (proven viral impact)
        'avalanche', 'avax', 'chainlink', 'link', 'polkadot', 'dot',  # Layer 1 majors
        'tron', 'trx', 'stellar', 'xlm', 'cosmos', 'atom', 'near protocol', 'near',  # Other major alts
        'wrapped bitcoin', 'wbtc', 'staked eth', 'steth',  # Synthetic/wrapped assets

        # === Key Exchanges (major platforms that move markets) ===
        'binance', 'coinbase', 'kraken', 'okx', 'bybit', 'kucoin', 'exchange', 'dex',
        'trading platform', 'crypto exchange', 'cex',  # Additional exchange terms
        
        # === Stablecoins (MASSIVE market impact - USDT/USDC move entire markets) ===
        'stablecoin', 'usdt', 'tether', 'usdc', 'dai', 'frax', 'frax usd', 'usd coin',
        'algorithmic stablecoin', 'stablecoin regulation', 'stablecoin adoption',
        'terrra', 'ust collapse', 'stablecoin depeg', 'circle usdc',  # Major stablecoin events

        # === Market & Sentiment Terms ===
        'bullish', 'bearish', 'pump', 'dump', 'fomo', 'fud', 'whale', 'hodl',
        'market cap', 'price action', 'trading volume', 'volatility',

        # === Regulation & Institutional Drivers ===
        'sec', 'etf', 'spot etf', 'futures etf', 'regulation', 'regulatory approval', 'cbdc', 'adoption',
        'institutional', 'blackrock', 'fidelity', 'corporate adoption', 'institutional investor',
        'institutional adoption', 'corporate treasury',  # Additional institutional terms

        # Government & Regulatory Impact (major crypto price drivers)
        'government regulation', 'crypto regulation', 'financial regulation', 'banking regulation',
        'central bank', 'federal reserve', 'treasury department', 'financial regulator',
        'legislation', 'crypto law', 'digital asset regulation', 'virtual currency regulation',
        'regulatory framework', 'compliance requirement', 'regulatory approval', 'regulatory rejection',
        'ban crypto', 'crypto ban', 'mining ban', 'trading ban', 'exchange regulation',
        'kyc regulation', 'aml regulation', 'cftc', 'finra', 'occ', 'federal reserve bank',
        'monetary authority', 'financial services authority', 'securities regulator',

        # === Security & Trust Factors ===
        'trust', 'security', 'blockchain security', 'hack', 'scam', 'exploit',
        'cyber attack', 'wallet drain', 'exchange hacked', 'investor confidence',

        # === Mining, Supply & Demand (from your study) ===
        'bitcoin mining', 'mining cost', 'mining profitability', 'mining difficulty', 'proof of work',
        'proof of stake', 'energy consumption', 'limited supply', 'bitcoin demand',
        'scarcity', 'supply and demand', 'hash rate', 'block reward',
        'asic miner', 'mining pool', 'difficulty adjustment',  # Additional mining terms

        # === Social Media Influence (from your study) ===
        'bitcoin tweets', 'crypto twitter', 'social media sentiment',
        'tweet volume', 'twitter mentions', 'public sentiment', 'meme coin',
        'reddit crypto',  # Reddit is scraped, so this makes sense

        # === Google Search & Web Trends (from your study) ===
        'google trends', 'search volume', 'bitcoin interest',
        'search trend', 'public interest', 'trend analysis',
        'crypto searches', 'bitcoin popularity',  # Search trends discussed in news

        # === Market Psychology & Sentiment ===
        'market sentiment', 'market confidence', 'investor sentiment',
        'fear', 'greed', 'fear and greed', 'panic', 'euphoria',

        # === Technical & Economic Factors ===
        'inflation', 'interest rates', 'economic indicator', 'monetary policy',
        'market trend', 'price fluctuation', 'supply shock',
        'liquidity pool', 'yield farming',  # DeFi terms

        # === Influencer & Media Impact (proven market movers) ===
        'elon musk', 'tesla', 'twitter', 'spacex', 'celebrity endorsement',
        'donald trump', 'trump', 'us president', 'political influence',  # Trump has major crypto impact

        # === Major Events & Crashes ===
        'halving', 'crypto crash', 'market crash', 'ftx', 'terra', 'collapse',
        'detailed analysis', 'in-depth analysis', 'comprehensive analysis', 'research report',
        
        # === DeFi Protocols (Major platforms with massive TVL) ===
        'uniswap', 'uni', 'pancakeswap', 'cake', 'aave', 'compound', 'comp',
        'makerdao', 'dai', 'curve', 'crv', 'sushiswap', 'sushi', 'lido', 'liquid staking',
        'oneinch', 'balancer', 'bal', 'frax finance', 'frax',  # Top DeFi protocols
        
        # === Layer 2 & Modern Infrastructure (MASSIVE growth sector) ===
        'layer 2', 'l2', 'arbitrum', 'optimism', 'op', 'rollup', 'zk-rollup', 'optimistic rollup',
        'starknet', 'polygon zkevm', 'scroll', 'base', 'coinbase layer 2',  # L2 explosion
        'bridges', 'cross-chain', 'bridge hack', 'atomic swap', 'interoperability',
        
        # === Crypto Infrastructure & Tools (Essential for adoption) ===
        'metamask', 'hardware wallet', 'ledger', 'trezor', 'cold storage', 'hot wallet',
        'wallet security', 'seed phrase', 'private key', 'crypto wallet', 'web3 wallet',
        'gas fees', 'gas prices', 'network congestion', 'transaction fee', 'priority fee',
        
        # === Corporate & Payment Adoption (Huge market sentiment driver) ===
        'paypal crypto', 'paypal bitcoin', 'visa crypto', 'mastercard crypto',
        'amazon crypto', 'apple crypto', 'google crypto', 'microsoft crypto',
        'tesla', 'tesla bitcoin', 'microstrategy', 'mstr',  # Corporate treasury adoption
        'corporate treasury', 'reserve asset', 'bitcoin reserve', 'balance sheet',
        'crypto payment', 'merchant adoption', 'crypto merchant', 'payment processor',
        
        # === Memecoins & Viral Content (Proven market movers) ===
        'meme coin', 'meme token', 'dogecoin', 'shiba inu', 'pepe', 'bonk', 'floki',
        'wojak', 'meme stock', 'retail frenzy', 'reddit pump', 'tiktok crypto',
        
        # === Modern Staking & Restaking (Major trend) ===
        'liquid staking', 'lido staking', 'staked eth', 'restaking', 'eigenlayer',
        'liquid restaking', 'lsd', 'staking apy', 'staking yield', 'staking rewards',
        
        # === Regional Regulation (Major price impacts) ===
        'european union', 'mica', 'europe crypto', 'eu regulation',
        'china crypto ban', 'china bitcoin ban', 'indian crypto', 'indian cryptocurrency',
        'hong kong crypto', 'singapore crypto', 'singapore regulation', 'switzerland crypto',
        'el salvador bitcoin', 'bitcoin legal tender', 'adoption nation',
        'japan crypto', 'south korea crypto', 'philippines crypto', 'thailand crypto',
        
        # === Central Banks & Institutional (Price moving decisions) ===
        'central bank digital currency', 'cbdc', 'digital yuan', 'digital euro', 'digital dollar',
        'federal reserve crypto', 'fed digital currency', 'bank of england crypto',
        'bank of japan crypto', 'people\'s bank of china', 'ecb crypto',
        
        # === Major Companies & Exchanges (News drivers) ===
        'tether', 'circle', 'cryptocurrency exchange', 'crypto exchange hack',
        'exchange outage', 'trading halt', 'withdrawal suspended', 'user funds',
        
        # === Technical Terms (Market knowledge) ===
        'proof of work', 'proof of stake', 'consensus mechanism', 'blockchain technology',
        'smart contract exploit', 'bridge exploit', 'rug pull', 'exit scam',
        'market maker', 'market liquidity', 'order book', 'spread',
        
        # === Security Incidents (Major market movers) ===
        'exchange hack', 'wallet hack', 'smart contract bug', 'protocol exploit',
        'crypto heist', 'cyber attack', 'funds stolen', 'security breach',
        
        # === Monetary Policy Impact (Proven correlation) ===
        'quantitative easing', 'qe', 'tapering', 'rate hike', 'interest rate cut',
        'inflation hedge', 'digital gold', 'store of value', 'safe haven asset',
        
        # === Media & Social Trends (Sentiment drivers) ===
        'crypto twitter', 'crypto influencer', 'youtube crypto', 'tiktok crypto',
        'media coverage', 'mainstream adoption', 'crypto ads', 'super bowl crypto'
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in crypto_keywords)


def is_access_block_page(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(pattern in lower for pattern in ACCESS_BLOCK_PATTERNS)


def is_news_article(text: str, url: str) -> bool:
    """Check if this looks like a news article (not price data)"""
    text_lower = text.lower()
    url_lower = url.lower()

    # Skip obvious non-article URLs - Keep only essential filters
    skip_patterns = [
        '/data/', '/indices/', '/tag/', '/category/', '/author/',
        '#', 'javascript:', 'mailto:', '/search', '/login',
        '/register', '/cookie', '/privacy', '/policy', '/ads/', '/advertisement',
        '/news/artificial-intelligence', '/news/technology', '/news/editors-picks',
        '/news/business', '/news/cryptocurrencies', '/news/defi', '/news/markets',
        '/news/nft', '/news/gaming', '/news/space', '/news/health', '/news/law',
        '/markets/bitcoin-price-crashes-below-112000', '/takes/', '/industry-events/',
        '/culture/', '/el-salvador-bitcoin-news/', '/guides/', '/reviews/', '/glossary/',
        '/press-releases/', '/sponsored/', '/print/', '/bitcoin-books/', '/legal/',
        '/politics/', '/featured/', '/press-releases/', '/blog/', '/stocks/'
    ]

    if any(pattern in url_lower for pattern in skip_patterns):
        return False

    # Skip very short text (likely navigation)
    if len(text) < 8:
        return False

    # Skip very long text (likely not headlines) - allow detailed articles
    if len(text) > 20000:  # Increased from 5000 to 15000 to capture detailed crypto articles
        return False

    # Must be crypto-related
    if not is_crypto_related(text):
        return False

    # Skip obvious price ticker data (short text with $ and numbers)
    if '$' in text and len(text) < 30:
        # Check if it's just price data like "BTC $50,000 2.5%"
        import re
        price_pattern = r'^\s*[A-Z]{2,5}\s*\$[\d,]+\.?\d*\s*[+-]?\d+\.?\d*%?\s*$'
        if re.match(price_pattern, text.strip()):
            return False

    return True


def analyze_sentiment_fast(text: str) -> Dict:
    """
    Sentiment Analysis: LSTM (primary sentiment classification)
    Quantification: VADER (short text) or RoBERTa (long text)
    
    Architecture:
    - LSTM: Sentiment classification (negative/neutral/positive - 3-class system)
    - VADER: Quantification for short text (<40 chars)
    - RoBERTa: Quantification for long text (>=40 chars)
    """
    try:
        # STEP 1: SENTIMENT ANALYSIS (LSTM)
        # Primary sentiment classification - this is the main prediction
        lstm_sentiment = "neutral"
        lstm_confidence = 0.5
        lstm_polarity = 0.0
        
        # Check if model is trained and can actually make predictions
        if hasattr(lstm_analyzer, 'is_trained') and lstm_analyzer.is_trained and hasattr(lstm_analyzer, 'model'):
            try:
                lstm_result = lstm_analyzer.predict_sentiment(text)
                lstm_sentiment = lstm_result.get("sentiment", "neutral")
                lstm_confidence = lstm_result.get("confidence", 0.5)
                lstm_polarity = lstm_result.get("polarity", 0.0)
            except Exception as pred_error:
                # Model exists but prediction failed (likely TF compatibility issue)
                lstm_sentiment = "neutral"
                lstm_confidence = 0.5
                lstm_polarity = 0.0
        
        # Ensure LSTM sentiment is in 3-class format (negative, neutral, positive)
        # Legacy "super positive" / "super negative" are mapped to "positive" / "negative"
        valid_sentiments = ["negative", "neutral", "positive"]
        if lstm_sentiment not in valid_sentiments:
            sentiment_mapping = {
                "super_negative": "negative",
                "super negative": "negative",
                "very_negative": "negative", 
                "very negative": "negative",
                "extremely_negative": "negative",
                "extremely negative": "negative",
                "super_positive": "positive",
                "super positive": "positive",
                "very_positive": "positive",
                "very positive": "positive",
                "extremely_positive": "positive",
                "extremely positive": "positive"
            }
            lstm_sentiment = sentiment_mapping.get(lstm_sentiment, "neutral")
        
        # STEP 2: QUANTIFICATION (Separate from sentiment analysis)
        # Choose quantifier based on text length
        quantifier_confidence = 0.5
        quantifier_polarity = 0.0
        quantifier_method = "none"
        
        text_length = len(text) if text else 0
        
        if text_length < 40:
            # SHORT TEXT: Use VADER (better for short text)
            if vader_analyzer is not None:
                try:
                    vader_scores = vader_analyzer.polarity_scores(text)
                    
                    quantifier_confidence = abs(vader_scores['compound'])
                    quantifier_polarity = vader_scores['compound']
                    
                    quantifier_method = "vader"
                except Exception as e:
                    print(f"WARNING: VADER quantification failed: {e}")
        
        else:
            # LONG TEXT: Use RoBERTa (better for long text)
            if quantifier is not None:
                try:
                    quant_result = quantifier.quantify_sentiment(text)
                    
                    quantifier_confidence = quant_result.get('confidence', 0.5)
                    quantifier_polarity = quant_result.get('score', 0.0)
                    quantifier_method = "roberta"
                    
                except Exception as e:
                    print(f"WARNING: RoBERTa quantification failed: {e}")
        
        # FINAL DECISION
        # LSTM is the primary classifier - quantification is for validation/confidence
        # They are NOT weighted equally because they do different things
        
        final_sentiment = lstm_sentiment  # LSTM decides the sentiment class
        final_confidence = lstm_confidence  # Use LSTM confidence as primary
        
        # Quantification affects confidence, not the sentiment class itself
        if lstm_confidence > 0.8:
            # High confidence from LSTM - trust it
            validation_status = "high_confidence_lstm"
        else:
            quantifier_supports = (
                quantifier_method != "none" and
                abs(quantifier_polarity) >= 0.1 and
                (
                    (lstm_polarity > 0 and quantifier_polarity > 0) or
                    (lstm_polarity < 0 and quantifier_polarity < 0) or
                    (abs(lstm_polarity) < 0.1 and abs(quantifier_polarity) < 0.1)
                )
            )
            
            if quantifier_supports:
                final_confidence = min(1.0, lstm_confidence + 0.1)
                validation_status = f"validated_by_{quantifier_method}"
            elif quantifier_method != "none" and abs(lstm_polarity - quantifier_polarity) < 0.3:
            # Close agreement - moderate confidence
                validation_status = f"moderate_agreement_{quantifier_method}"
            else:
                # Disagreement - reduce confidence but still use LSTM
                final_confidence = max(0.3, lstm_confidence - 0.2)
                if quantifier_method != "none":
                    validation_status = f"disagreement_with_{quantifier_method}"
                else:
                    validation_status = "single_model"

        return {
            # Final results
            "confidence": final_confidence,
            "polarity": lstm_polarity,
            "validation_status": validation_status,
            
            # Sentiment analysis results (LSTM)
            "lstm_sentiment": lstm_sentiment,
            "lstm_confidence": lstm_confidence,
            "lstm_polarity": lstm_polarity,
            
            # Quantification results (VADER or RoBERTa)
            "quantifier_confidence": quantifier_confidence,
            "quantifier_polarity": quantifier_polarity,
            "quantifier_method": quantifier_method,  # "vader", "roberta", or "none"
            
            # Metadata
            "text_length": text_length
        }
        
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return {
            "confidence": 0.5,
            "polarity": 0.0,
            "validation_status": "error",
            "lstm_sentiment": "neutral",
            "lstm_confidence": 0.5,
            "lstm_polarity": 0.0,
            "quantifier_confidence": 0.5,
            "quantifier_polarity": 0.0,
            "quantifier_method": "none",
            "dual_validation": False
        }


def extract_date_from_url(url: str) -> Optional[datetime]:
    """Extract publication date from URL patterns"""
    try:
        # URL date patterns
        patterns = [
            r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2025/09/26/
            r'/(\d{4})-(\d{1,2})-(\d{1,2})',  # /2025-09-26
            r'/(\d{4})/(\d{1,2})/(\d{1,2})',   # /2025/09/26
            r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2025/09/26/
            r'/(\d{2})/(\d{1,2})/(\d{1,2})/',  # /25/09/26/ (2-digit year)
            r'/(\d{4})(\d{2})(\d{2})',         # /20250926
            r'/(\d{4})/(\d{2})/(\d{2})',       # /2025/09/26
            r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2025/9/26/
            r'/(\d{4})-(\d{1,2})-(\d{1,2})-',  # /2025-09-26-
            r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2025/09/26/
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups
                    # Handle 2-digit years
                    if len(year) == 2:
                        year = f"20{year}" if int(year) < 50 else f"19{year}"

                    try:
                        return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                    except ValueError:
                        continue

        return None
    except Exception:
        return None


def extract_date_from_element(driver, element) -> Optional[datetime]:
    """Extract date from page elements """
    try:
        # Look for date elements near the current element
        date_selectors = [
            '.date', '.published', '.timestamp', '.time', '.created',
            '[datetime]', '[data-date]', '[data-time]', '[data-published]',
            '.article-date', '.post-date', '.news-date', '.publish-date',
            'time', '.date-published', '.entry-date', '.post-time'
        ]

        # Check current element and its parents
        current_element = element
        for level in range(5):  # Check up to 5 parent levels
            try:
                # Check for datetime attributes
                datetime_attr = current_element.get_attribute('datetime')
                if datetime_attr:
                    try:
                        return date_parser.parse(datetime_attr)
                    except:
                        pass

                # Check for data attributes
                for attr in ['data-date', 'data-time', 'data-published']:
                    attr_value = current_element.get_attribute(attr)
                    if attr_value:
                        try:
                            return date_parser.parse(attr_value)
                        except:
                            pass

                # Check for date text in element
                element_text = current_element.text.strip()
                if element_text:
                    parsed_date = parse_date_text(element_text)
                    if parsed_date:
                        return parsed_date

                # Look for date elements within current element
                for selector in date_selectors:
                    try:
                        date_element = current_element.find_element(By.CSS_SELECTOR, selector)
                        date_text = date_element.text.strip()
                        if date_text:
                            parsed_date = parse_date_text(date_text)
                            if parsed_date:
                                return parsed_date
                    except:
                        continue

                # Move to parent element
                current_element = current_element.find_element(By.XPATH, '..')

            except:
                break

        return None
    except Exception:
        return None


def clean_article_text(text: str) -> str:
    """
    Comprehensive text cleaning to remove unnecessary boilerplate, citations, and metadata.
    Removes:
    - Source citations (Source: TradingView, Source: Google Trends, etc.)
    - References sections
    - Image captions and metadata
    - Author attribution lines
    - Date ranges in parentheses
    - Copyright notices
    - Social media sharing prompts
    """
    if not text:
        return ""
    
    # Remove source citations (e.g., "Source: TradingView", "Source: Google Trends")
    text = re.sub(r'Source:\s*[^\n]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Source\s*:\s*[^\n]+', '', text, flags=re.IGNORECASE)
    
    # Remove "Source: TradingView (price data), author's analysis..." patterns
    text = re.sub(r'Source:\s*[^\.]+\.\s*[^\n]+', '', text, flags=re.IGNORECASE)
    
    # Remove references section - we'll handle this more carefully below
    # Don't use DOTALL here as it might remove article content
    
    # Remove image captions (e.g., "Source: TradingView\n\nAssessing the First Month...")
    # Pattern: Lines that are just "Source: ..." followed by newlines
    text = re.sub(r'^Source:\s*[^\n]+\s*\n+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove date ranges in parentheses at end of sentences
    # e.g., "From July 27 to September 4, 2025."
    text = re.sub(r'From\s+\w+\s+\d{1,2}\s+to\s+\w+\s+\d{1,2},?\s+\d{4}\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'As of\s+\w+\s+\d{1,2},?\s+\d{4}\.?', '', text, flags=re.IGNORECASE)
    
    # Remove standalone date ranges (e.g., "July 27 to September 4, 2025")
    text = re.sub(r'\w+\s+\d{1,2}\s+to\s+\w+\s+\d{1,2},?\s+\d{4}', '', text, flags=re.IGNORECASE)
    
    # Remove "last X days" patterns (e.g., "last 30 days as of September 5, 2025")
    text = re.sub(r'last\s+\d+\s+days?\s+as of\s+[^\n]+', '', text, flags=re.IGNORECASE)
    
    # Remove author attribution lines (e.g., "Author: John Doe", "By John Doe")
    text = re.sub(r'^(Author|By|Written by):\s*[^\n]+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove copyright notices
    text = re.sub(r'©\s*\d{4}\s*[^\n]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'All Rights Reserved[^\n]*', '', text, flags=re.IGNORECASE)
    
    # Remove social media prompts (e.g., "Share this article", "Follow us on")
    text = re.sub(r'Share\s+this\s+[^\n]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Follow\s+us\s+on\s+[^\n]+', '', text, flags=re.IGNORECASE)
    
    # Remove "Read more" links
    text = re.sub(r'Read\s+more[^\n]*', '', text, flags=re.IGNORECASE)
    
    # Remove standalone links (lines that are just URLs or "Link" text)
    text = re.sub(r'^https?://[^\s]+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\|\s*Link\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Remove reference-style links (e.g., "FanTokens | Link", "Text. Source | Link")
    text = re.sub(r'[^\n]+\s*\|\s*Link\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'[^\n]+\s*\|\s*link\s*', '', text, flags=re.MULTILINE)
    
    # Remove lines ending with "| Link" or "| link"
    text = re.sub(r'^[^\n]+\s*\|\s*[Ll]ink\s*$', '', text, flags=re.MULTILINE)
    
    # Remove standalone "Link" word (not part of a sentence)
    text = re.sub(r'\bLink\b(?=\s*$)', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Remove reference sections that contain links (e.g., "References\n...Link\n...")
    # This handles the entire references block
    lines = text.split('\n')
    cleaned_lines = []
    in_references = False
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        # Detect start of references section
        if line_lower.startswith('reference'):
            in_references = True
            continue
        # If we're in references and line contains "link" or "|", skip it
        if in_references:
            if 'link' in line_lower or '|' in line:
                continue
            # If we hit a blank line after references, we might be out of references
            if not line.strip():
                in_references = False
                continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Remove lines that are just separators (e.g., "---", "===", "___")
    text = re.sub(r'^[-=_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Remove phone numbers
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', text)
    
    # Remove excessive whitespace (multiple newlines, spaces)
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)  # Remove empty lines
    
    # Final cleanup: remove leading/trailing whitespace
    text = text.strip()
    
    return text


def parse_date_text(text: str) -> Optional[datetime]:
    """Parse various date text formats"""
    try:
        # Clean the text
        text = text.strip()

        # Skip if text is too long (likely not a date)
        if len(text) > 50:
            return None

        # Common date patterns
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2025-09-26
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 09/26/2025
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # 09-26-2025
            r'(\d{4})/(\d{1,2})/(\d{1,2})',  # 2025/09/26
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',   # 26 Sep 2025
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # Sep 26, 2025
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',   # 26 September 2025
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        if groups[1].isalpha():  # Month is text
                            month_map = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            month = month_map.get(groups[1].lower())
                            if month:
                                return datetime(int(groups[2]), month, int(groups[0]), tzinfo=timezone.utc)
                        else:  # Month is numeric
                            return datetime(int(groups[0]), int(groups[1]), int(groups[2]), tzinfo=timezone.utc)
                except ValueError:
                    continue

        # Try dateutil parser as fallback
        try:
            parsed = date_parser.parse(text, fuzzy=True)
            if parsed:
                return parsed.replace(tzinfo=timezone.utc)
        except:
            pass

        return None
    except Exception:
        return None

def get_chromedriver_path() -> Optional[str]:
    """Retrieve and cache chromedriver path to avoid repeated downloads."""
    global CHROMEDRIVER_PATH
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH

    with CHROMEDRIVER_LOCK:
        if CHROMEDRIVER_PATH:
            return CHROMEDRIVER_PATH
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            CHROMEDRIVER_PATH = ChromeDriverManager().install()
            return CHROMEDRIVER_PATH
        except Exception as e:
            print(f"ChromeDriverManager install failed: {e}")
            CHROMEDRIVER_PATH = None
            return None


def setup_driver():
    """Setup browser driver with enhanced performance and retry logic"""
    
    def _create_driver():
        """Create driver with enhanced options"""
        # Try Brave first
        try:
            brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
            if os.path.exists(brave_path):
                options = Options()
                options.page_load_strategy = 'eager'
                options.binary_location = brave_path
                options.add_argument('--headless=new')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--use-gl=swiftshader')
                options.add_argument('--disable-gpu-compositing')
                options.add_argument('--disable-software-rasterizer')
                options.add_argument('--disable-gpu-sandbox')
                options.add_argument('--disable-gpu-rasterization')
                options.add_argument('--disable-features=Vulkan,UseSkiaRenderer,CanvasOopRasterization,OnDeviceModel')
                options.add_argument('--disable-background-timer-throttling')
                options.add_argument('--disable-backgrounding-occluded-windows')
                options.add_argument('--disable-renderer-backgrounding')
                options.add_argument('--no-proxy-server')
                options.add_argument('--disable-translate')
                options.add_argument('--blink-settings=imagesEnabled=false')
                options.add_argument('--disable-background-networking')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-push-messaging')
                options.add_argument('--window-size=1920,1080')
                try:
                    ua = random.choice(USER_AGENTS)
                except Exception:
                    ua = USER_AGENTS[0]
                options.add_argument(f'--user-agent={ua}')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-plugins')
                options.add_argument('--disable-images')
                # REMOVED: --disable-javascript (breaks dynamic content)
                # REMOVED: --disable-css (breaks styling)
                options.add_argument('--disable-webgl')
                options.add_argument('--disable-background-timer-throttling')
                options.add_argument('--disable-backgrounding-occluded-windows')
                options.add_argument('--disable-renderer-backgrounding')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-gpu')
                # Advanced anti-detection options
                # Note: JavaScript is needed for dynamic content loading
                options.add_argument('--disable-web-security')  # Bypass CORS
                options.add_argument('--disable-features=VizDisplayCompositor')  # Reduce detection
                # Additional options to suppress Google APIs GCM errors
                options.add_argument('--disable-sync')
                options.add_argument('--disable-default-apps')
                options.add_argument('--disable-hang-monitor')
                options.add_argument('--disable-ipc-flooding-protection')
                options.add_argument('--disable-domain-reliability')
                options.add_argument('--disable-component-extensions-with-background-pages')
                options.add_argument('--log-level=3')  # Suppress USB and other Chrome errors
                # Stealth options
                options.add_argument('--disable-web-security')
                options.add_argument('--allow-running-insecure-content')
                options.add_argument('--disable-features=IsolateOrigins,site-per-process')
                options.add_argument('--disable-site-isolation-trials')
                options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                options.add_experimental_option('useAutomationExtension', False)
                # Add Chrome prefs to appear more human-like
                prefs = {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                    "profile.default_content_setting_values.notifications": 2
                }
                options.add_experimental_option("prefs", prefs)

                driver = webdriver.Chrome(options=options)
                _configure_driver(driver)
                print("Brave driver setup successful")
                return driver
        except Exception as e:
            print(f"Brave setup failed: {e}")

        # Try Chrome
        try:
            chromedriver_path = get_chromedriver_path()
            if not chromedriver_path:
                raise RuntimeError("ChromeDriver path unavailable")
            service = Service(chromedriver_path)
            options = Options()
            options.page_load_strategy = 'eager'
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--use-gl=swiftshader')
            options.add_argument('--disable-gpu-compositing')
            options.add_argument('--disable-features=Vulkan,UseSkiaRenderer,CanvasOopRasterization,OnDeviceModel')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--no-proxy-server')
            options.add_argument('--disable-translate')
            options.add_argument('--blink-settings=imagesEnabled=false')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-push-messaging')
            # Randomize window size to avoid detection
            window_sizes = ["1920,1080", "1366,768", "1440,900", "1536,864", "1280,720"]
            options.add_argument(f'--window-size={random.choice(window_sizes)}')
            try:
                ua = random.choice(USER_AGENTS)
            except Exception:
                ua = USER_AGENTS[0]
            options.add_argument(f'--user-agent={ua}')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
            # Additional options to suppress Google APIs errors
            options.add_argument('--disable-sync')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-domain-reliability')
            options.add_argument('--disable-component-extensions-with-background-pages')
            # Enhanced stealth options
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            options.add_argument('--disable-site-isolation-trials')
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            # Add Chrome prefs to appear more human-like
            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "profile.default_content_setting_values.notifications": 2
            }
            options.add_experimental_option("prefs", prefs)

            driver = webdriver.Chrome(service=service, options=options)
            _configure_driver(driver)
            print("Chrome driver setup successful")
            return driver
        except Exception as e:
            print(f"Chrome setup failed: {e}")

        print("Driver setup failed")
        return None
    
    def _configure_driver(driver):
        """Configure driver with stealth and performance settings"""
        try:
            # Block heavy resource types and analytics via CDP
            driver.execute_cdp_cmd('Network.enable', {})
            block_urls = [
                '*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.svg',
                '*.mp4', '*.webm', '*.mp3', '*.woff', '*.woff2', '*.ttf', '*.otf',
                '*googletagmanager.com*', '*google-analytics.com*', '*doubleclick.net*', '*googlesyndication.com*'
            ]
            driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': block_urls})
        except Exception:
            pass
        
        # Stealth JavaScript - hide automation traces
        stealth_js = """
        // Hide webdriver property
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        
        // Mock languages
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        
        // Mock Chrome runtime
        window.navigator.chrome = {runtime: {}};
        
        // Mock permissions
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({state: 'granted'})
            })
        });
        
        // Hide automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        
        // Mock screen properties
        Object.defineProperty(screen, 'availHeight', {get: () => 1040});
        Object.defineProperty(screen, 'availWidth', {get: () => 1920});
        Object.defineProperty(screen, 'colorDepth', {get: () => 24});
        Object.defineProperty(screen, 'height', {get: () => 1080});
        Object.defineProperty(screen, 'width', {get: () => 1920});
        
        // Mock connection
        Object.defineProperty(navigator, 'connection', {get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 2
        })});
        
        // Mock hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
        
        // Mock device memory
        Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
        
        // Mock platform
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        """
        driver.execute_script(stealth_js)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.implicitly_wait(IMPLICIT_WAIT)
    
    # Use circuit breaker for driver creation
    try:
        return driver_circuit_breaker.call(_create_driver)
    except Exception as e:
        print(f"Circuit breaker prevented driver creation: {e}")
        return None


class DriverPool:
    """Thread-safe pool for reusing Selenium drivers across tasks."""

    def __init__(self, max_size: int = 6, acquire_timeout: float = 15.0):
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self._pool: "queue.Queue[webdriver.Chrome]" = queue.Queue(maxsize=max_size)
        self._total_created = 0
        self._lock = threading.Lock()

    def acquire(self) -> Optional[webdriver.Chrome]:
        deadline = time.time() + self.acquire_timeout
        while True:
            try:
                driver = self._pool.get_nowait()
            except queue.Empty:
                driver = self._create_if_capacity()
                if driver:
                    return driver
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                try:
                    driver = self._pool.get(timeout=remaining)
                except queue.Empty:
                    return None
            if self._is_driver_healthy(driver):
                return driver
            self._dispose(driver)

    def release(self, driver: Optional[webdriver.Chrome]):
        if not driver:
            return
        if not self._is_driver_healthy(driver):
            self._dispose(driver)
            return
        try:
            self._pool.put_nowait(driver)
        except queue.Full:
            self._dispose(driver)

    def _create_if_capacity(self) -> Optional[webdriver.Chrome]:
        with self._lock:
            if self._total_created >= self.max_size:
                return None
            driver = setup_driver()
            if driver:
                self._total_created += 1
            return driver

    def _is_driver_healthy(self, driver: Optional[webdriver.Chrome]) -> bool:
        if not driver:
            return False
        try:
            _ = driver.title  # Simple heartbeat check
            return True
        except WebDriverException:
            return False
        except Exception:
            return False

    def _dispose(self, driver: Optional[webdriver.Chrome]):
        if not driver:
            return
        try:
            driver.quit()
        except Exception:
            pass
        with self._lock:
            if self._total_created > 0:
                self._total_created -= 1


driver_pool = DriverPool(max_size=8, acquire_timeout=20.0)


def should_block_content(article_data: Dict) -> tuple[bool, str]:
    """
    Check if content should be blocked based on blocklist
    Returns: (should_block: bool, reason: str)
    """
    title = article_data.get('title', '').lower()
    content = article_data.get('content', '').lower()
    headline = article_data.get('headline', '').lower()
    
    # Comprehensive blocklist (built-in patterns)
    BLOCKLIST_PATTERNS = [
        # Reddit Discussion Threads
        'daily discussion',
        'daily general discussion',
        'weekly discussion',
        'monthly discussion',
        'general discussion thread',
        'daily crypto discussion',
        'daily thread',
        'skeptics discussion',
        
        # Meta/Admin Posts
        'daily reminder',
        'daily dose',
        'daily reminder to',
        'reminder:',
        'announcement:',
        'meta discussion',
        'subreddit update',
        'new moderator',
        'rule change',
        
        # Low-Quality Content
        'megathread',
        'weekly recap',
        'daily recap',
        'daily roundup',
        'what are your moves tomorrow',
        'what are you buying',
        'weekend discussion',
        'what happened this week',
        
        # Promotional/Spam (VERY SPECIFIC - only block obvious spam, not mentions in articles)
        '[removed]',
        '[deleted]',
        'join our discord',
        'check out our telegram',
        # REMOVED 'subscribe to' - too aggressive, blocks legitimate articles
        # REMOVED 'follow us on' - too aggressive
        'free crypto giveaway',
        'free coins scam',
        'airdrop scam',
        
        # Reddit-specific
        'upvote this',
        'karma farming',
        'cake day',
        'happy cake day',
    ]
    
    # Load additional patterns from external file (if exists)
    try:
        blocklist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content_blocklist.txt')
        if os.path.exists(blocklist_file):
            with open(blocklist_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        if line.lower() not in [p.lower() for p in BLOCKLIST_PATTERNS]:
                            BLOCKLIST_PATTERNS.append(line.lower())
    except Exception as e:
        # If file read fails, just use built-in patterns
        pass
    
    # Check ONLY title (not content) - content might mention these naturally
    # RELAXED: Only block if pattern appears in title/headline, not in article content
    title_check = f"{title} {headline}".strip().lower()
    
    for pattern in BLOCKLIST_PATTERNS:
        # Only block if pattern is prominent in title (not just mentioned in content)
        if pattern in title_check:
            # Additional check: only block if it's actually the focus (not just a mention)
            # This prevents blocking articles that mention "subscribe" as part of the story
            if pattern in ['daily discussion', 'daily thread', 'weekly discussion', '[removed]', '[deleted]']:
                return True, f"Blocked by pattern: '{pattern}'"
            # For other patterns, be more lenient - only block if title is very short (likely spam)
            elif len(title_check) < 100:  # Short title with spam pattern = likely spam
                return True, f"Blocked by pattern: '{pattern}'"
    
    # Additional checks for very short content (catch only truly empty content)
    # RELAXED: Allow shorter content since we're sometimes just getting headlines from URL slugs
    # The scraper will open articles to get full content when needed
    if len(content.strip()) < 5:
        return True, "Content too short (< 5 characters)"
    
    # Check if title is mostly the same as date pattern (Daily Discussion format)
    import re
    date_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}'
    if re.search(date_pattern, title, re.IGNORECASE):
        # If title contains date and "discussion", likely a daily thread
        if 'discussion' in title or 'thread' in title:
            return True, "Daily discussion thread (date pattern detected)"
    
    return False, ""

def save_to_mongodb(article_data: Dict, source_name: str) -> bool:
    """Save article to MongoDB with enhanced caching and retry logic"""
    try:
        def _normalize_text(value: Any) -> str:
            if value is None:
                return ""
            text = unicodedata.normalize("NFKC", str(value))
            text = re.sub(r'\s+', ' ', text.strip())
            return text.lower()

        # Check cache first to avoid duplicate processing
        url_value = article_data.get('url', '')
        title_value = article_data.get('title', '')
        content_value = article_data.get('content', '')

        normalized_title = _normalize_text(title_value)
        normalized_content = _normalize_text(content_value)

        cache_key = hashlib.md5(f"{normalized_title}|{normalized_content}".encode('utf-8')).hexdigest()
        content_fingerprint = hashlib.md5(normalized_content.encode('utf-8')).hexdigest()
        title_fingerprint = hashlib.md5(normalized_title.encode('utf-8')).hexdigest()
        
        # Check if we've already processed this URL recently
        cached_result = smart_cache.get(cache_key)
        if cached_result:
            print(f"    CACHED: {article_data.get('title', 'No title')[:50]}... (skipping)")
            return cached_result
        
        # Check blocklist first
        should_block, block_reason = should_block_content(article_data)
        if should_block:
            print(f"    BLOCKED: {article_data.get('title', 'No title')[:50]}...")
            print(f"       Reason: {block_reason}")
            smart_cache.set(cache_key, False)  # Cache the negative result
            return False
        
        # Check content quality - RELAXED for news sources, STRICT for Reddit/Twitter
        title = article_data.get('title', '')
        content = content_value
        
        # Determine source type from source_name
        is_news_source = any(news in source_name.lower() for news in ['cointelegraph', 'coindesk', 'decrypt', 'coingape', 'beincrypto', 'utoday', 'bitcoin', 'cryptonews', 'potato', 'block', 'bankless', 'coinbureau', 'defiant', 'ambcrypto', 'dailyhodl', 'cryptobasic'])
        is_reddit = 'reddit' in source_name.lower() or any(sub in source_name.lower() for sub in ['cryptocurrency', 'bitcoin', 'ethereum', 'defi', 'nft', 'technology', 'xrp', 'markets'])
        is_twitter = 'twitter' in source_name.lower() or any(handle in source_name.lower() for handle in ['vitalik', 'elon', 'musk', 'aantonop', 'saylor', 'dixon', 'andreessen', 'trump'])
        
        # Apply minimum content length check globally
        if not content or len(content) < 100:
            print(f"    SKIPPED (Content too short: {len(content)} chars): {title[:50]}...")
            smart_cache.set(cache_key, False)
            return False

        if is_access_block_page(content):
            print(f"    SKIPPED (Access-block / security page detected): {title[:50]}...")
            smart_cache.set(cache_key, False)
            return False
        
        if is_reddit or is_twitter:
            # STRICT: Reddit/Twitter have random content, apply quality check
            if not is_quality_content(content, title):
                print(f"    SKIPPED (Low Quality): {title[:50]}...")
                smart_cache.set(cache_key, False)
                return False
        else:
            # Default quality check for unknown sources
            if not is_quality_content(content, title):
                print(f"    SKIPPED (Low Quality): {title[:50]}...")
                smart_cache.set(cache_key, False)
                return False
        
        print(f"    PASSED CHECKS - Attempting to save: {article_data.get('title', 'No title')[:50]}...")
        
        # SECURITY: Validate article data with Pydantic BEFORE saving to MongoDB
        if VALIDATION_ENABLED:
            # Prepare data for validation
            validation_data = {
                'title': title,
                'content': content,
                'source': source_name,
                'url': url_value,
                'scraped_at': article_data.get('scraped_at', datetime.now(timezone.utc)),
            }
            
            # Optional fields
            if article_data.get('author'):
                validation_data['author'] = article_data.get('author')
            
            # Include dual validation info
            if article_data.get('validation_status'):
                validation_data['validation_status'] = article_data.get('validation_status')
            if article_data.get('lstm_confidence'):
                validation_data['lstm_confidence'] = article_data.get('lstm_confidence')
            if article_data.get('quantifier_confidence') is not None:
                validation_data['quantifier_confidence'] = article_data.get('quantifier_confidence')
            
            # Validate
            is_valid, validated_dict, error_msg = validate_article_data(validation_data)
            if not is_valid:
                print(f"    REJECTED (Validation Failed): {title[:50]}...")
                print(f"       Error: {error_msg}")
                smart_cache.set(cache_key, False)
                return False
            print(f"    VALIDATED: Data passed Pydantic validation")
        
        # Use retry manager for database operations
        def _save_article():
            collection = get_mongo_collection()
            if collection is None:
                raise Exception("MongoDB connection failed!")

            assigned_asset, asset_mentions = assign_asset_label(
                article_data.get('title', ''),
                content_value,
                article_data.get('asset', '')
            )

            enhanced_data = {
                'unique_id': article_data.get('unique_id', ''),
                'date_published': article_data.get('date_published', datetime.now(timezone.utc)),
                'scraped_at': datetime.now(timezone.utc),
                'url': url_value,
                'language': 'en',
                'headline': article_data.get('title', ''),
                'content': content_value,
                'type': 'news',
                'asset': assigned_asset,
                'lstm_sentiment': article_data.get('lstm_sentiment', 'neutral'),
                'lstm_polarity': article_data.get('lstm_polarity', 0.0),
                'lstm_confidence': article_data.get('lstm_confidence', 0.5),
                'quantifier_polarity': article_data.get('quantifier_polarity', 0.0),
                'quantifier_confidence': article_data.get('quantifier_confidence', 0.5),
                'sentiment_confidence': article_data.get('confidence', article_data.get('lstm_confidence', 0.5)),
                'validation_status': article_data.get('validation_status', 'single_model'),
                'sentiment_5class': article_data.get('sentiment_5class'),
                'labeled_at': article_data.get('labeled_at'),
                'labeled_by': article_data.get('labeled_by'),
                'migrated_at': article_data.get('migrated_at'),
                'normalized_headline_hash': title_fingerprint,
                'normalized_content_hash': content_fingerprint,
                'content_hash': hashlib.md5(f"{url_value.strip()}{normalized_content}".encode('utf-8')).hexdigest(),
                'source': source_name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'quantifier_method': article_data.get('quantifier_method', 'none')
            }

            if asset_mentions:
                enhanced_data['asset_mentions'] = list(asset_mentions)

            # Quick duplicate check using cache
            if collection.find_one({'url': url_value}, {'_id': 1}):
                print(f"    DUPLICATE: URL already in database - {title[:50]}...")
                smart_cache.set(cache_key, False)
                return False
            normalized_match = collection.find_one({'normalized_content_hash': content_fingerprint}, {'_id': 1})
            if normalized_match:
                print(f"    DUPLICATE: Matching content already stored (normalized fingerprint)")
                smart_cache.set(cache_key, False)
                track_success(source_name, True)
                return False

            # Attempt insert; unique indexes provide safety if race occurs
            print(f"    Inserting document to MongoDB (unique url/content_hash enforced)...")
            result = collection.insert_one(enhanced_data)
            
            if result.inserted_id:
                print(f"    SUCCESS: SAVED TO MONGODB: {enhanced_data['headline'][:50]}... (ID: {result.inserted_id})")
                track_success(source_name, True)
                return True
            else:
                print(f"    FAILED TO SAVE - No inserted_id returned")
                track_success(source_name, False)
                return False

        # Use circuit breaker for database operations with proper error handling
        try:
            result = mongodb_circuit_breaker.call(_save_article)
            smart_cache.set(cache_key, result)
            return result
        except Exception as e:
            error_msg = str(e).encode('ascii', 'replace').decode('ascii')
            print(f"Circuit breaker prevented MongoDB save: {error_msg}")
            smart_cache.set(cache_key, False)
            return False

    except Exception as e:
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        print(f"    MongoDB save error: {error_msg}")
        smart_cache.set(cache_key, False)  # Cache the negative result
        return False
    finally:
        # Keep cached client alive for reuse; do not close here
        pass



def scrape_twitter_api_tweepy(source_config: dict) -> int:
    """Scrape Twitter using official Twitter API (Tweepy)"""
    try:
        import tweepy
        import os

        username = source_config['url']
        source_name = source_config['name']

        print(f"  Using Tweepy API for @{username}...")

        # Get Bearer Token from environment variables (or optional local file)
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if not bearer_token:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                token_path = os.path.join(base_dir, 'TWITTER_BEARER_TOKEN.txt')
                if os.path.exists(token_path):
                    with open(token_path, 'r', encoding='utf-8') as tf:
                        bearer_token = tf.read().strip()
            except Exception:
                pass

        if not bearer_token:
            print(f"  ERROR: Twitter Bearer Token not set for @{username}")
            print(f"     To use Tweepy (official Twitter API), you need to:")
            print(f"     1. Get your Bearer Token from Twitter Developer Portal")
            print(f"     2. Set this environment variable:")
            print(f"        - TWITTER_BEARER_TOKEN")
            print(f"     Alternative: Set credentials in Windows Environment Variables")
            print(f"     Optional: put token in data scraping/TWITTER_BEARER_TOKEN.txt")
            return 0

        # Use provided Bearer Token for OAuth 2.0
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        if not bearer_token:
            print(f"    ERROR: TWITTER_BEARER_TOKEN not set")
            return 0

        try:
            # Create Tweepy client with Bearer Token
            client = tweepy.Client(bearer_token=bearer_token)
            print(f"    Using OAuth 2.0 Bearer Token")

        except Exception as e:
            print(f"    ERROR: Bearer Token authentication failed: {e}")
            return 0

        # Get user ID
        user_response = client.get_user(username=username)
        if not user_response.data:
            print(f"  User @{username} not found")
            return 0

        user_id = user_response.data.id

        # Pagination using since_id from state
        state = load_scraper_state()
        since_id_key = f"twitter_since_id::{username}"
        since_id = state.get(since_id_key)

        tweets_list = []
        page_count = 0
        pagination_token = None
        newest_id = since_id
        
        # Error handling: limit retries to avoid wasting time
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3  # Skip source after 3 consecutive failures
        total_errors = 0
        MAX_TOTAL_ERRORS = 5  # Skip source after 5 total errors

        while page_count < MAX_TWITTER_PAGES:
            kwargs = {
                'id': user_id,
                'max_results': 100,
                'tweet_fields': ['created_at', 'public_metrics']
            }
            if pagination_token:
                kwargs['pagination_token'] = pagination_token
            if since_id:
                kwargs['since_id'] = since_id

            try:
                tweets_response = client.get_users_tweets(**kwargs)
                # Reset consecutive errors on success
                consecutive_errors = 0
            except Exception as api_err:
                # Increment error counters
                consecutive_errors += 1
                total_errors += 1
                
                # Check if we should skip this source
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"    WARNING: Skipping {source_name}: {MAX_CONSECUTIVE_ERRORS} consecutive errors")
                    print(f"    Last error: {api_err}")
                    break
                
                if total_errors >= MAX_TOTAL_ERRORS:
                    print(f"    WARNING: Skipping {source_name}: {MAX_TOTAL_ERRORS} total errors reached")
                    break
                
                # Handle specific error types
                err_text = str(api_err).lower()
                if '429' in err_text or 'too many requests' in err_text or 'rate limit' in err_text:
                    # EMERGENCY FIX: Better rate limit handling
                    if consecutive_errors == 1:
                        sleep_s = 3  # OPTIMIZED: Reduced from 5s to 3s (still safe)
                        print(f"    Twitter rate limit hit; waiting {sleep_s}s...")
                        time.sleep(sleep_s)
                        continue
                    elif consecutive_errors == 2:
                        sleep_s = 6  # OPTIMIZED: Reduced from 10s to 6s (still safe)
                        print(f"    Twitter rate limit hit again; waiting {sleep_s}s...")
                        time.sleep(sleep_s)
                        continue
                    else:
                        print(f"    WARNING: Persistent rate limiting on {source_name}, skipping to next source")
                        break
                
                # Network errors (DNS, connection, etc.)
                if 'failed to resolve' in err_text or 'connection' in err_text or 'network' in err_text:
                    print(f"    WARNING: Network error on {source_name}: {api_err}")
                    print(f"    Skipping to next source")
                    break
                
                # Other errors
                print(f"    Twitter API error ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {api_err}")
                
                # Wait briefly before retry
                time.sleep(2)  # OPTIMIZED: Reduced from 5s to 2s
                continue

            page_count += 1

            if not tweets_response or not tweets_response.data:
                break

            for tweet in tweets_response.data:
                if newest_id is None or int(tweet.id) > int(newest_id):
                    newest_id = tweet.id

                asset_label, asset_mentions = assign_asset_label(tweet.text, tweet.text)

                tweet_data = {
                'headline': tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                'content': tweet.text,
                'source': f"Twitter_{source_name}",
                'date_published': tweet.created_at,
                'url': f"https://twitter.com/{username}/status/{tweet.id}",
                'asset': asset_label,
                'scraped_at': datetime.now(),
                'source_type': 'twitter_api_official',
                'likes': tweet.public_metrics['like_count'],
                'retweets': tweet.public_metrics['retweet_count']
                }

                if asset_mentions:
                    tweet_data['asset_mentions'] = list(asset_mentions)

                if save_to_mongodb(tweet_data, source_name):
                    tweets_list.append(tweet_data)

            # Next page
            meta = getattr(tweets_response, 'meta', {}) or {}
            pagination_token = meta.get('next_token') if isinstance(meta, dict) else None
            if not pagination_token:
                break

        # Persist newest since_id
        if newest_id:
            state[since_id_key] = str(newest_id)
            save_scraper_state(state)

        print(f"  Collected {len(tweets_list)} tweets from @{username} via API (pages={page_count})")
        return len(tweets_list)

    except Exception as e:
        print(f"  Tweepy error for @{username}: {e}")
        return 0

def scrape_sources_concurrently(sources: list, max_workers: int = 8) -> int:  # OPTIMIZED: Pool-aligned default (8 workers)
    """
    Scrape multiple sources concurrently using thread pools
    This is the main performance improvement - concurrent processing
    """
    print(f"CONCURRENT SCRAPING: {len(sources)} sources with {max_workers} workers")
    
    total_articles = 0
    results = []
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all scraping tasks
        future_to_source = {}
        
        # Separate sources by priority (normal sources first, low priority last)
        normal_sources = []
        low_priority_list = []
        
        for source in sources:
            source_name = source['name']
            
            # Skip sources that are temporarily blocked (for 1 hour)
            if source_name in SKIPPED_SOURCES:
                # Get remaining time
                source_state = SOURCE_BACKOFF_STATE.get(source_name, {})
                if source_state.get('last_block_time'):
                    time_since = (datetime.now(timezone.utc) - source_state['last_block_time']).total_seconds()
                    if time_since < 3600:
                        remaining_min = int((3600 - time_since) / 60)
                        print(f"  SKIPPING {source_name} (blocked for {remaining_min} more minutes)")
                    else:
                        print(f"  RETRY: {source_name} (1 hour passed, will retry)")
                else:
                    print(f"  SKIPPING {source_name} (temporarily blocked)")
                continue
            
            # Check if source should be scraped this cycle
            should_scrape, reason = should_scrape_source(source_name)
            if not should_scrape:
                # Silent skip - don't print unless important
                continue
            
            # Separate into normal and low priority
            if source_name in LOW_PRIORITY_SOURCES:
                low_priority_list.append(source)
            else:
                normal_sources.append(source)
        
        # Process normal priority sources first, then low priority
        all_prioritized_sources = normal_sources + low_priority_list
        
        for source in all_prioritized_sources:
            source_name = source['name']
            source_type = source['type']
            
            # Submit task to thread pool
            if source_type == 'twitter_official_api':
                future = executor.submit(scrape_twitter_api_tweepy, source)
            else:
                # Use shared driver pool to reduce setup overhead
                future = executor.submit(scrape_source_with_pool, source)
            
            future_to_source[future] = source
        
        # Process completed tasks
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            source_name = source['name']
            
            try:
                articles_found = future.result()
                total_articles += articles_found
                results.append({
                    'source': source_name,
                    'articles': articles_found,
                    'status': 'success'
                })
                if articles_found > 0:
                    print(f"  {source_name}: {articles_found} articles")
                
            except Exception as e:
                print(f"  ERROR {source_name}: {e}")
                results.append({
                    'source': source_name,
                    'articles': 0,
                    'status': 'error',
                    'error': str(e)
                })
    
    # Summary
    successful_sources = [r for r in results if r['status'] == 'success']
    failed_sources = [r for r in results if r['status'] == 'error']
    
    print(f"\nCONCURRENT SCRAPING SUMMARY:")
    print(f"  Successful: {len(successful_sources)} sources")
    print(f"  Failed: {len(failed_sources)} sources")
    print(f"  Total Articles: {total_articles}")
    
    return total_articles


def scrape_source_with_existing_driver(driver, source_config: dict) -> int:
    """
    Execute scraping for a single source using an already-acquired driver.
    """
    if not driver:
        return 0

    source_name = source_config['name']
    source_type = source_config['type']

    try:
        if source_type in ('news', 'reddit'):
            return scrape_chronological_source(driver, source_config)
        elif source_type == 'twitter_official_api':
            return scrape_twitter_api_tweepy(source_config)
        else:
            print(f"  ERROR {source_name}: Unknown source type: {source_type}")
            return 0
    except Exception as e:
        print(f"  ERROR {source_name}: Scraping error - {e}")
        return 0


def scrape_source_with_driver(source_config: dict) -> int:
    """
    Scrape a single source with its own driver instance
    This prevents driver conflicts in concurrent processing
    """
    driver: Optional[webdriver.Chrome] = None
    try:
        driver = setup_driver()
        if not driver:
            print(f"  ERROR {source_config.get('name', 'UNKNOWN')}: Driver setup failed")
            return 0
        return scrape_source_with_existing_driver(driver, source_config)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_source_with_pool(source_config: dict) -> int:
    """
    Scrape a source using a shared driver from the global pool.
    """
    driver = driver_pool.acquire()
    if not driver:
        print(f"  WARN {source_config.get('name', 'UNKNOWN')}: No available drivers in pool")
        return 0
    try:
        return scrape_source_with_existing_driver(driver, source_config)
    finally:
        driver_pool.release(driver)


def scrape_chronological_source(driver, source_config: dict) -> int:
    """Scrape chronologically from oldest to newest pages"""
    source_name = source_config['name']
    base_url = source_config['url']
    source_type = source_config['type']
    
    # Initialize counters
    already_seen_count = 0
    
    try:
        base_domain = urllib.parse.urlparse(base_url).netloc.lower()
        if base_domain.startswith('www.'):
            base_domain = base_domain[4:]
    except Exception:
        base_domain = ""

    total_processed = 0
    consecutive_empty_pages = 0  # Track pages with no new content

    # Per-site adapter: allow/deny URL substrings
    # RESTORED: Allow-lists are essential for research data quality
    # Each site has carefully curated paths for news/analysis content
    site_allow_substrings = {
        'coindesk.com': [
            '/news/', '/markets/', '/policy/', '/tech/', '/business/', 
            '/finance/', '/layer2/', '/web3/', '/consensus-magazine/'
        ],
        'u.today': [
            '/news/',  # PHASE 1 FIX: Only accept real article URLs, not category pages
            '/opinions/', 
            '/interviews/'
            # Removed generic category URLs that were causing "Low Quality" errors
        ],
        'beincrypto.com': [
            # BeInCrypto uses direct article URLs (hyphenated, not in /news/ folder)
            # So we'll be more permissive - any article-like URL with crypto keywords
            '/', '/learn/', '/type/feature/'  # Accept core learn/features
        ],
        'decrypt.co': [
            '/news/', '/features/', '/reviews/', '/policy/', '/markets/',
            '/web3/', '/ai/', '/business/'
        ],
        'bankless.com': [
            '/read/',  # Accept all /read/ articles (most permissive)
            '/newsletter/', '/podcast/'
        ],
        'theblock.co': [
            '/post/', '/news/', '/policy/', '/data/', '/research/'
        ],
        'cointelegraph.com': [
            '/news/', '/magazine/', '/markets/', '/analysis/', '/opinion/',
            '/explained/',
            '/bitcoin/', '/ethereum/', '/altcoin', '/blockchain/', '/regulation/'
        ],
        'cryptoslate.com': [
            # CryptoSlate uses root-level article URLs (e.g., /bitcoin-price-analysis)
            # Most permissive - will be filtered by deny list
            '/', '/news/', '/insights/', '/podcasts/', '/market-reports/'
        ],
        'bitcoinmagazine.com': [
            '/news/', '/markets/', '/business/', '/culture/', '/politics/',
            '/technical/', '/legal/', '/takes/', '/print/', '/featured/'
        ],
        'cryptonews.com': [
            '/news/', '/exclusives/', '/features/', '/bitcoin-news', 
            '/ethereum-news', '/altcoin-news', '/blockchain-news', '/defi-news'
        ],
        'blockworks.co': [
            '/news/', '/research/', '/podcast/', '/newsletter/'
        ],
    }
    site_deny_substrings = {
        'u.today': [
            '/advertise', '/press-releases', '/press-releases/submit', '/airdrops', '/airdrops/submit',
            '/event/submit', '/events', '/partners', '/sponsored', '/mentions', '/about', '/jobs',
            '/privacy', '/terms', '/consent', '/rss.php', '/guides/', '/price-prediction', '/price-analysis'
        ],
        'coindesk.com': ['/about', '/privacy', '/terms', '/cookies', '/sponsored'],
        'decrypt.co': ['/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss', '/price/', '/prices'],
        'bankless.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # Bankless-specific: filter navigation/category pages
            '/topic/', '/read/topic/', '/daily-brief', '/metaversal', '/mindshare'
        ],
        'beincrypto.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # BeInCrypto-specific: filter bonus/top-picks/type pages
            '/bonus-hunter/', '/top-picks/', '/type/', '/author/', '/category/', '/price/',
            '/newsletters'  # allow selected /learn/ when whitelisted
        ],
        'theblock.co': ['/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss'],
        'cointelegraph.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # CoinTelegraph-specific: filter author/category/reference pages
            '/authors/', '/category/', '/tags/', '/tag/'  # allow /explained/ when whitelisted
        ],
        'cryptoslate.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # CryptoSlate-specific: extensive category system
            '/people/', '/companies/', '/products/', '/cryptos/', '/coins/', 
            '/insights/category/', '/podcasts/category/', '/bitcoin-retirement-calculator/'
        ],
        'bitcoinmagazine.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # BitcoinMagazine-specific: filter educational/reference pages
            '/guides/', '/reviews/', '/glossary/', '/bitcoin-books/', '/bitcoin-iras/',
            '/industry-events/', '/el-salvador-bitcoin-news/'
        ],
        'cryptonews.com': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/press-releases', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # CryptoNews-specific: filter category/section pages (they end with /)
            '/news/blockchain-news/', '/news/bitcoin-news/', '/news/ethereum-news/', '/news/altcoin-news/',
            '/news/price-analysis/', '/news/defi-news/', '/news/nft-news/', '/news/sponsored/',
            '/exclusives/features/'
        ],
        'blockworks.co': [
            '/about', '/privacy', '/terms', '/cookies', '/sponsored', '/advertise', '/jobs', '/careers', '/contact', '/rss',
            # Blockworks-specific: filter navigation pages (single words ending in /)
            '/podcasts', '/events'  # These are category pages, not individual articles
        ],
    }
    # SIMPLIFIED: Always start from page 1 (freshest content)
    # MongoDB deduplication handles preventing re-saves of existing articles
    page = 1
    max_pages = MAX_PAGES_PER_SOURCE

    print(f"  Starting {source_type} scraping: {source_name}")

    while page <= max_pages:
        try:
            # ULTRA-FAST: No delay between pages
            # if page > 1:
            # Optimized: No unnecessary delays between page loads

            # Construct URL for current page with proper pagination patterns
            page_start_time = time.time()
            if source_type == 'news':
                if page == 1:
                    # Page 1 - always the homepage (freshest content)
                    current_url = base_url
                else:
                    # Page 2+ - site-specific pagination formats
                    if base_domain == 'coindesk.com':
                        current_url = f"{base_url.rstrip('/')}?page={page}"
                    elif base_domain == 'u.today':
                        current_url = f"{base_url.rstrip('/')}/page/{page}"
                    elif base_domain == 'decrypt.co':
                        # Decrypt uses ?page=N format
                        current_url = f"{base_url.rstrip('/')}?page={page}"
                    elif base_domain == 'bankless.com':
                        # Bankless doesn't have traditional pagination, skip page 2+
                        if page > 1:
                            break
                    elif base_domain == 'beincrypto.com':
                        current_url = f"{base_url.rstrip('/')}/page/{page}"
                    elif base_domain == 'cointelegraph.com':
                        current_url = f"{base_url.rstrip('/')}/page/{page}"
                    elif base_domain == 'theblock.co':
                        current_url = f"{base_url.rstrip('/')}/page/{page}"
                    else:
                        # Default: try /page/X/ format
                        current_url = f"{base_url.rstrip('/')}/page/{page}"
            elif source_type == 'reddit':
                if page == 1:
                    current_url = f"{base_url}?sort=old"
                else:
                    # Reddit: go to older posts
                    current_url = f"{base_url}?sort=old&count={page*25}&after=t3_{page*25}"
            elif source_type == 'twitter':
                if page == 1:
                    current_url = f"{base_url}&src=recent"
                else:
                    # Twitter: chronological order
                    current_url = f"{base_url}&src=recent&page={page}"

            print(f"    Page {page}: {current_url}")

            # Load page with timeout and error handling
            page_load_failed = False
            try:
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                driver.get(current_url)
                
                # FIXED: Add random human-like delay after page load (1-3 seconds)
                time.sleep(random.uniform(0.5, 1.5))  # OPTIMIZED: Reduced from 1-3s to 0.5-1.5s
                
            except TimeoutException:
                page_load_failed = True
                print(f"    Page load timed out after {PAGE_LOAD_TIMEOUT}s, continuing...")
                # Try to proceed with whatever loaded - might be slow connection or blocking
            
            # FIXED: Add human-like scrolling with delays
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(random.uniform(0.2, 0.5))  # OPTIMIZED: Reduced from 0.5-1s to 0.2-0.5s (still enough for lazy loading)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
                time.sleep(random.uniform(0.2, 0.5))  # OPTIMIZED: Reduced scroll wait
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(0.2, 0.5))  # OPTIMIZED: Reduced scroll wait
            except Exception:
                pass  # Scrolling failed, continue anyway

            # Check if we're blocked - ENHANCED DETECTION with AUTO-BACKOFF
            try:
                page_title = driver.title
            except Exception:
                page_title = ""
            is_blocked, block_type = detect_blocking(driver, page_title=page_title)
            
            # If page load failed repeatedly, might be blocking too
            if page_load_failed:
                # Check if this is a repeated timeout for this source
                state = SOURCE_BACKOFF_STATE.get(source_name, {})
                if state.get('consecutive_blocks', 0) > 0:
                    # Already had blocks - timeout might indicate blocking
                    is_blocked = True
                    block_type = "repeated_timeout"
            
            if is_blocked:
                page_title = driver.title
                print(f"    BLOCKED DETECTED: {page_title} (type: {block_type})")
                
                # Apply adaptive backoff wait
                wait_time = get_adaptive_wait_time(source_name, is_blocked=True)
                print(f"    Auto-waiting {wait_time}s ({wait_time/60:.1f} min) before continuing...")
                time.sleep(wait_time)
                
                # Skip this page and try next cycle
                break

            # Check if page loaded successfully
            try:
                driver.find_element(By.TAG_NAME, "body")
            except Exception as e:
                print(f"    Page {page} failed to load properly: {e}")
                # Check if it's a session error and re-raise
                if "invalid session id" in str(e).lower():
                    raise e
                break

            # FIXED: More human-like scrolling with delays
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(0.2, 0.5))  # OPTIMIZED: Reduced from 0.5-1.5s to 0.2-0.5s
            except Exception:
                pass

            # Get selectors based on source type
            if source_type == 'news':
                # Default generic selectors
                generic_selectors = [
                    'h1 a', 'h2 a', 'h3 a', 'article a', '.headline a', '.title a',
                    '.article-title a', '.post-title a', '.news-title a',
                    '.entry-title a', '.story-title a', '.content-title a',
                    'a[href*="/news/"]'
                ]

                site_selectors = {
                    'coindesk.com': [
                        # MANUALLY VERIFIED: Finds 42 articles
                        'a[href*="/news/"]', 'a[href*="/markets/"]', 
                        'a div.font-serif',  # Backup: Finds 10 feature articles
                        'a[href^="/policy/"]', 'a[href^="/tech/"]', 'a[href^="/business/"]'
                    ],
                    'u.today': [
                        # MANUALLY VERIFIED: All tests returned 0 (site likely blocks or uses heavy JS)
                        # Using broad fallback selectors - may need Selenium wait/scroll
                        'article a', 'h2 a', 'h3 a', '.post a', '.entry a',
                        'a[href*="/news/"]', 'a[href*="-"]'
                    ],
                    'decrypt.co': [
                        # MANUALLY VERIFIED: Only target news/feature article links, NOT price pages
                        # Must be very specific to avoid /price/ widgets
                        'article a[href*="/news/"]', 'article a[href*="/features/"]', 
                        'article a[href*="/policy/"]', 'article a[href*="/web3/"]',
                        # Fallback: direct selectors for news sections
                        'a[href^="/news/"][href*="-"]', 'a[href^="/features/"][href*="-"]'
                    ],
                    'bankless.com': [
                        # MANUALLY VERIFIED: Test C=74, Test A=69
                        '.post a', '.article a',  # Primary: 74 articles
                        'a[href*="/read/"]',  # Backup: 69 articles
                    ],
                    'beincrypto.com': [
                        # MANUALLY VERIFIED: Test F=84
                        '[class*="post"] a', '[class*="card"] a',  # Primary: 84 articles
                        'article a', 'h2 a', 'h3 a'  # Fallback
                    ],
                    'theblock.co': [
                        # MANUALLY VERIFIED: Test F=88
                        'a[href*="-"]',  # Primary: 88 articles (hyphenated article URLs)
                        'article a', 'a[href^="/post/"]'  # Fallback
                    ],
                    'cointelegraph.com': [
                        # MANUALLY VERIFIED: Test B=59, Test E=53
                        'article a',  # Primary: 59 articles
                        'a[href*="/news/"]', 'a[href*="/magazine/"]',  # Backup: 53 articles
                        'h2 a', 'h3 a'
                    ],
                    'cryptoslate.com': [
                        # MANUALLY VERIFIED: Test D=195, Test E=164, Test A=87
                        'a[href*="-"]',  # Primary: 195 articles
                        '[class*="article"] a', '[class*="post"] a',  # Backup: 164 articles
                        'article a'  # Fallback: 87 articles
                    ],
                    'bitcoinmagazine.com': [
                        # MANUALLY VERIFIED: Test C=86
                        'h2 a', 'h3 a',  # Primary: 86 articles
                        'article a', '.article a'  # Fallback
                    ],
                    'cryptonews.com': [
                        # MANUALLY VERIFIED: Test F=385 (high - may include navigation)
                        # Using more restrictive selectors to avoid false positives
                        'article a',  # More restrictive
                        'a[href^="/news/"]', 'a[href*="/exclusives/"]',  # Specific paths
                        '[class*="article"] a', '[class*="news"] a'  # Backup
                    ],
                    'blockworks.co': [
                        # MANUALLY VERIFIED: Test A=34
                        'a[href^="/news/"]',  # Primary: 34 articles
                        'article a', 'h2 a', 'h3 a'  # Fallback
                    ],
                }

                selectors = site_selectors.get(base_domain, generic_selectors)
                # DEBUG: Show which selectors are being used - SILENT MODE
                # if base_domain in site_selectors:
                #     print(f"      Using site-specific selectors for {base_domain}: {selectors}")
                # else:
                #     print(f"      Using generic selectors (no match for {base_domain})")
            elif source_type == 'reddit':
                selectors = [
                    'h3 a', '.title a', '[data-testid="post-title"] a',
                    'a[href*="/r/"]', '.Post a', '.entry a'
                ]
            elif source_type == 'twitter':
                selectors = [
                    '[data-testid="tweet"]', '.tweet-text', '[role="article"]',
                    '.tweet', '.status', '[data-testid="tweet-text"]'
                ]

            # Find content (collect hrefs first to avoid stale elements)
            all_elements = []
            # print(f"      DEBUG: Using selectors: {selectors}")  # DEBUG - SILENT MODE
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    all_elements.extend(elements)
                    # if elements:
                    #     print(f"      Found {len(elements)} elements with selector: {selector}")
                except Exception as e:
                    # print(f"      ERROR with selector {selector}: {e}")  # DEBUG - SILENT MODE
                    continue

            # If no elements found, try generic selectors
            if not all_elements:
                # print("      No elements found with specific selectors, trying article-focused ones...")
                # Prioritize article content over navigation
                article_selectors = [
                    'article a', 'article h2 a', 'article h3 a',  # Article links
                    '.article-title a', '.headline a', '.title a',  # Title links
                    'h2 a', 'h3 a',  # Heading links
                    '.news-item a', '.post a', '.entry a',  # News/post links
                    'a[href*="/news/"]', 'a[href*="/article/"]', 'a[href*="/post/"]'  # News URLs
                ]
                for selector in article_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        all_elements.extend(elements)
                        # if elements:
                        #     print(f"      Found {len(elements)} elements with article selector: {selector}")
                    except:
                        continue

                # If still no elements, try generic selectors
                if not all_elements:
                    # print("      No article elements found, trying generic selectors...")
                    generic_selectors = ['h2 a', 'h3 a', 'article', '.title', '.headline']
                    for selector in generic_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            all_elements.extend(elements)
                            # if elements:
                            #     print(f"      Found {len(elements)} elements with generic selector: {selector}")
                        except:
                            continue

            # If still no elements, try to find any clickable links (avoid for heavy homepages)
            if not all_elements:
                if base_domain in ['u.today']:
                    # print("      Skipping generic link scan for heavy homepage (u.today)")
                    pass
                else:
                    # print("      Still no elements found, trying to find any links...")
                    try:
                        all_elements = driver.find_elements(By.TAG_NAME, 'a')
                        # print(f"      Found {len(all_elements)} total links on page")
                    except Exception as e:
                        # print(f"      Error finding links: {e}")
                        # Check if it's a session error and re-raise
                        if "invalid session id" in str(e).lower():
                            raise e
                        pass

            # print(f"    Found {len(all_elements)} elements on page {page}")

            # Snapshot hrefs to avoid stale element reference
            hrefs = []
            for el in all_elements[:MAX_ELEMENTS_PER_PAGE * 2]:  # over-collect, we'll filter down
                try:
                    href = el.get_attribute('href')
                    if href:
                        hrefs.append(href)
                except Exception:
                    continue

            # Normalize and deduplicate hrefs
            unique_urls = []
            seen_local = set()
            for href in hrefs:
                try:
                    url_candidate = href if href.startswith('http') else None
                    if not url_candidate:
                        continue
                    # Skip external domains early
                    tdom = urllib.parse.urlparse(url_candidate).netloc.lower()
                    if tdom.startswith('www.'):
                        tdom = tdom[4:]
                    if base_domain and tdom and not tdom.endswith(base_domain):
                        continue
                    if url_candidate in seen_local:
                        continue
                    seen_local.add(url_candidate)
                    unique_urls.append(url_candidate)
                except Exception:
                    continue

            page_processed = 0
            processed_urls = set()
            external_skipped = 0
            nonarticle_skipped = 0
            considered = 0

            try:
                for i, url in enumerate(unique_urls[:MAX_ELEMENTS_PER_PAGE]):
                    try:
                        # Early URL de-dup: skip immediately if seen or in DB
                        try:
                            if is_url_seen(url):
                                already_seen_count += 1
                                continue
                            col = get_mongo_collection()
                            if col is not None and col.find_one({'url': url}, {'_id': 1}):
                                already_seen_count += 1
                                remember_url(url)
                                continue
                        except Exception as e:
                            pass
                        
                        # Only print URL when actually processing
                        print(f"      Processing new article: {url[:100]}")

                        if source_type == 'twitter':
                            # Twitter specific extraction
                            try:
                                content = ""
                            except Exception:
                                continue
                        else:
                            # News and Reddit extraction
                            # get headline textContent via JS if needed
                            content = ''

                        # Remember URL after normalization
                        try:
                            remember_url(url)
                        except Exception:
                            pass

                        # Filter out external domains (keep same-site links only)
                        try:
                            target_domain = urllib.parse.urlparse(url).netloc.lower()
                            if target_domain.startswith('www.'):
                                target_domain = target_domain[4:]
                        except Exception:
                            target_domain = ""
                        if base_domain and target_domain and not target_domain.endswith(base_domain):
                            print(f"      Skipped: External domain: {target_domain} (base: {base_domain})")
                            external_skipped += 1
                            continue

                        # Filter known non-article URL paths - Keep only essential
                        url_lower = url.lower()
                        
                        # IMPROVED: Better category page filtering
                        url_path = urllib.parse.urlparse(url).path
                        
                        # Skip URLs that end with just category names
                        if url_path.endswith('/'):
                            # Only skip very obvious category pages (very short paths)
                            path_parts = [p for p in url_path.split('/') if p]
                            # Only skip if it's a very short path (likely category)
                            if len(url_path) < 15 and len(path_parts) <= 1:
                                print(f"      Skipped: Category page: '{url[:50]}...'")
                                nonarticle_skipped += 1
                                continue
                        
                        # Skip URLs that are clearly category/listing pages
                        skip_category_patterns = [
                            '/news/artificial-intelligence/', '/news/technology/', '/news/editors-picks/',
                            '/news/business/', '/news/cryptocurrencies/', '/news/defi/', '/news/markets/',
                            '/news/nft/', '/news/gaming/', '/news/space/', '/news/health/', '/news/law/',
                            '/markets/', '/takes/', '/industry-events/', '/culture/',
                            # '/guides/',  # relaxed to allow high-value guides when whitelisted
                            '/reviews/', '/glossary/',
                            # '/press-releases/',  # relaxed to allow select press releases when whitelisted
                            '/sponsored/', '/print/',
                            '/bitcoin-books/', '/legal/', '/politics/', '/featured/', '/stocks/',
                            '/category/', '/newsletter/', '/interviews/', '/magazine/', '/reviews/',
                            '/research/', '/data/', '/analysis/', '/opinions/', '/podcasts/',
                            '/videos/', '/video/', '/interview/', '/opinion/'
                        ]
                        # Allow-list override: if site has allow-list and URL matches, don't skip
                        allow_list = site_allow_substrings.get(base_domain)
                        allowed_match = any(allow in url_lower for allow in allow_list) if allow_list else False
                        if not allowed_match and any(pattern in url_lower for pattern in skip_category_patterns):
                            print(f"      Skipped: Category/listing page: '{url[:50]}...'")
                            nonarticle_skipped += 1
                            continue
                        
                        # Start with global denies then site-specific denies (respect allow-list)
                        url_skip_patterns = list(GLOBAL_DENY_SUBSTRINGS)
                        url_skip_patterns.extend(['/submit'])
                        # Site-specific denies
                        for deny in site_deny_substrings.get(base_domain, []):
                            url_skip_patterns.append(deny)
                        if not allowed_match and any(pat in url_lower for pat in url_skip_patterns):
                            print(f"      Skipped: Non-article URL path: '{url[:50]}...'")
                            nonarticle_skipped += 1
                            continue
                        
                        # Site-specific allows: if defined, require at least one (only when defined)
                        if allow_list and not allowed_match:
                            print(f"      Skipped: URL not in allowed paths for {base_domain}")
                            nonarticle_skipped += 1
                            continue

                        # PHASE 3 FIX: Content extraction - get full article text
                        if not content or len(content) < 100:
                            try:
                                # Navigate to article URL to get full content
                                current_url = driver.current_url
                                driver.get(url)
                                time.sleep(0.3)  # OPTIMIZED: Reduced from 1s to 0.3s (page_load_strategy='eager' handles most loading)
                                
                                # Try multiple content selectors for full article text
                                content_selectors = [
                                    'article .content',
                                    'article .article-content', 
                                    '.article-body',
                                    '.post-content',
                                    'article p',
                                    '.entry-content',
                                    '.post-body',
                                    '[class*="content"] p',
                                    '[class*="article"] p'
                                ]
                                
                                full_content = ""
                                for selector in content_selectors:
                                    try:
                                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                        if elements:
                                            for elem in elements:
                                                text = elem.text.strip()
                                                if text and len(text) > 20:
                                                    full_content += text + " "
                                            if len(full_content) > 100:  # Got enough content
                                                content = full_content
                                                print(f"        [OK] Extracted full content ({len(content)} chars)")
                                                break
                                    except Exception:
                                        continue
                                
                                # Navigate back to main page
                                driver.get(current_url)
                                time.sleep(0.3)  # OPTIMIZED: Reduced from 1s to 0.3s
                            except Exception as e:
                                print(f"        Could not extract full content: {e}")

                        # EMERGENCY FIX: Extract content directly without opening new tabs
                        if (not content or len(content) < 5) and url:
                            try:
                                # Navigate directly to the URL (much faster than new tabs)
                                current_url = driver.current_url
                                driver.get(url)
                                
                                # Wait for page to load
                                try:
                                    WebDriverWait(driver, 5).until(
                                        EC.presence_of_element_located((By.TAG_NAME, 'body'))
                                    )
                                except Exception:
                                    pass  # Continue even if timeout
                                
                                # Extract title
                                title = driver.title or ""
                                
                                # Extract content using multiple strategies
                                content = ""
                                
                                # Strategy 1: Try article content selectors
                                article_selectors = [
                                    'article .content', 'article .article-content', 'article .post-content',
                                    '.article-body', '.post-body', '.content', '.entry-content',
                                    'article p', '.article-text'
                                ]
                                
                                for selector in article_selectors:
                                    try:
                                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                        if elements:
                                            for element in elements:
                                                text = element.text.strip()
                                                if text and len(text) > 20:
                                                    content += text + " "
                                            if content:
                                                break
                                    except Exception:
                                        continue
                                
                                # Strategy 2: Fallback to all paragraphs
                                if not content:
                                    try:
                                        paragraphs = driver.find_elements(By.TAG_NAME, "p")
                                        for p in paragraphs:
                                            text = p.text.strip()
                                            if text and len(text) > 20:
                                                content += text + " "
                                    except Exception:
                                        pass
                                
                                if content:
                                    print(f"        [OK] Extracted content directly ({len(content)} chars)")
                                
                                # Navigate back to original page
                                driver.get(current_url)
                                
                            except Exception as e:
                                print(f"        Error extracting content from {url}: {e}")
                                # Navigate back to original page on error
                                try:
                                    driver.get(current_url)
                                except Exception:
                                    pass

                        if not content or len(content) < 50:
                            try:
                                print(
                                    f"      Skipped: No content found ({len(content) if content else 0} chars): '{content[:30] if content else 'None'}...'"
                                )
                            except Exception:
                                print("      Skipped: No content found (logging sanitized)")
                            nonarticle_skipped += 1
                            continue
                        
                        # Ensure we never save empty/no-title items
                        if not content.strip():
                            continue

                        # Use canonical URL if captured and same domain
                        try:
                            if canonical_url:
                                tdom = urllib.parse.urlparse(canonical_url).netloc.lower()
                                if tdom.startswith('www.'):
                                    tdom = tdom[4:]
                                if not base_domain or tdom.endswith(base_domain):
                                    url = canonical_url
                        except Exception:
                            pass

                        # Allow longer articles - increased limit for detailed crypto content
                        if len(content) > 70000:
                            print(f"      Skipped: Content too long ({len(content)} chars): '{content[:30]}...'")
                            continue

                        if url in processed_urls:
                            continue
                        processed_urls.add(url)

                        # REMOVED skip_patterns check - too aggressive, blocks legitimate crypto content
                        # Crypto-related content should pass through - other filters handle spam/ads
                        
                        # Reddit-specific: only accept comments permalink pages
                        if base_domain.endswith('reddit.com') and '/comments/' not in url_lower:
                            nonarticle_skipped += 1
                            continue

                        # Skip if content is extremely short (less than 3 words)
                        if len(content.split()) < 3:
                            print(f"      Skipped: Too short ({len(content.split())} words): '{content[:50]}...'")
                            nonarticle_skipped += 1
                            continue

                        # Skip if content contains only symbols/numbers
                        if content.replace(' ', '').replace('.', '').replace(',', '').replace('%', '').replace('$', '').isdigit():
                            try:
                                print(f"      Skipped: Only numbers/symbols: '{content[:50]}...'")
                            except Exception:
                                print("      Skipped: Only numbers/symbols (logging sanitized)")
                            nonarticle_skipped += 1
                            continue

                        # Check if crypto-related (RE-ENABLED)
                        if not is_crypto_related(content):
                            print(f"      Skipped: Not crypto-related: '{content[:50]}...'")
                            nonarticle_skipped += 1
                            continue

                        print(f"      {source_type.title()} content: {content[:50]}...")
                        print(f"      Processing article for MongoDB...")

                        try:
                            # Date extraction - try multiple methods
                            publication_date = None
                            date_source = "none"

                            # Method 1: Extract from URL
                            publication_date = extract_date_from_url(url)
                            if publication_date:
                                date_source = "URL"

                            # Method 2: (disabled) element-based extraction removed in URL-first flow
                            # We rely on URL dates or fallback; page-level date can be added if needed

                            # Method 3: Use progressively older dates for chronological effect
                            if not publication_date:
                                days_ago = random.randint(page * 7, (page + 1) * 7)  # Older dates for earlier pages
                                publication_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
                                date_source = f"fallback ({days_ago} days ago)"

                            # Ensure date is timezone-aware
                            if publication_date and publication_date.tzinfo is None:
                                publication_date = publication_date.replace(tzinfo=timezone.utc)

                            # Sanity clamp publication date (avoid far-future/invalid years)
                            now_utc = datetime.now(timezone.utc)
                            if publication_date and (publication_date.year < 2009 or publication_date > now_utc + timedelta(days=1)):
                                url_based = extract_date_from_url(url)
                                publication_date = url_based if url_based else now_utc
                                date_source = "sanity_clamped"

                            # Debug: Show date extraction result
                            print(
                                f"        Date extracted: {publication_date.strftime('%Y-%m-%d %H:%M')} (from {date_source})"
                            )
                            print(f"        Debug - Final URL: {url}")

                            # Clean the extracted content AFTER date extraction to preserve date info
                            if content:
                                original_length = len(content)
                                content = clean_article_text(content)
                                if original_length != len(content):
                                    print(f"        [CLEANED] Removed {original_length - len(content)} chars of boilerplate")

                            # Derive a concise title from content (URL-first flow, element may not exist)
                            # Try to extract a proper title from the beginning of content
                            content_lines = (content or '').split('\n')
                            if content_lines:
                                # Use first line if it's reasonable length, otherwise truncate
                                first_line = content_lines[0].strip()
                                if 20 <= len(first_line) <= 200:
                                    derived_title = first_line
                                else:
                                    derived_title = first_line[:140].strip()
                            else:
                                derived_title = "Untitled Article"

                            article_data = {
                                'title': derived_title,
                                'content': content,
                                'url': url,
                                'date_published': publication_date,
                                'unique_id': f"{source_name}_{source_type}_{int(time.time())}_{random.randint(1000, 9999)}"
                            }

                            # Avoid identical headline/content where possible by truncating title only
                            if article_data['content'] and article_data['title'] == article_data['content']:
                                article_data['title'] = article_data['title'][:140].strip()

                            # Add sentiment analysis (store ALL sentiment fields)
                            sentiment_result = analyze_sentiment_fast(content)
                            article_data.update(sentiment_result)  # Add all sentiment fields to article_data

                            # Save to MongoDB
                            print(f"      Calling save_to_mongodb...")
                            if save_to_mongodb(article_data, f"{source_name}_{source_type}"):
                                page_processed += 1
                                total_processed += 1
                                print(f"      SUCCESS: Article saved to MongoDB!")
                                inc_stat(source_name, 'saved', 1)
                            else:
                                print(f"      WARNING: Article NOT saved to MongoDB!")
                                inc_stat(source_name, 'skipped_duplicate', 1)

                        except Exception as e:
                            print(f"      Error processing article: {e}")
                            log_error(source_name, url, 'process_article', e)
                            continue

                    except Exception as e:
                        print(f"      Error processing element: {e}")
                        log_error(source_name, current_url, 'process_element', e)
                        continue

                    # Early-exit heuristic: if mostly non-articles so far and nothing saved - MORE LENIENT
                    considered += 1
                    if considered >= 40 and page_processed == 0:  # INCREASED from 20 to 40 - check more elements before giving up!
                        skip_ratio = (external_skipped + nonarticle_skipped) / float(considered)
                        if skip_ratio >= 0.9:  # INCREASED from 0.8 to 0.9 - more persistent!
                            print("      Early exit: high non-article/external ratio on this page")
                            break

            except Exception as e:
                print(f"    Error processing elements on page {page}: {e}")
                continue

            # Note page time
            note_page_time(source_name, time.time() - page_start_time)
            # Only print if articles found
            if page_processed > 0:
                print(f"    Page {page}: {page_processed} items")
            
            # Page loaded successfully - gradually reset backoff
            if page_processed > 0:
                _ = get_adaptive_wait_time(source_name, is_blocked=False)
            
            # Smart early exit: Stop if no new content found
            # FIXED: Increased thresholds to prevent premature exits and collect more data
            if page_processed == 0:
                consecutive_empty_pages += 1
                
                # If page 1 is empty, check if it's really all duplicates or just no content
                if page == 1:
                    # Silent - don't print verbose message
                    # Only skip if we're sure it's duplicates, not just no content
                    if page_processed == 0 and consecutive_empty_pages >= 5:  # INCREASED from 3 to 5
                        break
                else:
                    # Continue silently
                    pass
                
                # For pages 2+, exit after 20 consecutive empty pages (FURTHER INCREASED to collect more data)
                if consecutive_empty_pages >= 20:
                    print(f"    Early exit: {consecutive_empty_pages} consecutive empty pages")
                    break
            else:
                consecutive_empty_pages = 0  # Reset on successful page
            
            # Simple page advancement (no bookmarks needed)
            page += 1
            
            # Stop if max pages reached
            if page > MAX_PAGES_PER_SOURCE:
                print(f"    Reached page limit ({MAX_PAGES_PER_SOURCE} pages scanned)")
                break

        except Exception as e:
            print(f"    Error on page {page}: {e}")
            # Check if it's a session error and re-raise to trigger session recovery
            if "invalid session id" in str(e).lower():
                raise e
            log_error(source_name, current_url if 'current_url' in locals() else '', 'page_error', e)
            break

    if 'already_seen_count' in locals():
        print(f"  Completed {source_name} ({source_type}): {total_processed} new articles, {already_seen_count} already seen/duplicates")
    else:
        print(f"  Completed {source_name} ({source_type}): {total_processed} total items saved to MongoDB")
    
    # Show current backoff status for this source - SILENT MODE
    # if source_name in SOURCE_BACKOFF_STATE:
    #     blocks = SOURCE_BACKOFF_STATE[source_name].get('consecutive_blocks', 0)
    #     if blocks > 0:
    #         print(f"    WARNING: Backoff level: {blocks}/6 (will auto-reset on success)")
    
    return total_processed


def main():
    """Main function - Continuous scraping"""
    print("Starting Continuous Crypto News Scraper...")

    # Initialize LSTM model (load existing per-asset model if available)
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Prefer BTC model as default (others can be added similarly)
        btc_model_base = os.path.join(base_dir, 'models', 'lstm_sentiment_model_btc')
        generic_model_base = os.path.join(base_dir, 'models', 'lstm_sentiment_model')

        def model_exists(model_base: str) -> bool:
            return (
                os.path.exists(f"{model_base}_model.h5") and
                os.path.exists(f"{model_base}_tokenizer.pkl") and
                os.path.exists(f"{model_base}_label_encoder.pkl")
            )

        model_to_load = None
        if model_exists(btc_model_base):
            model_to_load = btc_model_base
        elif model_exists(generic_model_base):
            model_to_load = generic_model_base

        if model_to_load:
            try:
                lstm_analyzer.load_model(model_to_load)
                print(f"LSTM model loaded successfully from {model_to_load}")
            except Exception as load_error:
                print(f"\n{'='*70}")
                print("ERROR: LSTM Model Failed to Load")
                print(f"{'='*70}")
                print(f"Error: {load_error}")
                print(f"\nThis is likely due to Python 3.13 compatibility issues with TensorFlow 2.x")
                print(f"Solutions:")
                print(f"  1. Use Python 3.12 (recommended) - see SETUP_PYTHON_312.md")
                print(f"  2. Models will use default values (neutral, 0.5 confidence)")
                print(f"  3. System will continue without sentiment analysis")
                print(f"{'='*70}\n")
        else:
            print("No LSTM model files found; continuing without LSTM...")
    except Exception as e:
        print(f"\n{'='*70}")
        print("ERROR: LSTM Model Initialization Failed")
        print(f"{'='*70}")
        print(f"Error: {e}")
        print(f"\nThis is likely due to Python 3.13 compatibility issues with TensorFlow 2.x")
        print(f"System will continue with default sentiment values")
        print(f"{'='*70}\n")

    # Test MongoDB and ensure unique indexes (for multi-runner safety)
    client = get_mongodb_connection()
    if client is not None:
        print("MongoDB connected successfully")
        ok = ensure_indexes()
        print("MongoDB indexes ensured" if ok else "MongoDB indexes not ensured")
    else:
        print("MongoDB connection failed!")
        return

    # Setup driver
    driver = setup_driver()
    if not driver:
        print("Driver setup failed!")
        return

    try:
        # Nicely categorized sources
        sources_catalog = {
            "News - Tier 1 (Major)": [
                {'name': 'CoinTelegraph', 'url': 'https://cointelegraph.com', 'type': 'news'},
                {'name': 'CoinDesk', 'url': 'https://www.coindesk.com', 'type': 'news'},
                {'name': 'TheBlock', 'url': 'https://www.theblock.co', 'type': 'news'},
                {'name': 'Decrypt', 'url': 'https://decrypt.co', 'type': 'news'},
                {'name': 'BitcoinMagazine', 'url': 'https://bitcoinmagazine.com', 'type': 'news'}
            ],
            "News - Tier 2 (Reliable)": [
                {'name': 'Blockworks', 'url': 'https://blockworks.co', 'type': 'news'},
                {'name': 'BeInCrypto', 'url': 'https://beincrypto.com', 'type': 'news'},
                {'name': 'CryptoNews', 'url': 'https://cryptonews.com', 'type': 'news'},
                {'name': 'CryptoPotato', 'url': 'https://cryptopotato.com', 'type': 'news'},
                {'name': 'CoinGape', 'url': 'https://coingape.com', 'type': 'news'},
                {'name': 'TheDailyHodl', 'url': 'https://dailyhodl.com', 'type': 'news'}
            ],
            "News - Niche/Editorial": [
                {'name': 'UToday', 'url': 'https://u.today', 'type': 'news'},
                {'name': 'BitcoinCom', 'url': 'https://bitcoin.com', 'type': 'news'},
                {'name': 'CoinBureau', 'url': 'https://www.coinbureau.com', 'type': 'news'},
                {'name': 'TheDefiant', 'url': 'https://thedefiant.io', 'type': 'news'},
                {'name': 'AMBCrypto', 'url': 'https://ambcrypto.com', 'type': 'news'},
                {'name': 'Bitcoinist', 'url': 'https://bitcoinist.com', 'type': 'news'},
                {'name': 'CoinCodex', 'url': 'https://coincodex.com', 'type': 'news'}
            ],
            "Community (Reddit)": [
                {'name': 'CryptoCurrency', 'url': 'https://www.reddit.com/r/CryptoCurrency/', 'type': 'reddit'},
                {'name': 'Bitcoin', 'url': 'https://www.reddit.com/r/Bitcoin/', 'type': 'reddit'},
                {'name': 'Ethereum', 'url': 'https://www.reddit.com/r/ethereum/', 'type': 'reddit'},
                {'name': 'CryptoMarkets', 'url': 'https://www.reddit.com/r/CryptoMarkets/', 'type': 'reddit'},
                {'name': 'DeFi', 'url': 'https://www.reddit.com/r/DeFi/', 'type': 'reddit'},
                {'name': 'NFT', 'url': 'https://www.reddit.com/r/NFT/', 'type': 'reddit'},
                {'name': 'CryptoTechnology', 'url': 'https://www.reddit.com/r/CryptoTechnology/', 'type': 'reddit'},
                {'name': 'XRP', 'url': 'https://www.reddit.com/r/XRP/', 'type': 'reddit'}
            ],
            "Influencers (Twitter API)": [
                {'name': 'VitalikButerin', 'url': 'VitalikButerin', 'type': 'twitter_official_api'},
                {'name': 'ElonMusk', 'url': 'elonmusk', 'type': 'twitter_official_api'},
                {'name': 'AndreasAntonopoulos', 'url': 'aantonop', 'type': 'twitter_official_api'},
                {'name': 'MichaelSaylor', 'url': 'saylor', 'type': 'twitter_official_api'},
                {'name': 'ChrisDixon', 'url': 'cdixon', 'type': 'twitter_official_api'},
                {'name': 'MarcAndreessen', 'url': 'pmarca', 'type': 'twitter_official_api'},
                {'name': 'CryptoGodJohn', 'url': 'CryptoGodJohn', 'type': 'twitter_official_api'},
                {'name': 'DonaldTrump', 'url': 'realDonaldTrump', 'type': 'twitter_official_api'}
            ]
        }

        # Flatten catalog into sources list while preserving category
        sources = []
        for category_name, items in sources_catalog.items():
            for s in items:
                s_with_cat = dict(s)
                s_with_cat['category'] = category_name
                sources.append(s_with_cat)

        # Brief catalog summary
        print("\nSOURCE CATALOG:")
        for category_name, items in sources_catalog.items():
            print(f"  - {category_name}: {len(items)} sources")

        cycle_count = 0

        # Optional partitioning for multi-runner mode
        try:
            runner_id = int(os.getenv('RUNNER_ID', '0'))
            runner_count = int(os.getenv('RUNNER_COUNT', '1'))
            if runner_id < 0 or runner_count < 1 or runner_id >= runner_count:
                runner_id, runner_count = 0, 1
        except Exception:
            runner_id, runner_count = 0, 1

        if runner_count > 1:
            sources = [s for idx, s in enumerate(sources) if idx % runner_count == runner_id]
            print(f"Multi-runner mode: RUNNER_ID={runner_id}, RUNNER_COUNT={runner_count}, assigned {len(sources)} sources")

        while not shutdown_requested:  # Continuous loop with shutdown check
            cycle_count += 1
            print(f"\nCycle #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print("Press Ctrl+C to stop the scraper")
            
            # Show adaptive backoff status - SILENT MODE
            # blocked_sources = [name for name, state in SOURCE_BACKOFF_STATE.items() 
            #                  if state.get('consecutive_blocks', 0) > 0]
            # if blocked_sources:
            #     print(f"WARNING: Sources in backoff mode: {', '.join(blocked_sources)}")
            #     print()

            total_articles = 0

            # Ensure a healthy, long-lived driver (reuse across cycles)
            if not driver:
                driver = setup_driver()
                if not driver:
                    print("Driver setup failed for this cycle!")
                    time.sleep(30)
                    continue
            else:
                # Health check: rebuild only if session is stale
                try:
                    _ = driver.title
                except Exception:
                    print("Driver health check failed; recreating driver...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = setup_driver()
                    if not driver:
                        print("Driver setup failed after recreation; waiting before retry...")
                        time.sleep(30)
                        continue

            # Optional periodic refresh/recreate to avoid long-run leaks
            if cycle_count % 60 == 0:
                print("Periodic driver refresh (every 60 cycles)...")
                try:
                    driver.quit()
                except:
                    pass
                driver = setup_driver()
                if not driver:
                    print("Driver setup failed after periodic refresh; waiting...")
                    time.sleep(30)
                    continue

            try:
                # Initialize per-cycle stats
                init_cycle_stats(sources)

                # Track source failures across cycles
                if not hasattr(scrape_twitter_api_tweepy, 'source_failure_count'):
                    scrape_twitter_api_tweepy.source_failure_count = {}

                # Prioritize sources and process high-priority first
                prioritized_sources = prioritize_sources(sources)
                print(f"Processing {len(prioritized_sources)} sources (prioritized by success rate)")
                
                # REMOVED: Sequential scraping - using concurrent only for better performance
                        
                # Process sources concurrently for better performance
                print(f"\nPROCESSING {len(prioritized_sources)} SOURCES CONCURRENTLY...")
                
                # Filter sources that should be scraped
                sources_to_scrape = []
                for source in prioritized_sources:
                    source_name = source['name']
                    source_type = source['type']
                    
                    # SMART SCHEDULING: Check if source should be scraped this cycle
                    should_scrape, schedule_reason = should_scrape_source(source_name)
                    if not should_scrape:
                        print(f"  SKIPPED {source_name}: {schedule_reason}")
                        continue
                    
                    # Skip sources with poor success rates
                    if should_skip_source(source_name):
                        print(f"  SKIPPED {source_name}: Low success rate (less than 10% after 5+ attempts)")
                        continue
                    
                    # Check if source has too many recent failures
                    failure_count = scrape_twitter_api_tweepy.source_failure_count.get(source_name, 0)
                    if failure_count >= 3:
                        print(f"  SKIPPED {source_name}: Too many recent failures ({failure_count})")
                        continue
                    
                    sources_to_scrape.append(source)
                
                # Use concurrent processing for better performance
                if sources_to_scrape:
                    articles_found = scrape_sources_concurrently(sources_to_scrape, max_workers=8)  # OPTIMIZED: Align workers with driver pool
                    total_articles += articles_found
                    
                    print(f"  CONCURRENT CYCLE COMPLETE: {articles_found} total articles")
                    
                    # Record health metrics
                    health_monitor.record_metrics(
                        memory_manager=memory_manager,
                        smart_cache=smart_cache,
                        retry_manager=retry_manager,
                        sources_processed=len(sources_to_scrape),
                        articles_found=articles_found,
                        errors_count=0  # TODO: Track errors from concurrent processing
                    )
                else:
                    print("  NO SOURCES TO SCRAPE THIS CYCLE")
                
            finally:
                # Keep driver alive across cycles for performance; it will be
                # recreated only on failure or periodic refresh.
                pass
            
            print(f"\n Cycle #{cycle_count} completed! Total articles saved to MongoDB: {total_articles}")
            
            # Performance dashboard with health monitoring
            print(f"\n{'='*60}")
            print(f"PERFORMANCE DASHBOARD - Cycle #{cycle_count}")
            print(f"{'='*60}")
            
            working_sources = 0
            total_sources = len(sources)
            for source_name in sources:
                if source_name['name'] in SUCCESS_RATES and SUCCESS_RATES[source_name['name']]['success'] > 0:
                    working_sources += 1
            
            print(f"Sources Status: {working_sources}/{total_sources} working")
            print(f"Success Rate: {working_sources/total_sources:.1%}")
            print(f"Articles Saved: {total_articles}")
            
            # Memory monitoring
            memory_usage = memory_manager.get_memory_usage()
            print(f"Memory Usage: {memory_usage['rss_mb']:.1f}MB ({memory_usage['percent']:.1f}%)")
            print(f"Cache Size: {smart_cache.size()} items")
            
            # Retry statistics
            if retry_manager.retry_stats:
                print(f"Retry Stats: {dict(retry_manager.retry_stats)}")
            
            # Circuit breaker status
            print(f"\nCIRCUIT BREAKER STATUS:")
            driver_state = driver_circuit_breaker.get_state()
            mongodb_state = mongodb_circuit_breaker.get_state()
            scraping_state = scraping_circuit_breaker.get_state()
            
            print(f"   Driver: {driver_state['state']} (failures: {driver_state['failure_count']})")
            print(f"   MongoDB: {mongodb_state['state']} (failures: {mongodb_state['failure_count']})")
            print(f"   Scraping: {scraping_state['state']} (failures: {scraping_state['failure_count']})")
            
            # Health monitoring report
            print(f"\n{health_monitor.get_performance_summary()}")
            
            # Show top performing sources
            top_sources = sorted(SUCCESS_RATES.items(), key=lambda x: x[1]['success'], reverse=True)[:5]
            print(f"\nTop Sources:")
            for source, stats in top_sources:
                if stats['success'] > 0:
                    rate = stats['success'] / stats['total']
                    print(f"   {source}: {stats['success']} articles ({rate:.1%})")
            
            # Memory cleanup if needed
            if memory_manager.should_cleanup():
                print(f"Performing memory cleanup...")
                cleanup_stats = memory_manager.cleanup_memory()
                print(f"   Freed {cleanup_stats['memory_freed_mb']:.1f}MB")
            
            # Write per-cycle stats summary
            write_cycle_stats(cycle_count)
            
            # Log scraping statistics every 5 cycles
            if cycle_count % 5 == 0:
                log_scraping_stats()
            
            # FIXED: Wait before next cycle with randomization to avoid detection
            sleep_time = SLEEP_BETWEEN_CYCLES + random.uniform(0, 10)  # Add random 0-10 seconds
            print(f"Waiting {sleep_time:.1f} seconds before next cycle...")
            
            # Check for shutdown signal during sleep
            for _ in range(int(sleep_time)):
                if shutdown_manager and shutdown_manager.is_shutdown_requested:
                    print("\nShutdown requested during wait period...")
                    break
                elif shutdown_requested:
                    print("\nShutdown requested during wait period...")
                    break
                time.sleep(1)
            
            # Check one final time before next cycle
            if shutdown_manager and shutdown_manager.is_shutdown_requested:
                print("\nShutdown requested, stopping scraper...")
                break
            elif shutdown_requested:
                print("\nShutdown requested, stopping scraper...")
                break
        
    except KeyboardInterrupt:
        print("\n[STOP] Scraper stopped by user (Ctrl+C)")
        print("[STATS] Final Statistics:")
        print(f"   Total articles collected: {total_articles}")
        print(f"   Cycle completed: {cycle_count}")
    except Exception as e:
        print(f"\nError: {e}")
        try:
            log_error('global', '', 'fatal', e)
        except Exception:
            pass
    finally:
        # Final cleanup
        try:
            if 'driver' in locals() and driver:
                driver.quit()
                print("Browser closed.")
            
            # Cleanup systems
            print("Cleaning up systems...")
            smart_cache.clear()
            memory_manager.cleanup_memory()
            print("Cleanup completed.")
        except Exception as e:
            print(f"Cleanup error: {e}")
            pass

def test_twitter_credentials():
    """Test if Twitter API credentials are properly configured"""
    print("Testing Twitter API Credentials...")
    try:
        import tweepy
        import os

        # Get Bearer Token from environment variables
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        if not bearer_token:
            print("ERROR: Twitter Bearer Token not set")
            print("   Please set the following environment variable:")
            print("   - TWITTER_BEARER_TOKEN")
            print("   Get this from: https://developer.twitter.com/ (Bearer Token section)")
            return False

        # Use provided Bearer Token for OAuth 2.0
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        if not bearer_token:
            print(f"    TWITTER_BEARER_TOKEN not set")
            return False

        try:
            # Create Tweepy client with Bearer Token
            client = tweepy.Client(bearer_token=bearer_token)
            print(f"    Using OAuth 2.0 Bearer Token")

        except Exception as e:
            print(f"    Bearer Token authentication failed: {e}")
            return False

        # Test with a simple user lookup (VitalikButerin)
        try:
            user_response = client.get_user(username='VitalikButerin')
            if user_response.data:
                print(f"SUCCESS: Twitter API credentials working! Found user: @{user_response.data.username}")
                return True
            else:
                print("ERROR: Twitter API credentials invalid - user not found")
                return False
        except Exception as e:
            print(f"ERROR: Twitter API error: {e}")
            return False

    except ImportError:
        print("ERROR: Tweepy not installed. Run: pip install tweepy")
        return False

def clear_database():
    """Clear all articles from MongoDB database"""
    try:
        client = get_mongodb_connection()
        if client is None:
            print("ERROR: Cannot connect to MongoDB!")
            return False
        
        db = client['crypto_articles']
        collection = db['articles']
        
        # Get count before deletion
        count_before = collection.count_documents({})
        print(f"Found {count_before} articles in database")
        
        if count_before == 0:
            print("Database is already empty")
            return True
        
        # Ask for confirmation
        confirm = input(f"Are you sure you want to delete ALL {count_before} articles? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled")
            return False
        
        # Delete all documents
        result = collection.delete_many({})
        print(f"SUCCESS: Deleted {result.deleted_count} articles from database")
        return True
        
    except Exception as e:
        print(f"ERROR clearing database: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_twitter_credentials()
        elif sys.argv[1] == "clear":
            clear_database()
        elif sys.argv[1] == "fresh":
            print("Clearing database for fresh scraping...")
            if clear_database():
                print("Starting fresh scraping...")
                main()
            else:
                print("Failed to clear database")
        else:
            print("Usage: python Data_Scraper.py [test|clear|fresh]")
            print("  test  - Test Twitter API credentials")
            print("  clear - Clear all articles from database")
            print("  fresh - Clear database and start fresh scraping")
    else:
        main()
