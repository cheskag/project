import React, { useCallback, useEffect, useMemo, useState } from "react";
import Navbar from '../components/Navbar';
import axios from '../utils/axiosConfig';
import { motion } from 'framer-motion';

const POLL_INTERVAL_MS = 60000;
const COINS_CACHE_KEY = 'cryptogauge_coins_top100_v1';
const CACHE_TTL_MS = 5 * 60 * 1000;

// Expandable Content Component for Timeline
const ExpandableContent = ({ content, title }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const maxPreviewLength = 200;
  const needsExpansion = content && content.length > maxPreviewLength;
  const previewText = needsExpansion ? content.substring(0, maxPreviewLength) + '...' : content;
  
  return (
    <div style={{ 
      fontSize: '0.9rem', 
      color: 'var(--text-subtle)',
      lineHeight: 1.5
    }}>
      <div style={{ fontStyle: isExpanded ? 'normal' : 'italic' }}>
        {isExpanded ? content : previewText}
      </div>
      {needsExpansion && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          style={{
            marginTop: '0.5rem',
            padding: '0.4rem 0.8rem',
            background: 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            borderRadius: 6,
            color: '#3b82f6',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            e.target.style.background = 'rgba(59, 130, 246, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.target.style.background = 'rgba(59, 130, 246, 0.2)';
          }}
        >
          {isExpanded ? '▼ Show Less' : '▶ Show Full Context'}
        </button>
      )}
    </div>
  );
};

// Tooltip Component (shared across all tabs)
const Tooltip = ({ text, children, id, showTooltips, setShowTooltips }) => {
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      {children}
      <button
        onClick={() => setShowTooltips(prev => ({ ...prev, [id]: !prev[id] }))}
        onMouseEnter={() => setShowTooltips(prev => ({ ...prev, [id]: true }))}
        onMouseLeave={() => setShowTooltips(prev => ({ ...prev, [id]: false }))}
        style={{
          marginLeft: '0.25rem',
          width: '18px',
          height: '18px',
          borderRadius: '50%',
          border: '1px solid rgba(59, 130, 246, 0.5)',
          background: 'rgba(59, 130, 246, 0.2)',
          color: '#3b82f6',
          fontSize: '0.75rem',
          fontWeight: 'bold',
          cursor: 'help',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 0,
          lineHeight: 1
        }}
        aria-label={text}
      >
        ?
      </button>
      {showTooltips[id] && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          marginBottom: '0.5rem',
          padding: '0.75rem',
          background: 'rgba(15, 23, 42, 0.95)',
          border: '1px solid rgba(59, 130, 246, 0.5)',
          borderRadius: 8,
          fontSize: '0.85rem',
          color: 'var(--text-primary)',
          maxWidth: '250px',
          zIndex: 1000,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          whiteSpace: 'normal'
        }}>
          {text}
          <div style={{
            position: 'absolute',
            bottom: '-5px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '5px solid transparent',
            borderRight: '5px solid transparent',
            borderTop: '5px solid rgba(59, 130, 246, 0.5)'
          }} />
        </div>
      )}
    </span>
  );
};

const Prediction = () => {
  const [intervalDays, setIntervalDays] = useState(1);
  const [intervalHours, setIntervalHours] = useState(24);
  const [backtrack, setBacktrack] = useState(20);
  const [selected, setSelected] = useState('');
  const [coins, setCoins] = useState([]);
  const [coinsLoading, setCoinsLoading] = useState(false);
  const [coinsError, setCoinsError] = useState('');
  const [coinSearch, setCoinSearch] = useState('');
  const [beginnerMode, setBeginnerMode] = useState(false);
  const [showVolatilityExplanation, setShowVolatilityExplanation] = useState(false);
  const [showTooltips, setShowTooltips] = useState({});
  
  // Insights state
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [accuracyMetrics, setAccuracyMetrics] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [historicalData, setHistoricalData] = useState([]);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [historicalError, setHistoricalError] = useState(null);
  const [livePrice, setLivePrice] = useState(null);
  const [livePriceLoading, setLivePriceLoading] = useState(false);
  const [livePriceError, setLivePriceError] = useState(null);
  const [trendForecast, setTrendForecast] = useState(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState(null);
  const [notifications, setNotifications] = useState([]);

  const selectedCoinMeta = useMemo(
    () => coins.find((coin) => coin.id === selected),
    [coins, selected],
  );

  // Notification helper
  const showNotification = useCallback((message, type = 'error') => {
    const id = Date.now();
    const notification = { id, message, type };
    setNotifications(prev => [...prev, notification]);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  }, []);

  const trendTimestamp = useMemo(() => {
    if (!trendForecast?.hour) return null;
    const parsed = new Date(trendForecast.hour);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }, [trendForecast]);

  const trendProbabilityItems = useMemo(() => {
    const probs = trendForecast?.probabilities || {};
    return [
      { key: 'up', label: 'Up', value: typeof probs.up === 'number' ? probs.up : null },
      { key: 'neutral', label: 'Neutral', value: typeof probs.neutral === 'number' ? probs.neutral : null },
      { key: 'down', label: 'Down', value: typeof probs.down === 'number' ? probs.down : null },
    ];
  }, [trendForecast]);

  const trendLabelDisplay = useMemo(() => {
    if (!trendForecast?.label) return null;
    return trendForecast.label.replace(/_/g, ' ').toUpperCase();
  }, [trendForecast]);

  const token = localStorage.getItem('token');

  const readCache = useCallback((key) => {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || !parsed.timestamp) {
        sessionStorage.removeItem(key);
        return null;
      }
      if (Date.now() - parsed.timestamp > CACHE_TTL_MS) {
        sessionStorage.removeItem(key);
        return null;
      }
      return parsed.payload;
    } catch (err) {
      sessionStorage.removeItem(key);
      return null;
    }
  }, []);

  const writeCache = useCallback((key, payload) => {
    try {
      sessionStorage.setItem(key, JSON.stringify({ timestamp: Date.now(), payload }));
    } catch (err) {
      // ignore
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadCoins = async () => {
      setCoinsLoading(true);
      setCoinsError('');
      try {
        const cached = readCache(COINS_CACHE_KEY);
        if (Array.isArray(cached) && cached.length) {
          if (!cancelled) {
            setCoins(cached);
            setSelected(cached.find((c) => c.id === 'bitcoin') ? 'bitcoin' : cached[0].id);
          }
          return;
        }

        const res = await axios.get('https://api.coingecko.com/api/v3/coins/markets', {
          params: {
            vs_currency: 'usd',
            order: 'market_cap_desc',
            per_page: 100,
            page: 1,
            sparkline: false,
            locale: 'en',
          },
          timeout: 20000,
        });
        if (cancelled) return;
        const list = Array.isArray(res.data)
          ? res.data
              .filter((c) => c && c.id && c.symbol && c.name)
              .map((c) => ({
                id: c.id,
                symbol: c.symbol?.toUpperCase() || '',
                name: c.name,
              }))
          : [];
        setCoins(list);
        setSelected(list.find((c) => c.id === 'bitcoin') ? 'bitcoin' : (list[0]?.id || ''));
        writeCache(COINS_CACHE_KEY, list);
      } catch (err) {
        if (cancelled) return;
        console.error('[Prediction] Coin list fetch failed:', err?.response?.data || err.message || err);
        setCoinsError('Unable to load coin list. Please try again later.');
      } finally {
        if (!cancelled) {
          setCoinsLoading(false);
        }
      }
    };

    loadCoins();
    return () => {
      cancelled = true;
    };
  }, [readCache, writeCache]);

  useEffect(() => {
    loadAccuracyMetrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return undefined;

    const controller = new AbortController();
    fetchHistoricalPerformance(selected, backtrack, controller.signal);
    fetchLivePrice(selected, controller.signal);

    return () => {
      controller.abort();
    };
  }, [selected, backtrack]);

  useEffect(() => {
    if (!selected) return undefined;

    const controller = new AbortController();
    const tick = () => fetchLivePrice(selected, controller.signal, true);

    const intervalId = window.setInterval(tick, POLL_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [selected]);

  const loadGeneralInsights = useCallback(async () => {
    if (!token || !selected) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Calculate date range: always start from NOW and go back by the total interval
      const now = new Date();
      // Total interval in hours: days + hours
      const totalIntervalHours = (intervalDays || 0) * 24 + (intervalHours || 0);
      // If no interval specified, default to 24 hours
      const finalIntervalHours = totalIntervalHours > 0 ? totalIntervalHours : 24;
      // Backtrack in hours (how many days to go back from now)
      const backtrackHours = (backtrack || 0) * 24;
      
      // End date is NOW minus backtrack
      const endDate = new Date(now.getTime() - backtrackHours * 60 * 60 * 1000);
      // Start date is end date minus the interval
      const startDate = new Date(endDate.getTime() - finalIntervalHours * 60 * 60 * 1000);
      
      console.log('[Frontend] Date calculation:', {
        now: now.toISOString(),
        intervalDays,
        intervalHours,
        totalIntervalHours: finalIntervalHours,
        backtrack,
        backtrackHours,
        startDate: startDate.toISOString(),
        endDate: endDate.toISOString()
      });

      const response = await axios.get('/api/insights', {
        params: {
          asset: selected,
          intervalDays,
          intervalHours,
          backtrack,
          start: startDate.toISOString(),
          end: endDate.toISOString(),
          maxDocs: 100, // Reduced for faster processing
        },
        timeout: 600000, // 10 minute timeout for insights generation (processing all documents can take time)
      });
      
      if (response.data && response.data.success) {
        setInsights(response.data.data);
        setError(null);
      } else {
        const errorMsg = response.data?.error || response.data?.details || 'Failed to load insights';
        console.error('[Insights] API returned unsuccessful response:', response.data);
        setError(errorMsg);
      }
    } catch (err) {
      console.error('[Insights] Error loading insights:', err);
      
      // Check if it's a timeout error (multiple ways to detect)
      const isTimeout = err?.isTimeout || 
                       err?.code === 'ECONNABORTED' || 
                       err?.code === 'ETIMEDOUT' ||
                       err?.message?.toLowerCase().includes('timeout') ||
                       err?.response?.status === 408 ||
                       (err?.response?.data?.error && err.response.data.error.toLowerCase().includes('timeout'));
      
      if (isTimeout) {
        // Don't show error popup for timeout - just show info notification
        // Processing all documents can take time, this is normal
        const timeoutMsg = 'Processing is taking longer than expected. This is normal when processing many documents. The system is still working - please wait or try refreshing...';
        showNotification(timeoutMsg, 'info');
        // Don't set error state to prevent popup - just show notification
        setError(null);
      } else if (err?.isNetworkError) {
        const networkMsg = err?.userMessage || 'Network error. Please check your connection and try again.';
        showNotification(networkMsg, 'error');
        setError(networkMsg);
      } else {
        const errorMsg = err?.userMessage ||
                        err?.response?.data?.error 
                        || err?.response?.data?.details 
                        || err?.message 
                        || 'Failed to load insights. Please check backend logs.';
        
        // Show as notification
        if (errorMsg.includes('timeout') || errorMsg.toLowerCase().includes('time')) {
          showNotification(errorMsg, 'warning');
        } else {
          showNotification(errorMsg, 'error');
        }
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  }, [token, selected, intervalDays, intervalHours, backtrack, showNotification]);

  const loadTrendForecast = useCallback(async () => {
    if (!token || !selected) {
      return;
    }
    setTrendLoading(true);
    setTrendError(null);
    try {
      const response = await axios.get('/api/insights/trend', {
        params: {
          asset: selected,
          intervalDays,
          intervalHours,
          backtrack,
        },
      });
      if (response.data.success) {
        setTrendForecast(response.data.data);
      } else {
        setTrendForecast(null);
        setTrendError(response.data.error || 'Trend forecast unavailable');
      }
    } catch (err) {
      setTrendForecast(null);
      setTrendError(err?.response?.data?.error || 'Unable to load prediction trend.');
    } finally {
      setTrendLoading(false);
    }
  }, [token, selected, intervalDays, intervalHours, backtrack]);

  useEffect(() => {
    loadGeneralInsights();
  }, [loadGeneralInsights]);

  useEffect(() => {
    loadTrendForecast();
  }, [loadTrendForecast]);

  const loadAccuracyMetrics = async () => {
    try {
      const response = await axios.get('/api/insights/accuracy', {
        timeout: 30000, // 30 seconds for accuracy metrics
      });
      if (response.data.success) {
        // Backend returns { success: true, data: metrics }
        setAccuracyMetrics(response.data.data);
      } else {
        console.error('[Accuracy] API returned unsuccessful response:', response.data);
        setAccuracyMetrics(null);
      }
    } catch (err) {
      console.error('[Accuracy] Failed to load accuracy metrics:', err);
      if (err?.isTimeout) {
        console.warn('[Accuracy] Request timed out - this is normal if evaluation is running');
      }
      setAccuracyMetrics(null);
    }
  };

  const fetchLivePrice = async (coinId, signal, silent = false, retryCount = 0) => {
    if (!coinId) return;

    if (!silent) {
      setLivePriceLoading(true);
      setLivePriceError(null);
    }

    try {
      const response = await axios.get('https://api.coingecko.com/api/v3/simple/price', {
        params: {
          ids: coinId,
          vs_currencies: 'usd',
          include_24hr_change: true,
          include_last_updated_at: true,
        },
        timeout: 20000, // Increased timeout
        signal,
      });

      const raw = response.data?.[coinId];

      if (!raw || typeof raw.usd !== 'number') {
        // Retry once if data format is wrong
        if (retryCount === 0) {
          setTimeout(() => fetchLivePrice(coinId, signal, silent, 1), 2000);
          return;
        }
        throw new Error('Price data unavailable');
      }

      setLivePrice({
        value: raw.usd,
        change24h: raw.usd_24h_change ?? null,
        updatedAt: raw.last_updated_at ? new Date(raw.last_updated_at * 1000) : new Date(),
      });
      setLivePriceError(null);
    } catch (err) {
      if (err.code === 'ERR_CANCELED') {
        return;
      }
      
      // Retry logic for network errors
      const isNetworkError = !err.response || err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT';
      if (isNetworkError && retryCount < 2) {
        console.log(`[Prediction] Retrying live price fetch (attempt ${retryCount + 1}/2)...`);
        setTimeout(() => fetchLivePrice(coinId, signal, silent, retryCount + 1), 2000);
        return;
      }
      
      console.error('[Prediction] Live price fetch failed:', err?.response?.data || err.message || err);
      // Don't show error for temporary network issues - just log it
      if (!isNetworkError) {
        setLivePriceError('Unable to load live price.');
      } else {
        // For network errors, don't show error - price will update on next poll
        setLivePriceError(null);
      }
      // Don't clear live price on error - keep showing last successful price
    } finally {
      if (!silent) {
        setLivePriceLoading(false);
      }
    }
  };

  const fetchHistoricalPerformance = async (coinId, days, signal, retryCount = 0) => {
    if (!coinId) return;

    const requestedDays = Math.max(1, Math.min(90, Number.isFinite(days) ? days : 1));
    setHistoricalLoading(true);
    setHistoricalError(null);

    try {
      const response = await axios.get(
        `https://api.coingecko.com/api/v3/coins/${encodeURIComponent(coinId)}/market_chart`,
        {
          params: {
            vs_currency: 'usd',
            days: requestedDays,
            interval: requestedDays <= 7 ? 'hourly' : 'daily',
          },
          timeout: 30000, // Increased timeout for backtracking
          signal
        }
      );

      const prices = Array.isArray(response.data?.prices) ? response.data.prices : [];

      if (!prices.length) {
        // Retry once if no data but request succeeded
        if (retryCount === 0) {
          setTimeout(() => fetchHistoricalPerformance(coinId, days, signal, 1), 2000);
          return;
        }
        setHistoricalData([]);
        setHistoricalError('No historical data available.');
        return;
      }

      const sorted = prices
        .map(([timestamp, price]) => ({ timestamp, price }))
        .sort((a, b) => a.timestamp - b.timestamp);

      const byDate = new Map();
      sorted.forEach(({ timestamp, price }) => {
        const dateKey = new Date(timestamp).toISOString().split('T')[0];
        byDate.set(dateKey, { timestamp, price });
      });

      const ascending = Array.from(byDate.values());
      const limited = ascending.slice(-requestedDays);

      const dateFormatter = new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
      const currencyFormatter = new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 2
      });
      const percentFormatter = new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });

      const processed = limited.map((entry, index) => {
        const previous = index > 0 ? limited[index - 1] : null;
        const priceChange = previous ? entry.price - previous.price : 0;
        const percentChange =
          previous && previous.price
            ? (priceChange / previous.price) * 100
            : 0;

        const signedPercent = previous
          ? `${percentChange >= 0 ? '+' : '-'}${percentFormatter.format(
              Math.abs(percentChange)
            )}%`
          : 'N/A';
        const signedPrice = previous
          ? `${priceChange >= 0 ? '+' : '-'}${currencyFormatter.format(
              Math.abs(priceChange)
            )}`
          : 'N/A';

        return {
          date: dateFormatter.format(new Date(entry.timestamp)),
          closePrice: currencyFormatter.format(entry.price),
          sensitivity:
            previous && previous.price ? `${signedPercent} / ${signedPrice}` : 'N/A'
        };
      });

      setHistoricalData(processed.reverse());
      setHistoricalError(null); // Clear any previous errors
    } catch (err) {
      if (err.code === 'ERR_CANCELED') {
        return;
      }
      
      // Retry logic for network errors
      const isNetworkError = !err.response || err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT';
      if (isNetworkError && retryCount < 2) {
        console.log(`[Prediction] Retrying historical data fetch (attempt ${retryCount + 1}/2)...`);
        setTimeout(() => fetchHistoricalPerformance(coinId, days, signal, retryCount + 1), 3000);
        return;
      }
      
      console.error('[Prediction] Historical data fetch failed:', err?.response?.data || err.message || err);
      const status = err?.response?.status;
      if (status === 429) {
        setHistoricalError('Rate limit hit. Please try again in a moment.');
      } else if (status === 404) {
        setHistoricalError('Historical data unavailable for this asset.');
      } else if (status === 400) {
        setHistoricalError('Invalid request. Try a shorter backtracking period.');
      } else if (isNetworkError) {
        setHistoricalError('Network error. Check your connection and try again.');
      } else {
        // Don't show error for temporary API issues - just log it
        console.warn('[Prediction] Historical data temporarily unavailable');
        setHistoricalError(null); // Don't show error to user for temporary issues
      }
      // Don't clear historical data on error - keep showing last successful data
    } finally {
      setHistoricalLoading(false);
    }
  };


  const renderInsightsContent = () => {
    if (!insights) return null;

    // Collect topics from all possible sources
    const topicHighlights = [];
    
    // Primary source: topic_insights
    if (Array.isArray(insights.topic_insights)) {
      topicHighlights.push(...insights.topic_insights);
    }
    
    // Secondary source: insights
    if (Array.isArray(insights.insights)) {
      insights.insights.forEach(item => {
        // Only add if not already in topicHighlights
        const exists = topicHighlights.some(t => 
          t.topic_id === item.topic_id || 
          (t.topic_name === item.topic_name && item.topic_name)
        );
        if (!exists) {
          topicHighlights.push(item);
        }
      });
    }
    
    // Check summary for topics
    const meta = insights.meta || insights.summary || {};
    if (Array.isArray(meta.topic_insights)) {
      meta.topic_insights.forEach(item => {
        const exists = topicHighlights.some(t => 
          t.topic_id === item.topic_id || 
          (t.topic_name === item.topic_name && item.topic_name)
        );
        if (!exists) {
          topicHighlights.push(item);
        }
      });
    }
    
    // Sort by confidence (highest first), then by sentiment score
    topicHighlights.sort((a, b) => {
      const confA = a.confidence || 0;
      const confB = b.confidence || 0;
      if (confB !== confA) return confB - confA;
      const scoreA = Math.abs(a.sentiment_score || a.sentimentScore || 0);
      const scoreB = Math.abs(b.sentiment_score || b.sentimentScore || 0);
      return scoreB - scoreA;
    });

    // Extract average sentiment early for use in Trading Recommendation
    let avgSentiment = meta.avg_sentiment ?? meta.average_sentiment ?? null;

    const windowMeta = insights.window || meta.window || {};
    const distribution = meta.overall_sentiment_distribution || meta.sentiment_distribution || {};
    const ratios = meta.overall_sentiment_ratio || meta.sentiment_ratio || {};
    const trend = meta.sentiment_trend || meta.trend || insights.trend || 'stable';
    const totalDocs = meta.total_documents ?? meta.documents ?? insights.documents ?? null;
    let reportText = typeof insights.report === 'string' ? insights.report.trim() : '';
    
    // Remove TOPIC-SENTIMENT INSIGHTS section from summary report (it's displayed separately above)
    if (reportText) {
      const lines = reportText.split('\n');
      const filteredLines = [];
      let skipSection = false;
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const upperLine = line.toUpperCase().trim();
        
        // Detect start of TOPIC-SENTIMENT INSIGHTS section
        if ((upperLine.includes('TOPIC') && upperLine.includes('SENTIMENT') && upperLine.includes('INSIGHTS')) ||
            upperLine === 'TOPIC-SENTIMENT INSIGHTS' ||
            upperLine === 'TOPIC SENTIMENT INSIGHTS') {
          skipSection = true;
          continue;
        }
        
        // If we're skipping the topic section, look for the end
        if (skipSection) {
          // Stop skipping when we hit the next major section
          // Common next sections: SENTIMENT DISTRIBUTION, KEY OBSERVATIONS, etc.
          if (upperLine.includes('SENTIMENT DISTRIBUTION') ||
              upperLine.includes('KEY OBSERVATIONS') ||
              upperLine.includes('PIPELINE STATISTICS') ||
              (upperLine.startsWith('===') && upperLine.length > 10) ||
              (upperLine.startsWith('---') && upperLine.length > 10)) {
            // Make sure it's not still part of topic section
            if (!upperLine.includes('TOPIC') && !upperLine.includes('SENTIMENT INSIGHTS')) {
              skipSection = false;
              // Include this line as it's the start of the next section
              filteredLines.push(line);
              continue;
            }
          }
          
          // Skip all lines in the topic section
          continue;
        }
        
        filteredLines.push(line);
      }
      
      reportText = filteredLines.join('\n').trim();
    }
    
    const dailyInsights = Array.isArray(insights.daily_insights) ? insights.daily_insights : [];
    const dailySummary = insights.daily_summary || {};
    const dailyDistribution = dailySummary.sentiment_distribution || {};

    const hasWindowDetails = windowMeta.start || windowMeta.end || totalDocs !== null;

    // Extract volatility data from insights
    const riskInsights = Array.isArray(insights.insights) 
      ? insights.insights.filter(i => i.type === 'risk')
      : [];
    const riskData = riskInsights.length > 0 ? riskInsights[0].supporting_data : null;
    const volatilityMetrics = riskData?.volatility_metrics || {};
    const overallRiskLevel = riskData?.overall_risk_level || 'low';
    const riskEmoji = riskData?.risk_emoji || '✅';
    const beginnerRiskInsight = riskInsights.length > 0 ? riskInsights[0].beginner_friendly_insight : null;


    return (
      <div className="insights-content" style={{ display: 'grid', gap: '1rem' }}>
        {/* Beginner Mode Toggle */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '1rem',
          background: 'rgba(15, 23, 42, 0.6)',
          borderRadius: 12,
          border: '2px solid rgba(59, 130, 246, 0.3)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.1rem' }}>🎓</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: '1rem' }}>Beginner Mode</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)' }}>
                {beginnerMode ? 'Simplified explanations enabled' : 'Technical details shown'}
              </div>
            </div>
          </div>
          <button
            onClick={() => setBeginnerMode(!beginnerMode)}
            style={{
              padding: '0.5rem 1.25rem',
              background: beginnerMode ? 'rgba(34, 197, 94, 0.2)' : 'rgba(59, 130, 246, 0.2)',
              border: `2px solid ${beginnerMode ? '#22c55e' : '#3b82f6'}`,
              borderRadius: 8,
              color: beginnerMode ? '#22c55e' : '#3b82f6',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.9rem',
              transition: 'all 0.2s ease'
            }}
          >
            {beginnerMode ? '✓ Enabled' : 'Enable'}
          </button>
        </div>

        {/* Enhanced Volatility Display */}
        {volatilityMetrics && Object.keys(volatilityMetrics).length > 0 && (
          <div className="content-panel" style={{
            background: overallRiskLevel === 'high' 
              ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)'
              : overallRiskLevel === 'medium'
              ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)'
              : 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)',
            borderRadius: 16,
            padding: '1.5rem',
            border: `2px solid ${
              overallRiskLevel === 'high' ? 'rgba(239, 68, 68, 0.4)'
              : overallRiskLevel === 'medium' ? 'rgba(245, 158, 11, 0.4)'
              : 'rgba(34, 197, 94, 0.4)'
            }`,
            boxShadow: `0 8px 16px -4px ${
              overallRiskLevel === 'high' ? 'rgba(239, 68, 68, 0.2)'
              : overallRiskLevel === 'medium' ? 'rgba(245, 158, 11, 0.2)'
              : 'rgba(34, 197, 94, 0.2)'
            }`
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3 className="content-panel__title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.5rem' }}>{riskEmoji}</span>
                Market Risk Assessment
                <Tooltip 
                  id="risk-assessment"
                  text="This shows how uncertain the market is. High risk means prices could swing dramatically. Low risk means more stable conditions."
                  showTooltips={showTooltips}
                  setShowTooltips={setShowTooltips}
                >
                  <span></span>
                </Tooltip>
              </h3>
              <div style={{
                padding: '0.5rem 1rem',
                background: overallRiskLevel === 'high' 
                  ? 'rgba(239, 68, 68, 0.2)'
                  : overallRiskLevel === 'medium'
                  ? 'rgba(245, 158, 11, 0.2)'
                  : 'rgba(34, 197, 94, 0.2)',
                border: `2px solid ${
                  overallRiskLevel === 'high' ? '#ef4444'
                  : overallRiskLevel === 'medium' ? '#f59e0b'
                  : '#22c55e'
                }`,
                borderRadius: 8,
                fontWeight: 700,
                textTransform: 'uppercase',
                fontSize: '0.85rem',
                color: overallRiskLevel === 'high' ? '#ef4444'
                  : overallRiskLevel === 'medium' ? '#f59e0b'
                  : '#22c55e'
              }}>
                {overallRiskLevel === 'high' ? '⚠️ High Risk' : overallRiskLevel === 'medium' ? '⚡ Medium Risk' : '✅ Low Risk'}
              </div>
            </div>

            {beginnerMode && beginnerRiskInsight && (
              <div style={{
                padding: '1rem',
                background: 'rgba(15, 23, 42, 0.6)',
                borderRadius: 10,
                marginBottom: '1rem',
                border: '1px solid rgba(59, 130, 246, 0.3)'
              }}>
                <div style={{ fontSize: '0.95rem', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {beginnerRiskInsight}
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              {/* Sentiment Confidence Volatility */}
              {volatilityMetrics.sentiment_confidence && (
                <div style={{
                  padding: '1rem',
                  background: 'rgba(15, 23, 42, 0.5)',
                  borderRadius: 10,
                  border: '1px solid rgba(59, 130, 246, 0.3)'
                }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    Sentiment Confidence
                    <Tooltip 
                      id="sentiment-volatility"
                      text="How much the confidence in sentiment predictions varies. Higher values mean less reliable predictions."
                      showTooltips={showTooltips}
                      setShowTooltips={setShowTooltips}
                    >
                      <span></span>
                    </Tooltip>
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                    {(volatilityMetrics.sentiment_confidence.std * 100).toFixed(1)}%
                  </div>
                  {beginnerMode && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
                      {volatilityMetrics.sentiment_confidence.std > 0.3 
                        ? 'High variation - predictions less reliable'
                        : volatilityMetrics.sentiment_confidence.std > 0.2
                        ? 'Moderate variation'
                        : 'Low variation - predictions more reliable'}
                    </div>
                  )}
                </div>
              )}

              {/* Price Volatility */}
              {volatilityMetrics.price && (
                <div style={{
                  padding: '1rem',
                  background: 'rgba(15, 23, 42, 0.5)',
                  borderRadius: 10,
                  border: '1px solid rgba(59, 130, 246, 0.3)'
                }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    Price Volatility
                    <Tooltip 
                      id="price-volatility"
                      text="How much cryptocurrency prices are moving up and down. Higher values mean bigger price swings."
                      showTooltips={showTooltips}
                      setShowTooltips={setShowTooltips}
                    >
                      <span></span>
                    </Tooltip>
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                    {(volatilityMetrics.price.std * 100).toFixed(1)}%
                  </div>
                  {beginnerMode && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
                      {volatilityMetrics.price.std > 0.05 
                        ? 'High price swings - very volatile'
                        : volatilityMetrics.price.std > 0.02
                        ? 'Moderate price movement'
                        : 'Stable prices'}
                    </div>
                  )}
                </div>
              )}

              {/* Trend Prediction Volatility */}
              {volatilityMetrics.trend_prediction && (
                <div style={{
                  padding: '1rem',
                  background: 'rgba(15, 23, 42, 0.5)',
                  borderRadius: 10,
                  border: '1px solid rgba(59, 130, 246, 0.3)'
                }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    Trend Prediction Uncertainty
                    <Tooltip 
                      id="trend-volatility"
                      text="How confident the system is about price direction predictions. Higher values mean less certainty about up/down/neutral trends."
                      showTooltips={showTooltips}
                      setShowTooltips={setShowTooltips}
                    >
                      <span></span>
                    </Tooltip>
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                    {(volatilityMetrics.trend_prediction.std * 100).toFixed(1)}%
                  </div>
                  {beginnerMode && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
                      {volatilityMetrics.trend_prediction.std > 0.3 
                        ? 'High uncertainty - trends unclear'
                        : volatilityMetrics.trend_prediction.std > 0.2
                        ? 'Moderate uncertainty'
                        : 'Low uncertainty - trends clearer'}
                    </div>
                  )}
                </div>
              )}

              {/* Signal Alignment Volatility */}
              {volatilityMetrics.signal_alignment && (
                <div style={{
                  padding: '1rem',
                  background: 'rgba(15, 23, 42, 0.5)',
                  borderRadius: 10,
                  border: '1px solid rgba(59, 130, 246, 0.3)'
                }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    Signal Conflicts
                    <Tooltip 
                      id="signal-alignment"
                      text="How often sentiment and price trend predictions disagree. Higher values mean mixed signals (e.g., positive sentiment but down trend)."
                      showTooltips={showTooltips}
                      setShowTooltips={setShowTooltips}
                    >
                      <span></span>
                    </Tooltip>
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                    {(volatilityMetrics.signal_alignment.conflict_rate * 100).toFixed(0)}%
                  </div>
                  {beginnerMode && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
                      {volatilityMetrics.signal_alignment.conflict_rate > 0.4 
                        ? 'Many conflicts - mixed signals'
                        : volatilityMetrics.signal_alignment.conflict_rate > 0.25
                        ? 'Some conflicts'
                        : 'Signals mostly agree'}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Time Window Info - Show First */}
        {hasWindowDetails && (
          <div className="metric-card metric-card--neutral" style={{ display: 'grid', gap: '0.35rem' }}>
            <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-subtle)' }}>
              Time window
              <Tooltip 
                id="time-window"
                text="The date range of data analyzed for these insights."
                showTooltips={showTooltips}
                setShowTooltips={setShowTooltips}
              >
                <span></span>
              </Tooltip>
            </div>
            <div style={{ fontWeight: 600 }}>
              {windowMeta.start ? new Date(windowMeta.start).toLocaleString() : '—'} →{' '}
              {windowMeta.end ? new Date(windowMeta.end).toLocaleString() : '—'}
            </div>
            <div style={{ color: 'var(--text-subtle)', fontSize: '0.9rem' }}>
              Asset focus: {windowMeta.asset || meta.asset || dailySummary.asset || 'ALL'} · Span:{' '}
              {windowMeta.span_hours ? windowMeta.span_hours.toFixed(1) : dailySummary.span_hours ? Number(dailySummary.span_hours).toFixed(1) : '—'} hrs ·
              Documents: {totalDocs ?? dailySummary.total_documents ?? '0'} · Days: {dailySummary.dates ?? '—'}
            </div>
            <div style={{ color: trend === 'improving' ? '#22c55e' : trend === 'declining' ? '#f97316' : 'var(--text-subtle)' }}>
              Sentiment trend: {String(trend).charAt(0).toUpperCase() + String(trend).slice(1)}
              <Tooltip 
                id="sentiment-trend"
                text="Whether overall sentiment is improving (getting more positive), declining (getting more negative), or stable."
                showTooltips={showTooltips}
                setShowTooltips={setShowTooltips}
              >
                <span></span>
              </Tooltip>
            </div>
          </div>
        )}

        {/* Trading Recommendation - Fun and Engaging */}
        {(() => {
          // Get trend forecast label
          const trendLabel = trendForecast?.label || null;
          const trendConfidence = trendForecast?.confidence || 0;
          
          // Get average sentiment
          const sentiment = avgSentiment !== null ? avgSentiment : (meta?.avg_sentiment !== undefined ? meta.avg_sentiment : null);
          
          // Generate recommendation
          let recommendation = 'HOLD';
          let recommendationColor = '#f59e0b';
          let recommendationEmoji = '⏸️';
          let recommendationReason = 'Monitoring market conditions';
          let recommendationStrength = 'moderate';
          
          if (trendLabel && sentiment !== null) {
            const isPositiveSentiment = sentiment > 0.3;
            const isNegativeSentiment = sentiment < -0.3;
            const isNeutralSentiment = sentiment >= -0.3 && sentiment <= 0.3;
            const isVeryPositive = sentiment > 0.7;
            const isVeryNegative = sentiment < -0.7;
            
            if (trendLabel === 'up' && (isPositiveSentiment || isVeryPositive)) {
              recommendation = 'BUY';
              recommendationColor = '#22c55e';
              recommendationEmoji = '🚀';
              recommendationReason = 'Strong upward trend with positive sentiment';
              recommendationStrength = isVeryPositive ? 'strong' : 'moderate';
            } else if (trendLabel === 'up' && isNeutralSentiment) {
              recommendation = 'BUY';
              recommendationColor = '#22c55e';
              recommendationEmoji = '📈';
              recommendationReason = 'Upward trend detected, neutral sentiment';
              recommendationStrength = 'moderate';
            } else if (trendLabel === 'down' && (isNegativeSentiment || isVeryNegative)) {
              recommendation = 'SELL';
              recommendationColor = '#ef4444';
              recommendationEmoji = '📉';
              recommendationReason = 'Downward trend with negative sentiment';
              recommendationStrength = isVeryNegative ? 'strong' : 'moderate';
            } else if (trendLabel === 'down' && isNeutralSentiment) {
              recommendation = 'SELL';
              recommendationColor = '#f97316';
              recommendationEmoji = '⚠️';
              recommendationReason = 'Downward trend detected, neutral sentiment';
              recommendationStrength = 'moderate';
            } else if (trendLabel === 'neutral' && isVeryPositive) {
              recommendation = 'BUY';
              recommendationColor = '#22c55e';
              recommendationEmoji = '💚';
              recommendationReason = 'Very positive sentiment despite neutral trend';
              recommendationStrength = 'moderate';
            } else if (trendLabel === 'neutral' && isVeryNegative) {
              recommendation = 'SELL';
              recommendationColor = '#ef4444';
              recommendationEmoji = '🔴';
              recommendationReason = 'Very negative sentiment despite neutral trend';
              recommendationStrength = 'moderate';
            } else {
              recommendation = 'HOLD';
              recommendationColor = '#f59e0b';
              recommendationEmoji = '⏸️';
              recommendationReason = 'Mixed signals - monitoring market conditions';
              recommendationStrength = 'moderate';
            }
          } else if (trendLabel) {
            // Only trend available
            if (trendLabel === 'up') {
              recommendation = 'BUY';
              recommendationColor = '#22c55e';
              recommendationEmoji = '📈';
              recommendationReason = 'Upward trend detected';
              recommendationStrength = 'moderate';
            } else if (trendLabel === 'down') {
              recommendation = 'SELL';
              recommendationColor = '#ef4444';
              recommendationEmoji = '📉';
              recommendationReason = 'Downward trend detected';
              recommendationStrength = 'moderate';
            }
          } else if (sentiment !== null) {
            // Only sentiment available
            if (sentiment > 0.5) {
              recommendation = 'BUY';
              recommendationColor = '#22c55e';
              recommendationEmoji = '💚';
              recommendationReason = 'Strong positive sentiment';
              recommendationStrength = 'moderate';
            } else if (sentiment < -0.5) {
              recommendation = 'SELL';
              recommendationColor = '#ef4444';
              recommendationEmoji = '🔴';
              recommendationReason = 'Strong negative sentiment';
              recommendationStrength = 'moderate';
            }
          }
          
          return (
            <div className="content-panel" style={{
              background: `linear-gradient(135deg, ${recommendationColor}15 0%, rgba(15, 23, 42, 0.8) 100%)`,
              borderRadius: 20,
              padding: '2rem',
              border: `3px solid ${recommendationColor}40`,
              boxShadow: `0 12px 32px -8px ${recommendationColor}30, 0 4px 16px -4px rgba(0, 0, 0, 0.3)`,
              position: 'relative',
              overflow: 'hidden',
              marginBottom: '1.5rem'
            }}>
              {/* Animated background effect */}
              <div style={{
                position: 'absolute',
                top: '-50%',
                right: '-50%',
                width: '200%',
                height: '200%',
                background: `radial-gradient(circle, ${recommendationColor}10 0%, transparent 70%)`,
                animation: 'pulse 3s ease-in-out infinite',
                pointerEvents: 'none'
              }} />
              
              <div style={{ position: 'relative', zIndex: 1 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '1.5rem',
                  flexWrap: 'wrap',
                  gap: '1rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{
                      fontSize: '3.5rem',
                      lineHeight: 1,
                      filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3))',
                      animation: 'bounce 2s ease-in-out infinite'
                    }}>
                      {recommendationEmoji}
                    </div>
                    <div>
                      <div style={{
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: 'var(--text-subtle)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em',
                        marginBottom: '0.25rem'
                      }}>
                        Trading Recommendation
                      </div>
                      <div style={{
                        fontSize: '2.5rem',
                        fontWeight: 800,
                        color: recommendationColor,
                        textShadow: `0 2px 8px ${recommendationColor}40`,
                        letterSpacing: '0.05em'
                      }}>
                        {recommendation}
                      </div>
                    </div>
                  </div>
                  
                  <div style={{
                    padding: '0.75rem 1.25rem',
                    background: `${recommendationColor}20`,
                    border: `2px solid ${recommendationColor}40`,
                    borderRadius: 12,
                    textAlign: 'center'
                  }}>
                    <div style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-subtle)',
                      marginBottom: '0.25rem'
                    }}>
                      Strength
                    </div>
                    <div style={{
                      fontSize: '1rem',
                      fontWeight: 700,
                      color: recommendationColor,
                      textTransform: 'capitalize'
                    }}>
                      {recommendationStrength}
                    </div>
                  </div>
                </div>
                
                <div style={{
                  padding: '1.25rem',
                  background: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: 12,
                  border: `1px solid ${recommendationColor}30`,
                  marginBottom: '1.25rem'
                }}>
                  <div style={{
                    fontSize: '1rem',
                    color: 'var(--text-primary)',
                    lineHeight: 1.6,
                    fontWeight: 500
                  }}>
                    💡 <strong>Why {recommendation}?</strong> {recommendationReason}
                  </div>
                </div>
                
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '1rem'
                }}>
                  {trendLabel && (
                    <div style={{
                      padding: '1rem',
                      background: 'rgba(15, 23, 42, 0.5)',
                      borderRadius: 10,
                      border: '1px solid rgba(59, 130, 246, 0.3)'
                    }}>
                      <div style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-subtle)',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                      }}>
                        Trend Forecast
                      </div>
                      <div style={{
                        fontSize: '1.25rem',
                        fontWeight: 700,
                        color: trendLabel === 'up' ? '#22c55e' : trendLabel === 'down' ? '#ef4444' : 'var(--text-primary)',
                        textTransform: 'uppercase',
                        marginBottom: '0.25rem'
                      }}>
                        {trendLabel}
                      </div>
                      {trendConfidence > 0 && (
                        <div style={{
                          fontSize: '0.85rem',
                          color: 'var(--text-subtle)'
                        }}>
                          Confidence: {(trendConfidence * 100).toFixed(1)}%
                        </div>
                      )}
                    </div>
                  )}
                  
                  {sentiment !== null && (
                    <div style={{
                      padding: '1rem',
                      background: 'rgba(15, 23, 42, 0.5)',
                      borderRadius: 10,
                      border: '1px solid rgba(59, 130, 246, 0.3)'
                    }}>
                      <div style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-subtle)',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                      }}>
                        Average Sentiment
                      </div>
                      <div style={{
                        fontSize: '1.25rem',
                        fontWeight: 700,
                        color: sentiment > 0.3 ? '#22c55e' : sentiment < -0.3 ? '#ef4444' : 'var(--text-primary)',
                        marginBottom: '0.25rem'
                      }}>
                        {sentiment > 0.3 ? 'Positive' : sentiment < -0.3 ? 'Negative' : 'Neutral'}
                      </div>
                      <div style={{
                        fontSize: '0.85rem',
                        color: 'var(--text-subtle)'
                      }}>
                        Score: {sentiment.toFixed(3)}
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Beginner-Friendly Explanation Section */}
                <div style={{
                  marginTop: '1.25rem',
                  padding: '1.5rem',
                  background: 'rgba(15, 23, 42, 0.7)',
                  borderRadius: 12,
                  border: `2px solid ${recommendationColor}30`
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    marginBottom: '1rem',
                    fontSize: '1.1rem',
                    fontWeight: 600
                  }}>
                    <span>💡</span>
                    <span>What This Means for You:</span>
                  </div>
                  
                  {recommendation === 'BUY' && (
                    <div>
                      <p style={{ marginBottom: '0.75rem', lineHeight: 1.6 }}>
                        ✅ <strong>Good time to consider buying:</strong>
                      </p>
                      <ul style={{ marginLeft: '1.5rem', marginBottom: '0.75rem', lineHeight: 1.8 }}>
                        <li>Market sentiment is positive (people are optimistic)</li>
                        <li>Price trend is predicted to go up</li>
                        <li>Both signals agree (high confidence)</li>
                      </ul>
                      <div style={{
                        padding: '0.75rem',
                        background: 'rgba(34, 197, 94, 0.15)',
                        borderRadius: 8,
                        fontSize: '0.85rem',
                        fontStyle: 'italic',
                        border: '1px solid rgba(34, 197, 94, 0.3)'
                      }}>
                        💡 <strong>Beginner Tip:</strong> Start with a small amount. Never invest more than you can afford to lose. Cryptocurrency is risky, and prices can go down even when predictions are positive.
                      </div>
                    </div>
                  )}
                  
                  {recommendation === 'SELL' && (
                    <div>
                      <p style={{ marginBottom: '0.75rem', lineHeight: 1.6 }}>
                        ⚠️ <strong>Consider selling or reducing position:</strong>
                      </p>
                      <ul style={{ marginLeft: '1.5rem', marginBottom: '0.75rem', lineHeight: 1.8 }}>
                        <li>Market sentiment is negative (people are worried)</li>
                        <li>Price trend is predicted to go down</li>
                        <li>Both signals agree (high confidence)</li>
                      </ul>
                      <div style={{
                        padding: '0.75rem',
                        background: 'rgba(239, 68, 68, 0.15)',
                        borderRadius: 8,
                        fontSize: '0.85rem',
                        fontStyle: 'italic',
                        border: '1px solid rgba(239, 68, 68, 0.3)'
                      }}>
                        💡 <strong>Beginner Tip:</strong> Don't panic sell. Consider your investment goals and risk tolerance. If you're unsure, it's okay to wait and watch. Always do your own research.
                      </div>
                    </div>
                  )}
                  
                  {recommendation === 'HOLD' && (
                    <div>
                      <p style={{ marginBottom: '0.75rem', lineHeight: 1.6 }}>
                        ⏸️ <strong>Wait and watch:</strong>
                      </p>
                      <ul style={{ marginLeft: '1.5rem', marginBottom: '0.75rem', lineHeight: 1.8 }}>
                        <li>Market signals are mixed or unclear</li>
                        <li>Not enough data for a clear direction</li>
                        <li>Better to wait for clearer signals</li>
                      </ul>
                      <div style={{
                        padding: '0.75rem',
                        background: 'rgba(245, 158, 11, 0.15)',
                        borderRadius: 8,
                        fontSize: '0.85rem',
                        fontStyle: 'italic',
                        border: '1px solid rgba(245, 158, 11, 0.3)'
                      }}>
                        💡 <strong>Beginner Tip:</strong> When in doubt, wait. It's better to miss an opportunity than to make a bad decision. Use this time to learn more about the market.
                      </div>
                    </div>
                  )}
                </div>
                
                <div style={{
                  marginTop: '1rem',
                  padding: '1rem',
                  background: `${recommendationColor}10`,
                  border: `1px dashed ${recommendationColor}40`,
                  borderRadius: 10,
                  fontSize: '0.85rem',
                  color: 'var(--text-subtle)',
                  fontStyle: 'italic',
                  textAlign: 'center'
                }}>
                  ⚠️ This recommendation is based on analysis and market sentiment. Always conduct your own research and consider risk management before making trading decisions. Never invest more than you can afford to lose.
                </div>
              </div>
            </div>
          );
        })()}

        {/* Topic Sentiment Insights - Fun and Engaging Display */}
        {topicHighlights.length > 0 && (
          <div className="content-panel" style={{ 
            background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(15, 23, 42, 0.6) 100%)', 
            borderRadius: 16, 
            padding: '1.5rem 1.75rem',
            border: '2px solid rgba(59, 130, 246, 0.3)',
            boxShadow: '0 8px 16px -4px rgba(59, 130, 246, 0.2)',
            display: 'grid',
            gap: '1.25rem'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.75rem',
              marginBottom: '0.5rem'
            }}>
              <div style={{
                width: '5px',
                height: '40px',
                background: 'linear-gradient(180deg, #3b82f6 0%, #1d4ed8 100%)',
                borderRadius: '3px',
                boxShadow: '0 2px 8px rgba(59, 130, 246, 0.4)'
              }} />
              <div style={{ flex: 1 }}>
                <h3 className="content-panel__title" style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>
                  🎯 Topic Sentiment Insights
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                    All {topicHighlights.length} key theme{topicHighlights.length !== 1 ? 's' : ''} driving market sentiment
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span style={{
                      padding: '0.2rem 0.6rem',
                      borderRadius: '12px',
                      background: 'rgba(59, 130, 246, 0.2)',
                      border: '1px solid rgba(59, 130, 246, 0.4)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#3b82f6'
                    }}>
                      LDA
                    </span>
                    <span style={{
                      padding: '0.2rem 0.6rem',
                      borderRadius: '12px',
                      background: 'rgba(34, 197, 94, 0.2)',
                      border: '1px solid rgba(34, 197, 94, 0.4)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#22c55e'
                    }}>
                      BERTopic
                    </span>
                  </div>
                </div>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-subtle)', fontStyle: 'italic' }}>
                  Topics extracted from MongoDB data using LDA & BERTopic models
                </p>
              </div>
            </div>
            
            <div style={{ display: 'grid', gap: '1rem' }}>
              {topicHighlights.map((item, idx) => {
                const sentimentLabel = item.sentiment_label || item.sentimentLabel || 'neutral';
                const sentimentScore = item.sentiment_score || item.sentimentScore || 0;
                const confidence = item.confidence || 0;
                
                // Determine colors and emoji based on sentiment
                let sentimentColor, sentimentBg, sentimentEmoji, sentimentGradient;
                if (sentimentLabel.toLowerCase() === 'positive' || sentimentScore > 0.3) {
                  sentimentColor = '#22c55e';
                  sentimentBg = 'rgba(34, 197, 94, 0.15)';
                  sentimentEmoji = '📈';
                  sentimentGradient = 'linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(34, 197, 94, 0.05) 100%)';
                } else if (sentimentLabel.toLowerCase() === 'negative' || sentimentScore < -0.3) {
                  sentimentColor = '#f87171';
                  sentimentBg = 'rgba(248, 113, 113, 0.15)';
                  sentimentEmoji = '📉';
                  sentimentGradient = 'linear-gradient(135deg, rgba(248, 113, 113, 0.2) 0%, rgba(248, 113, 113, 0.05) 100%)';
                } else {
                  sentimentColor = '#94a3b8';
                  sentimentBg = 'rgba(148, 163, 184, 0.15)';
                  sentimentEmoji = '➡️';
                  sentimentGradient = 'linear-gradient(135deg, rgba(148, 163, 184, 0.2) 0%, rgba(148, 163, 184, 0.05) 100%)';
                }
                
                const topicName = item.topic_name || item.title || `Topic ${idx + 1}`;
                const topicWords = item.topic_words || item.keywords || [];
                const docCount = item.doc_count || item.docCount || 0;
                const sentimentStrength = item.sentiment_strength || item.sentimentStrength || 'moderate';
                
                // Get full explanation - prioritize beginner-friendly version if in beginner mode
                let insightText = beginnerMode && item.beginner_friendly_insight
                  ? item.beginner_friendly_insight
                  : item.insight_text || item.description || item.summary || item.text || '';
                
                // If we have multiple sources and not in beginner mode, combine them for fuller understanding
                if (!beginnerMode) {
                  const additionalInfo = [];
                  if (item.description && item.description !== insightText) {
                    additionalInfo.push(item.description);
                  }
                  if (item.summary && item.summary !== insightText && !additionalInfo.includes(item.summary)) {
                    additionalInfo.push(item.summary);
                  }
                  
                  // Combine all explanations for fuller understanding
                  if (additionalInfo.length > 0) {
                    insightText = [insightText, ...additionalInfo].filter(Boolean).join(' ');
                  }
                }
                
                // If still no insight, provide a default based on topic words
                if (!insightText || insightText.trim() === 'No insight available.') {
                  if (beginnerMode) {
                    const wordsStr = topicWords.length > 0 ? topicWords.slice(0, 3).join(', ') : 'various themes';
                    if (sentimentLabel === 'positive') {
                      insightText = `Good news! People are talking positively about ${wordsStr}. This usually means prices might go up because people are optimistic.`;
                    } else if (sentimentLabel === 'negative') {
                      insightText = `Warning: People are talking negatively about ${wordsStr}. This might cause prices to go down because people are worried.`;
                    } else {
                      insightText = `People are talking about ${wordsStr}, but the sentiment is neutral. This means prices might stay relatively stable.`;
                    }
                  } else {
                    const wordsStr = topicWords.length > 0 ? topicWords.slice(0, 3).join(', ') : 'various themes';
                    insightText = `This topic focuses on ${wordsStr}. The sentiment analysis indicates ${sentimentLabel} sentiment (${sentimentScore > 0 ? '+' : ''}${sentimentScore.toFixed(2)}), suggesting ${sentimentLabel === 'positive' ? 'optimistic' : sentimentLabel === 'negative' ? 'concerned' : 'neutral'} market views on these themes.`;
                  }
                }
                
                return (
                  <div
                    key={`topic-${item.topic_id ?? idx}-${topicName}`}
                    style={{
                      background: sentimentGradient,
                      borderRadius: 12,
                      padding: '1.25rem',
                      border: `2px solid ${sentimentColor}40`,
                      boxShadow: `0 4px 12px -2px ${sentimentColor}20`,
                      display: 'grid',
                      gap: '0.75rem',
                      transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                  >
                    {/* Decorative corner accent */}
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      right: 0,
                      width: '60px',
                      height: '60px',
                      background: `radial-gradient(circle, ${sentimentColor}20 0%, transparent 70%)`,
                      borderRadius: '0 0 0 100%'
                    }} />
                    
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', position: 'relative', zIndex: 1 }}>
                      <div style={{
                        fontSize: '2rem',
                        lineHeight: 1,
                        filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))'
                      }}>
                        {sentimentEmoji}
                      </div>
                      <div style={{ flex: 1, display: 'grid', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                          <span style={{
                            fontSize: '1.1rem',
                            fontWeight: 700,
                            color: sentimentColor,
                            minWidth: '2rem',
                            textAlign: 'right'
                          }}>
                            {idx + 1}.
                          </span>
                          <h4 style={{ 
                            margin: 0, 
                            fontSize: '1.15rem', 
                            fontWeight: 700,
                            color: 'var(--text-primary)',
                            textShadow: '0 1px 2px rgba(0,0,0,0.1)',
                            flex: 1
                          }}>
                            {topicName}
                          </h4>
                          <div style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            padding: '0.25rem 0.65rem',
                            borderRadius: '20px',
                            background: sentimentBg,
                            border: `1px solid ${sentimentColor}40`,
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            color: sentimentColor
                          }}>
                            <span style={{ fontSize: '0.7rem' }}>●</span>
                            {sentimentLabel.toUpperCase()}
                          </div>
                          {item.model_source && (
                            <div style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                              padding: '0.2rem 0.5rem',
                              borderRadius: '16px',
                              background: item.model_source === 'BERTopic' 
                                ? 'rgba(34, 197, 94, 0.15)' 
                                : 'rgba(59, 130, 246, 0.15)',
                              border: `1px solid ${item.model_source === 'BERTopic' ? 'rgba(34, 197, 94, 0.4)' : 'rgba(59, 130, 246, 0.4)'}`,
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              color: item.model_source === 'BERTopic' ? '#22c55e' : '#3b82f6'
                            }}>
                              {item.model_source}
                            </div>
                          )}
                        </div>
                        
                        {topicWords.length > 0 && (
                          <div style={{ 
                            display: 'flex', 
                            flexWrap: 'wrap', 
                            gap: '0.4rem',
                            marginTop: '0.25rem'
                          }}>
                            {topicWords.slice(0, 5).map((word, wordIdx) => (
                              <span
                                key={`${idx}-word-${wordIdx}`}
                                style={{
                                  padding: '0.25rem 0.6rem',
                                  borderRadius: '12px',
                                  background: 'rgba(59, 130, 246, 0.15)',
                                  border: '1px solid rgba(59, 130, 246, 0.3)',
                                  fontSize: '0.75rem',
                                  fontWeight: 500,
                                  color: '#3b82f6',
                                  fontStyle: 'italic'
                                }}
                              >
                                {word}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div style={{
                      background: 'rgba(15, 23, 42, 0.5)',
                      borderRadius: 10,
                      padding: '1.1rem 1.25rem',
                      marginTop: '0.75rem',
                      borderLeft: `4px solid ${sentimentColor}`,
                      borderTop: `1px solid ${sentimentColor}30`,
                      position: 'relative',
                      zIndex: 1,
                      boxShadow: `inset 0 1px 3px ${sentimentColor}10`
                    }}>
                      <div style={{
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        color: sentimentColor,
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                      }}>
                        📊 Explanation
                      </div>
                      <p style={{ 
                        margin: 0, 
                        fontSize: '1rem', 
                        lineHeight: 1.7,
                        color: 'var(--text-primary)',
                        fontWeight: 400
                      }}>
                        {insightText}
                      </p>
                    </div>
                    
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      fontSize: '0.85rem',
                      color: 'var(--text-subtle)',
                      marginTop: '0.5rem',
                      paddingTop: '0.75rem',
                      borderTop: `1px solid ${sentimentColor}20`,
                      position: 'relative',
                      zIndex: 1
                    }}>
                      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        <span>
                          Confidence: <strong style={{ color: sentimentColor }}>{(confidence * 100).toFixed(1)}%</strong>
                        </span>
                        {sentimentScore != null && (
                          <span>
                            Sentiment: <strong style={{ color: sentimentColor }}>
                              {sentimentScore > 0 ? '+' : ''}{sentimentScore.toFixed(2)}
                            </strong>
                          </span>
                        )}
                        {docCount > 0 && (
                          <span>
                            Documents: <strong style={{ color: sentimentColor }}>{docCount}</strong>
                          </span>
                        )}
                        {sentimentStrength && (
                          <span>
                            Strength: <strong style={{ color: sentimentColor }}>{sentimentStrength}</strong>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Insights Timeline */}
        {(() => {
          const documentInsights = Array.isArray(insights.document_insights) ? insights.document_insights : [];
          
          if (documentInsights.length > 0) {
            return (
              <div className="content-panel" style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 12, padding: '1rem 1.25rem', display: 'grid', gap: '1rem' }}>
                <h3 className="content-panel__title" style={{ margin: 0 }}>Insights Timeline</h3>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                  {documentInsights.length} article(s) analyzed, sorted chronologically (oldest first)
                </p>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {documentInsights.map((doc, idx) => {
                    const timestamp = doc.timestamp || doc.scraped_at;
                    const formattedDate = timestamp 
                      ? new Date(timestamp).toLocaleString(undefined, { 
                          year: 'numeric', 
                          month: 'short', 
                          day: 'numeric', 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })
                      : `Item ${idx + 1}`;
                    
                    const sentimentScore = doc.sentiment_score;
                    const sentimentLabel = doc.topic_sentiment || 
                      (sentimentScore > 0.3 ? 'POSITIVE' : sentimentScore < -0.3 ? 'NEGATIVE' : 'NEUTRAL');
                    const sentimentColor = sentimentLabel === 'POSITIVE' ? '#22c55e' : 
                                          sentimentLabel === 'NEGATIVE' ? '#f87171' : 'var(--text-subtle)';
                    
                    return (
                      <div
                        key={`doc-${doc.index || idx}`}
                        style={{
                          background: 'rgba(15, 23, 42, 0.45)',
                          borderRadius: 10,
                          padding: '1rem',
                          display: 'grid',
                          gap: '0.75rem',
                          borderLeft: `3px solid ${sentimentColor}`
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                            {formattedDate}
                          </div>
                          {sentimentScore != null && (
                            <div style={{ 
                              fontSize: '0.85rem', 
                              color: sentimentColor,
                              fontWeight: 500
                            }}>
                              {sentimentLabel} ({sentimentScore > 0 ? '+' : ''}{sentimentScore.toFixed(2)})
                            </div>
                          )}
                        </div>
                        
                        {doc.title && (
                          <div style={{ fontWeight: 500, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                            {doc.title}
                          </div>
                        )}
                        
                        {doc.topic_name && (
                          <div style={{ 
                            background: 'rgba(59, 130, 246, 0.15)', 
                            borderRadius: 6, 
                            padding: '0.75rem',
                            display: 'grid',
                            gap: '0.5rem'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span style={{ 
                                fontWeight: 600, 
                                color: '#3b82f6',
                                fontSize: '1.1rem'
                              }}>
                                Topic: {doc.topic_name}
                              </span>
                              {doc.topic_keywords && doc.topic_keywords.length > 0 && (
                                <span style={{ 
                                  fontSize: '0.85rem', 
                                  color: 'var(--text-subtle)',
                                  fontStyle: 'italic'
                                }}>
                                  ({doc.topic_keywords.slice(0, 5).join(', ')})
                                </span>
                              )}
                            </div>
                            {doc.topic_insight && (
                              <div style={{ 
                                fontSize: '1rem', 
                                lineHeight: 1.6,
                                color: 'var(--text-primary)'
                              }}>
                                {doc.topic_insight}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {doc.content && !doc.topic_insight && (
                          <ExpandableContent content={doc.content} title={doc.title} />
                        )}
                        
                        {/* Show full content if available, even if topic_insight exists */}
                        {doc.content && doc.topic_insight && (
                          <ExpandableContent content={doc.content} title={doc.title} />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }
          
          return null;
        })()}

        {/* Summary Report - Clean and Essential Only */}
        {(() => {
          // Extract key metrics from summary
          let numDocs = meta.num_documents ?? totalDocs ?? 0;
          let numTopicsLDA = meta.num_topics_lda ?? 0;
          let numTopicsBERTopic = meta.num_topics_bertopic ?? 0;
          let numInsights = meta.num_insights ?? topicHighlights.length ?? 0;
          
          // Parse report text for pipeline statistics
          let generatedAt = null;
          if (reportText) {
            const generatedMatch = reportText.match(/Generated:\s*([^\n]+)/i);
            if (generatedMatch) {
              generatedAt = generatedMatch[1].trim();
            }
            
            // Extract pipeline statistics from report text
            const docsMatch = reportText.match(/Documents Processed:\s*(\d+)/i);
            if (docsMatch && !numDocs) {
              numDocs = parseInt(docsMatch[1], 10);
            }
            
            const ldaMatch = reportText.match(/LDA Topics Discovered:\s*(\d+)/i);
            if (ldaMatch && !numTopicsLDA) {
              numTopicsLDA = parseInt(ldaMatch[1], 10);
            }
            
            const bertopicMatch = reportText.match(/BERTopic Topics Discovered:\s*(\d+)/i);
            if (bertopicMatch && !numTopicsBERTopic) {
              numTopicsBERTopic = parseInt(bertopicMatch[1], 10);
            }
            
            const sentimentMatch = reportText.match(/Average Sentiment Score:\s*([\d.]+)/i);
            if (sentimentMatch && avgSentiment === null) {
              avgSentiment = parseFloat(sentimentMatch[1]);
            }
            
            const insightsMatch = reportText.match(/Topic Insights Generated:\s*(\d+)/i);
            if (insightsMatch && !numInsights) {
              numInsights = parseInt(insightsMatch[1], 10);
            }
          }
          
          // Only show summary if we have meaningful data
          const hasSummaryData = numDocs > 0 || numTopicsLDA > 0 || numTopicsBERTopic > 0 || avgSentiment !== null;
          
          if (!hasSummaryData && !reportText) {
            return null;
          }
          
          return (
            <div className="content-panel" style={{ 
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.75) 100%)', 
              borderRadius: 16, 
              padding: '1.5rem 1.75rem',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              boxShadow: '0 8px 16px -4px rgba(0, 0, 0, 0.2)'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                marginBottom: '1.5rem',
                paddingBottom: '1rem',
                borderBottom: '2px solid rgba(59, 130, 246, 0.3)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{
                    width: '5px',
                    height: '36px',
                    background: 'linear-gradient(180deg, #3b82f6 0%, #1d4ed8 100%)',
                    borderRadius: '3px',
                    boxShadow: '0 2px 8px rgba(59, 130, 246, 0.4)'
                  }} />
                  <div>
                    <h3 className="content-panel__title" style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700 }}>
                      📊 Analysis Summary
                    </h3>
                    {generatedAt && (
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                        Generated: {generatedAt}
                      </p>
                    )}
                  </div>
                </div>
              </div>
              
              <div style={{ display: 'grid', gap: '1.25rem' }}>
                {/* Key Metrics Grid */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                  gap: '1rem'
                }}>
                  {numDocs > 0 && (
                    <div className="metric-card" style={{ 
                      background: 'rgba(59, 130, 246, 0.1)',
                      border: '1px solid rgba(59, 130, 246, 0.3)'
                    }}>
                      <span className="stat__label">Documents Analyzed</span>
                      <span className="stat__value" style={{ color: '#3b82f6' }}>
                        {numDocs}
                      </span>
                    </div>
                  )}
                  
                  {numTopicsLDA > 0 && (
                    <div className="metric-card" style={{ 
                      background: 'rgba(59, 130, 246, 0.1)',
                      border: '1px solid rgba(59, 130, 246, 0.3)'
                    }}>
                      <span className="stat__label">LDA Topics</span>
                      <span className="stat__value" style={{ color: '#3b82f6' }}>
                        {numTopicsLDA}
                      </span>
                    </div>
                  )}
                  
                  {numTopicsBERTopic > 0 && (
                    <div className="metric-card" style={{ 
                      background: 'rgba(34, 197, 94, 0.1)',
                      border: '1px solid rgba(34, 197, 94, 0.3)'
                    }}>
                      <span className="stat__label">BERTopic Topics</span>
                      <span className="stat__value" style={{ color: '#22c55e' }}>
                        {numTopicsBERTopic}
                      </span>
                    </div>
                  )}
                  
                  {avgSentiment !== null && (
                    <div className="metric-card" style={{ 
                      background: avgSentiment > 0.3 
                        ? 'rgba(34, 197, 94, 0.1)' 
                        : avgSentiment < -0.3 
                        ? 'rgba(248, 113, 113, 0.1)' 
                        : 'rgba(148, 163, 184, 0.1)',
                      border: `1px solid ${avgSentiment > 0.3 ? 'rgba(34, 197, 94, 0.3)' : avgSentiment < -0.3 ? 'rgba(248, 113, 113, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`
                    }}>
                      <span className="stat__label">Avg Sentiment</span>
                      <span className="stat__value" style={{ 
                        color: avgSentiment > 0.3 ? '#22c55e' : avgSentiment < -0.3 ? '#f87171' : '#94a3b8'
                      }}>
                        {avgSentiment > 0 ? '+' : ''}{avgSentiment.toFixed(3)}
                      </span>
                    </div>
                  )}
                  
                  {numInsights > 0 && (
                    <div className="metric-card" style={{ 
                      background: 'rgba(168, 85, 247, 0.1)',
                      border: '1px solid rgba(168, 85, 247, 0.3)'
                    }}>
                      <span className="stat__label">Topic Insights</span>
                      <span className="stat__value" style={{ color: '#a855f7' }}>
                        {numInsights}
                      </span>
                    </div>
                  )}
                </div>
                
                {/* Pipeline Statistics Section */}
                <div style={{
                  background: 'rgba(15, 23, 42, 0.4)',
                  borderRadius: 12,
                  padding: '1rem 1.25rem',
                  border: '1px solid rgba(59, 130, 246, 0.2)'
                }}>
                  <div style={{ 
                    fontSize: '0.85rem', 
                    fontWeight: 600, 
                    color: '#3b82f6',
                    marginBottom: '0.75rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Pipeline Statistics
                  </div>
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '0.75rem'
                  }}>
                    {numDocs > 0 && (
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)'
                      }}>
                        <span style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                          Documents Processed:
                        </span>
                        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#3b82f6' }}>
                          {numDocs}
                        </span>
                      </div>
                    )}
                    
                    {numTopicsLDA >= 0 && (
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)'
                      }}>
                        <span style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                          LDA Topics Discovered:
                        </span>
                        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#3b82f6' }}>
                          {numTopicsLDA}
                        </span>
                      </div>
                    )}
                    
                    {numTopicsBERTopic >= 0 && (
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)'
                      }}>
                        <span style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                          BERTopic Topics Discovered:
                        </span>
                        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#22c55e' }}>
                          {numTopicsBERTopic}
                        </span>
                      </div>
                    )}
                    
                    {avgSentiment !== null && (
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)'
                      }}>
                        <span style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                          Average Sentiment Score:
                        </span>
                        <span style={{ 
                          fontSize: '0.95rem', 
                          fontWeight: 600, 
                          color: avgSentiment > 0.3 ? '#22c55e' : avgSentiment < -0.3 ? '#f87171' : '#94a3b8'
                        }}>
                          {avgSentiment > 0 ? '+' : ''}{avgSentiment.toFixed(3)}
                        </span>
                      </div>
                    )}
                    
                    {numInsights > 0 && (
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)'
                      }}>
                        <span style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                          Topic Insights Generated:
                        </span>
                        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#a855f7' }}>
                          {numInsights}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Overall Insights */}
                {numInsights > 0 && (
                  <div style={{
                    background: 'rgba(15, 23, 42, 0.5)',
                    borderRadius: 12,
                    padding: '1rem 1.25rem',
                    border: '1px solid rgba(59, 130, 246, 0.2)'
                  }}>
                    <div style={{ 
                      fontSize: '0.85rem', 
                      fontWeight: 600, 
                      color: '#3b82f6',
                      marginBottom: '0.5rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Key Findings
                    </div>
                    <div style={{ 
                      fontSize: '0.95rem', 
                      lineHeight: 1.6,
                      color: 'var(--text-primary)'
                    }}>
                      {numInsights} key topic{numInsights !== 1 ? 's' : ''} identified from {numDocs} document{numDocs !== 1 ? 's' : ''} using advanced topic modeling (LDA & BERTopic). 
                      {avgSentiment !== null && (
                        <span> Overall sentiment is <strong style={{ 
                          color: avgSentiment > 0.3 ? '#22c55e' : avgSentiment < -0.3 ? '#f87171' : '#94a3b8'
                        }}>{avgSentiment > 0.3 ? 'positive' : avgSentiment < -0.3 ? 'negative' : 'neutral'}</strong>.</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })()}

        {dailyInsights.length > 0 && (
          <div
            className="content-panel"
            style={{
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: 12,
              padding: '1rem 1.25rem',
              display: 'grid',
              gap: '1rem'
            }}
          >
            <div>
              <h3 className="content-panel__title" style={{ margin: 0 }}>Daily insight timeline</h3>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                Covering {dailySummary.dates ?? dailyInsights.length} day(s) · {dailySummary.total_documents ?? 0} articles analysed.
              </p>
            </div>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {dailyInsights.map((item, idx) => {
                const automated = Array.isArray(item.automated_insights) ? item.automated_insights : [];
                const formattedDate = item.date
                  ? new Date(`${item.date}T00:00:00Z`).toLocaleDateString()
                  : `Day ${idx + 1}`;
                return (
                  <div
                    key={`${item.date || idx}-daily`}
                    style={{
                      background: 'rgba(15, 23, 42, 0.45)',
                      borderRadius: 10,
                      padding: '0.85rem 1rem',
                      display: 'grid',
                      gap: '0.5rem'
                    }}
                  >
                    <div style={{ fontWeight: 600, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <span>{formattedDate}</span>
                      <span style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>
                        {item.asset ? item.asset.toUpperCase() : 'ALL'} · {item.total_documents ?? 0} articles
                      </span>
                    </div>
                    {automated.length > 0 && (
                      <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'grid', gap: '0.35rem', fontSize: '0.92rem' }}>
                        {automated.slice(0, 2).map((line, insightIdx) => (
                          <li key={`${item.date || idx}-insight-${insightIdx}`}>{line}</li>
                        ))}
                        {automated.length > 2 && (
                          <li style={{ listStyle: 'none', color: 'var(--text-subtle)', fontSize: '0.85rem' }}>+{automated.length - 2} more insights</li>
                        )}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    );
  };

  return (
    <>
      <Navbar />
      
      {/* Notification Toast Container */}
      <div style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        zIndex: 10000,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        maxWidth: '400px',
        pointerEvents: 'none'
      }}>
        {notifications.map((notification) => {
          const bgColor = notification.type === 'error' ? '#f87171' : 
                         notification.type === 'warning' ? '#f97316' : '#3b82f6';
          const icon = notification.type === 'error' ? '❌' : 
                      notification.type === 'warning' ? '⚠️' : 'ℹ️';
          
          return (
            <motion.div
              key={notification.id}
              initial={{ opacity: 0, x: 100, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 100, scale: 0.9 }}
              style={{
                background: `linear-gradient(135deg, ${bgColor} 0%, ${bgColor}dd 100%)`,
                color: 'white',
                padding: '0.85rem 1rem',
                borderRadius: '12px',
                boxShadow: '0 8px 16px -4px rgba(0, 0, 0, 0.3)',
                fontSize: '0.9rem',
                lineHeight: 1.5,
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                pointerEvents: 'auto',
                border: `1px solid ${bgColor}80`,
                maxWidth: '100%'
              }}
            >
              <span style={{ fontSize: '1.2rem', flexShrink: 0 }}>{icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                  {notification.type === 'error' ? 'Error' : 
                   notification.type === 'warning' ? 'Warning' : 'Info'}
                </div>
                <div style={{ fontSize: '0.85rem', opacity: 0.95 }}>
                  {notification.message}
                </div>
              </div>
              <button
                onClick={() => setNotifications(prev => prev.filter(n => n.id !== notification.id))}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  border: 'none',
                  color: 'white',
                  borderRadius: '6px',
                  width: '24px',
                  height: '24px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1rem',
                  flexShrink: 0,
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.3)'}
                onMouseLeave={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.2)'}
              >
                ×
              </button>
            </motion.div>
          );
        })}
      </div>
      
      <motion.section
        className="page-shell page-shell--wide"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        aria-labelledby="prediction-heading"
      >
        {loading && !error && !insights ? (
          <div className="hero-skeleton" role="status" aria-live="polite">
            <span className="hero-skeleton__eyebrow" />
            <span className="hero-skeleton__title" />
            <span className="hero-skeleton__subtitle" />
          </div>
        ) : (
          <header className="page-header" style={{ alignItems: 'center', textAlign: 'center' }}>
            <span className="page-header__eyebrow">Prediction lab</span>
            <h1 id="prediction-heading" className="page-header__title">Market Outlook</h1>
            <p className="page-header__subtitle" style={{ margin: '0 auto', maxWidth: '720px' }}>
              {error
                ? 'Insights are temporarily unavailable. Refresh the page or revisit later to continue forecasting.'
                : 'Fine-tune the prediction engine, explore accuracy metrics, and compare scenarios to stay ahead of the market.'}
            </p>
          </header>
        )}

        <div className="split-layout">
          <aside className="panel" aria-label="Prediction parameters">
            <div className="panel__heading">Data parameters</div>
            <div className="panel__content">
              <div className="input-group">
                <label htmlFor="backtrack-range" className="input-label">Backtracking period</label>
                <input
                  id="backtrack-range"
                  type="range"
                  min={1}
                  max={40}
                  value={backtrack}
                  onChange={e => setBacktrack(Number(e.target.value))}
                />
                <span className="content-panel__text" style={{ marginTop: '-0.25rem' }}>{backtrack} days</span>
              </div>
              <div className="input-group">
                <label htmlFor="interval-days" className="input-label">Select interval (days)</label>
                <input
                  id="interval-days"
                  className="input-control"
                  type="number"
                  min={0}
                  max={7}
                  value={intervalDays}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    if (Number.isFinite(next)) {
                      setIntervalDays(Math.min(7, Math.max(0, next)));
                    }
                  }}
                  placeholder="0-7 days"
                />
                <span className="content-panel__text" style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                  Set to 0 to rely on the hour interval below.
                </span>
              </div>
              <div className="input-group">
                <label htmlFor="interval-hours" className="input-label">Interval (hours)</label>
                <input
                  id="interval-hours"
                  className="input-control"
                  type="number"
                  min={1}
                  max={24}
                  value={intervalHours}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    if (Number.isFinite(next)) {
                      setIntervalHours(Math.min(24, Math.max(1, next)));
                    }
                  }}
                  placeholder="1-24 hours"
                />
              </div>
              <div className="section-divider" />
              <div className="input-group">
                <label htmlFor="coin-select" className="input-label">Target cryptocurrency</label>
                {coinsLoading ? (
                  <div className="empty-state">Loading coins…</div>
                ) : coinsError ? (
                  <div className="empty-state" style={{ borderStyle: 'solid' }}>{coinsError}</div>
                ) : (
                  <>
                    <input
                      id="coin-search"
                      className="input-control"
                      type="text"
                      value={coinSearch}
                      onChange={(e) => setCoinSearch(e.target.value)}
                      placeholder="Search coin (e.g. BTC, Bitcoin)"
                      style={{ marginBottom: '0.75rem' }}
                    />
                    <select
                      id="coin-select"
                      className="select-control"
                      value={selected}
                      onChange={e => setSelected(e.target.value)}
                    >
                      {coins
                        .filter((coin) => {
                          if (!coinSearch) return true;
                          const q = coinSearch.toLowerCase();
                          return (coin.symbol || '').toLowerCase().includes(q) || (coin.name || '').toLowerCase().includes(q);
                        })
                        .map((coin) => (
                          <option key={coin.id} value={coin.id}>
                            {(coin.symbol || '').toUpperCase()} — {coin.name}
                          </option>
                        ))}
                    </select>
                  </>
                )}
              </div>
              <div className="badge-stack">
                <span className="badge">Hybrid models</span>
                <span className="badge">Sentiment enriched</span>
                <span className="badge">Backtest ready</span>
              </div>
            </div>
          </aside>

          <div className="panel panel--muted" style={{ gap: '1.75rem' }}>
            <div className="card-grid card-grid--two" aria-label="Key metrics">
              <div className="metric-card">
                <span className="stat__label">Coin price</span>
                <div className="stat__value">
                  {livePriceLoading && 'Loading…'}
                  {!livePriceLoading && livePrice && new Intl.NumberFormat(undefined, {
                    style: 'currency',
                    currency: 'USD',
                    maximumFractionDigits: 2
                  }).format(livePrice.value)}
                  {!livePriceLoading && !livePrice && !livePriceError && '—'}
                  {!livePriceLoading && livePriceError && 'Error'}
                </div>
                <span className="stat__delta">
                  {livePriceError && (
                    <span style={{ color: '#f97316' }}>{livePriceError}</span>
                  )}
                  {!livePriceError && livePrice && typeof livePrice.change24h === 'number' && (
                    <>
                      {livePrice.change24h >= 0 ? '+' : '-'}
                      {Math.abs(livePrice.change24h).toFixed(2)}% (24h)
                    </>
                  )}
                  {!livePriceError && livePrice && livePrice.updatedAt && (
                    <span style={{ display: 'block', color: 'var(--text-subtle)', fontSize: '0.75rem', marginTop: '0.35rem' }}>
                      Updated {livePrice.updatedAt.toLocaleTimeString()}
                    </span>
                  )}
                  {!livePriceError && !livePrice && !livePriceLoading && 'Realtime snapshot'}
                </span>
              </div>
              <div className="metric-card metric-card--neutral" style={{ display: 'grid', gap: '0.4rem' }}>
                <span className="stat__label">Trend forecast</span>
                <div className="stat__value" style={{ color: trendForecast?.label === 'up' ? '#22c55e' : trendForecast?.label === 'down' ? '#f87171' : 'var(--text-primary)' }}>
                  {trendLoading && 'Loading…'}
                  {!trendLoading && trendError && 'Unavailable'}
                  {!trendLoading && !trendError && (trendLabelDisplay || 'Awaiting data')}
                </div>
                <span className="stat__delta">
                  {trendLoading && 'Updating prediction'}
                  {!trendLoading && trendError && (
                    <span style={{ color: '#f97316' }}>{trendError}</span>
                  )}
                  {!trendLoading && !trendError && trendForecast && (
                    <>Confidence {typeof trendForecast.confidence === 'number' ? `${(trendForecast.confidence * 100).toFixed(1)}%` : '—'}{trendTimestamp ? ` · Updated ${trendTimestamp.toLocaleString()}` : ''}</>
                  )}
                  {!trendLoading && !trendError && !trendForecast && 'Awaiting first prediction'}
                </span>
                {trendForecast && (
                  <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                    {trendProbabilityItems.map((item) => (
                      <span key={item.key}>
                        {item.label}: {item.value != null ? `${(item.value * 100).toFixed(1)}%` : '—'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="glass-card" style={{ background: 'rgba(15, 23, 42, 0.72)', minHeight: '120px' }}>
              <span className="panel__heading">
                Historical performance {selectedCoinMeta ? `(${selectedCoinMeta.symbol.toUpperCase()})` : ''}
              </span>
              <div className="scroll-area" style={{ maxHeight: '140px' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Historical date</th>
                      <th>Close price</th>
                      <th>Sensitivity (% change / price)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historicalLoading && (
                      <tr>
                        <td colSpan={3} style={{ textAlign: 'center' }}>Loading historical data…</td>
                      </tr>
                    )}
                    {!historicalLoading && historicalError && (
                      <tr>
                        <td colSpan={3} style={{ textAlign: 'center', color: '#f97316' }}>{historicalError}</td>
                      </tr>
                    )}
                    {!historicalLoading && !historicalError && historicalData.length === 0 && (
                      <tr>
                        <td colSpan={3} style={{ textAlign: 'center' }}>No historical data available.</td>
                      </tr>
                    )}
                    {!historicalLoading && !historicalError && historicalData.map((row, index) => (
                      <tr key={`${row.date}-${index}`}>
                        <td>{row.date}</td>
                        <td>{row.closePrice}</td>
                        <td>{row.sensitivity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="glass-card" style={{ background: 'rgba(15, 23, 42, 0.72)', display: 'grid', gap: '0.75rem', minHeight: '620px', paddingTop: '0.5rem' }}>
              <div className="page-actions" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', margin: 0, padding: '0.5rem 0 0 0' }}>
                <h2 className="content-panel__title" style={{ margin: 0 }}>Insights</h2>
                <div className="tabs" role="tablist" aria-label="Insights view">
                  <button
                    type="button"
                    className={`tab ${activeTab === 'overview' ? 'tab--active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                    role="tab"
                    aria-selected={activeTab === 'overview'}
                  >
                    Overview
                  </button>
                  <button
                    type="button"
                    className={`tab ${activeTab === 'accuracy' ? 'tab--active' : ''}`}
                    onClick={() => {
                      setActiveTab('accuracy');
                      // Load accuracy metrics when tab is clicked if not already loaded
                      if (!accuracyMetrics) {
                        loadAccuracyMetrics();
                      }
                    }}
                    role="tab"
                    aria-selected={activeTab === 'accuracy'}
                  >
                    Accuracy
                  </button>
                </div>
              </div>

              <div className="scroll-area" role="region" aria-live="polite" style={{ maxHeight: '540px', marginTop: 0 }}>
                {loading && (
                  <div className="empty-state">Loading…</div>
                )}

                {error && (
                  <div className="empty-state" style={{ borderStyle: 'solid', borderColor: '#f97316', color: '#f97316', padding: '1rem', borderRadius: '8px', background: 'rgba(249, 115, 22, 0.1)' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Failed to load insights</div>
                    <div style={{ fontSize: '0.9rem' }}>{error}</div>
                    <button 
                      onClick={() => loadGeneralInsights()} 
                      style={{ 
                        marginTop: '0.75rem', 
                        padding: '0.5rem 1rem', 
                        background: '#f97316', 
                        color: 'white', 
                        border: 'none', 
                        borderRadius: '6px', 
                        cursor: 'pointer',
                        fontSize: '0.9rem'
                      }}
                    >
                      Retry
                    </button>
                  </div>
                )}

                {activeTab === 'overview' && !loading && !error && insights && (
                  <div style={{ fontSize: '0.95rem', lineHeight: 1.5 }}>
                    {renderInsightsContent() || (
                      <div className="empty-state">No insights data available in the selected time window</div>
                    )}
                  </div>
                )}

                {activeTab === 'accuracy' && (
                  accuracyMetrics ? (
                  <div className="insights-content" style={{ display: 'grid', gap: '1rem' }}>
                    {/* Main System Accuracy - Overall System Performance */}
                    <div className="metric-card metric-card--neutral" style={{ 
                      background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)',
                      borderRadius: 16,
                      padding: '1.5rem',
                      border: '2px solid rgba(34, 197, 94, 0.3)',
                      boxShadow: '0 8px 16px -4px rgba(34, 197, 94, 0.2)'
                    }}>
                      <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: '0.5rem' }}>
                        Main System Accuracy
                      </div>
                      <div className="stat__value" style={{ fontSize: '3rem', fontWeight: 800, color: '#22c55e', margin: '0.5rem 0' }}>
                        {accuracyMetrics.summary?.main_system_accuracy 
                          ? (accuracyMetrics.summary.main_system_accuracy * 100).toFixed(1) + '%'
                          : (Math.max(...Object.values(accuracyMetrics.summary?.accuracy_comparison || { baseline: 0 })) * 100).toFixed(1) + '%'}
                      </div>
                      <div className="stat__delta" style={{ color: 'var(--text-subtle)', fontSize: '0.9rem' }}>
                        Combined accuracy of sentiment analysis and trend prediction
                      </div>
                      {accuracyMetrics.summary?.evaluation_date && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginTop: '0.5rem', fontStyle: 'italic' }}>
                          Evaluated: {new Date(accuracyMetrics.summary.evaluation_date).toLocaleString()}
                        </div>
                      )}
                    </div>

                    {/* Individual Model Accuracies - Prominent Display */}
                    <div className="content-panel" style={{ 
                      background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(15, 23, 42, 0.6) 100%)',
                      borderRadius: 16,
                      padding: '1.5rem',
                      border: '2px solid rgba(59, 130, 246, 0.3)'
                    }}>
                      <h3 className="content-panel__title" style={{ marginBottom: '1.5rem' }}>📊 Individual Model Accuracies</h3>
                      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                        {/* BiLSTM Accuracy */}
                        {accuracyMetrics.summary?.accuracy_comparison?.bilstm !== null && accuracyMetrics.summary?.accuracy_comparison?.bilstm !== undefined && (
                          <div style={{
                            background: accuracyMetrics.summary?.best_sentiment_model === 'bilstm' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(15, 23, 42, 0.45)',
                            borderRadius: 12,
                            padding: '1.5rem',
                            border: `2px solid ${accuracyMetrics.summary?.best_sentiment_model === 'bilstm' ? 'rgba(34, 197, 94, 0.4)' : 'rgba(59, 130, 246, 0.3)'}`,
                            textAlign: 'center'
                          }}>
                            <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: '0.75rem' }}>
                              BiLSTM Sentiment Analysis
                              {accuracyMetrics.summary?.best_sentiment_model === 'bilstm' && <span style={{ color: '#22c55e', marginLeft: '0.5rem' }}>⭐</span>}
                            </div>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: accuracyMetrics.summary?.best_sentiment_model === 'bilstm' ? '#22c55e' : '#3b82f6', marginBottom: '0.5rem' }}>
                              {(accuracyMetrics.summary.accuracy_comparison.bilstm * 100).toFixed(1)}%
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                              Positive/Neutral/Negative Classification
                            </div>
                          </div>
                        )}
                        
               {/* RoBERTa Accuracy */}
               {accuracyMetrics.summary?.accuracy_comparison?.roberta !== null && accuracyMetrics.summary?.accuracy_comparison?.roberta !== undefined && (
                 <div style={{
                   background: accuracyMetrics.summary?.best_sentiment_model === 'roberta' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(15, 23, 42, 0.45)',
                   borderRadius: 12,
                   padding: '1.5rem',
                   border: `2px solid ${accuracyMetrics.summary?.best_sentiment_model === 'roberta' ? 'rgba(34, 197, 94, 0.4)' : 'rgba(59, 130, 246, 0.3)'}`,
                   textAlign: 'center'
                 }}>
                   <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}>
                     {beginnerMode ? 'Advanced Sentiment Analysis' : 'RoBERTa Sentiment Analysis'}
                     {accuracyMetrics.summary?.best_sentiment_model === 'roberta' && <span style={{ color: '#22c55e', marginLeft: '0.5rem' }}>⭐</span>}
                     <Tooltip 
                       id="roberta-accuracy"
                       text={beginnerMode 
                         ? "Another system that reads text to understand feelings. It's like having a second opinion to make sure we're right."
                         : "RoBERTa (Robustly Optimized BERT Pretraining Approach) transformer model for sentiment analysis"}
                       showTooltips={showTooltips}
                       setShowTooltips={setShowTooltips}
                     >
                       <span></span>
                     </Tooltip>
                   </div>
                   <div style={{ fontSize: '2.5rem', fontWeight: 800, color: accuracyMetrics.summary?.best_sentiment_model === 'roberta' ? '#22c55e' : '#3b82f6', marginBottom: '0.5rem' }}>
                     {(accuracyMetrics.summary.accuracy_comparison.roberta * 100).toFixed(1)}%
                   </div>
                   <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                     {beginnerMode ? 'How well it understands feelings in text' : 'Positive/Neutral/Negative Classification'}
                   </div>
                 </div>
               )}
                        
               {/* LSTM Trend Prediction Accuracy */}
               {accuracyMetrics.summary?.accuracy_comparison?.lstm_trend !== null && accuracyMetrics.summary?.accuracy_comparison?.lstm_trend !== undefined && (
                 <div style={{
                   background: 'rgba(15, 23, 42, 0.45)',
                   borderRadius: 12,
                   padding: '1.5rem',
                   border: '2px solid rgba(59, 130, 246, 0.3)',
                   textAlign: 'center'
                 }}>
                   <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}>
                     {beginnerMode ? 'Price Prediction' : 'LSTM Trend Prediction'}
                     <Tooltip 
                       id="lstm-trend-accuracy"
                       text={beginnerMode 
                         ? "This system looks at past price patterns to predict if prices will go up, down, or stay the same. It's like a weather forecast for cryptocurrency prices."
                         : "LSTM (Long Short-Term Memory) neural network for predicting price movement direction"}
                       showTooltips={showTooltips}
                       setShowTooltips={setShowTooltips}
                     >
                       <span></span>
                     </Tooltip>
                   </div>
                   <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#3b82f6', marginBottom: '0.5rem' }}>
                     {(accuracyMetrics.summary.accuracy_comparison.lstm_trend * 100).toFixed(1)}%
                   </div>
                   <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                     {beginnerMode ? 'How well it predicts price direction' : 'Up/Down/Neutral Price Movement'}
                   </div>
                 </div>
               )}
                        
                        {/* Baseline */}
                        {accuracyMetrics.summary?.accuracy_comparison?.baseline !== null && accuracyMetrics.summary?.accuracy_comparison?.baseline !== undefined && (
                          <div style={{
                            background: 'rgba(15, 23, 42, 0.3)',
                            borderRadius: 12,
                            padding: '1.5rem',
                            border: '2px solid rgba(148, 163, 184, 0.2)',
                            textAlign: 'center',
                            opacity: 0.7
                          }}>
                            <div style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: '0.75rem' }}>
                              Baseline (Random)
                            </div>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#94a3b8', marginBottom: '0.5rem' }}>
                              {(accuracyMetrics.summary.accuracy_comparison.baseline * 100).toFixed(1)}%
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                              Random Guess Baseline
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Detailed Model Metrics - Same design as Overview topic cards */}
                    {accuracyMetrics.models && Object.entries(accuracyMetrics.models).map(([modelName, modelData]) => (
                      <div key={modelName} className="content-panel" style={{
                        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(15, 23, 42, 0.6) 100%)',
                        borderRadius: 16,
                        padding: '1.5rem',
                        border: '2px solid rgba(59, 130, 246, 0.3)',
                        boxShadow: '0 4px 12px -2px rgba(59, 130, 246, 0.2)'
                      }}>
                        <h3 className="content-panel__title" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '1.5rem' }}>🎯</span>
                          {modelName === 'bilstm' ? 'BiLSTM' : modelName === 'lstm_trend' ? 'LSTM Trend Prediction' : modelName.toUpperCase()} Detailed Metrics
                          {modelData.task && (
                            <span style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', fontWeight: 'normal', marginLeft: '0.5rem' }}>
                              ({modelData.task})
                            </span>
                          )}
                        </h3>
                        {modelData.note && (
                          <div style={{ 
                            fontSize: '0.85rem', 
                            color: 'var(--text-subtle)', 
                            fontStyle: 'italic',
                            marginBottom: '1rem',
                            padding: '0.5rem',
                            background: 'rgba(59, 130, 246, 0.1)',
                            borderRadius: 6
                          }}>
                            {modelData.note}
                          </div>
                        )}
                        
                        {/* Overall Metrics Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                          <div style={{ background: 'rgba(15, 23, 42, 0.5)', borderRadius: 10, padding: '1rem', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '0.25rem' }}>Precision</div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                              {(modelData.precision * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div style={{ background: 'rgba(15, 23, 42, 0.5)', borderRadius: 10, padding: '1rem', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '0.25rem' }}>Recall</div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                              {(modelData.recall * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div style={{ background: 'rgba(15, 23, 42, 0.5)', borderRadius: 10, padding: '1rem', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '0.25rem' }}>F1-Score</div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                              {(modelData.f1_score * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div style={{ background: 'rgba(15, 23, 42, 0.5)', borderRadius: 10, padding: '1rem', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '0.25rem' }}>Accuracy</div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>
                              {(modelData.overall_accuracy * 100).toFixed(1)}%
                            </div>
                          </div>
                        </div>

                        {/* Per-Class Metrics */}
                        {modelData.precision_per_class && Object.keys(modelData.precision_per_class).length > 0 && (
                          <div style={{ marginTop: '1rem' }}>
                            <h4 className="content-panel__title" style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>
                              Per-Class Performance Evaluation
                              <span style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', fontWeight: 'normal', marginLeft: '0.5rem' }}>
                                ({Object.keys(modelData.precision_per_class).join(', ')})
                              </span>
                            </h4>
                            <div style={{ display: 'grid', gap: '0.75rem' }}>
                              {Object.entries(modelData.precision_per_class).map(([className, precision]) => {
                                const recall = modelData.recall_per_class?.[className] || 0;
                                const f1 = modelData.f1_per_class?.[className] || 0;
                                const support = modelData.support_per_class?.[className] || 0;
                                
                                // Handle both sentiment classes and trend classes
                                const sentimentColor = className === 'positive' || className === 'up' ? '#22c55e' : 
                                                      className === 'negative' || className === 'down' ? '#ef4444' : '#94a3b8';
                                
                                return (
                                  <div key={className} style={{
                                    background: `linear-gradient(135deg, ${sentimentColor}15 0%, rgba(15, 23, 42, 0.5) 100%)`,
                                    borderRadius: 12,
                                    padding: '1rem',
                                    border: `2px solid ${sentimentColor}40`,
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                                    gap: '0.75rem'
                                  }}>
                                    <div>
                                      <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                                        {className}
                                      </div>
                                      <div style={{ fontSize: '1.1rem', fontWeight: 600, color: sentimentColor }}>
                                        Precision: {(precision * 100).toFixed(1)}%
                                      </div>
                                    </div>
                                    <div>
                                      <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                                        Recall
                                      </div>
                                      <div style={{ fontSize: '1.1rem', fontWeight: 600, color: sentimentColor }}>
                                        {(recall * 100).toFixed(1)}%
                                      </div>
                                    </div>
                                    <div>
                                      <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                                        F1-Score
                                      </div>
                                      <div style={{ fontSize: '1.1rem', fontWeight: 600, color: sentimentColor }}>
                                        {(f1 * 100).toFixed(1)}%
                                      </div>
                                    </div>
                                    <div>
                                      <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                                        Samples
                                      </div>
                                      <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                        {support}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}

                    {/* Evaluation Metadata */}
                    {accuracyMetrics.evaluation_metadata && (
                      <div className="content-panel" style={{
                        background: 'rgba(15, 23, 42, 0.4)',
                        borderRadius: 12,
                        padding: '1rem',
                        fontSize: '0.85rem',
                        color: 'var(--text-subtle)'
                      }}>
                        <div style={{ display: 'grid', gap: '0.5rem' }}>
                          <div><strong>Total Samples:</strong> {accuracyMetrics.evaluation_metadata.total_samples || 'N/A'}</div>
                          <div><strong>Test Samples:</strong> {accuracyMetrics.evaluation_metadata.test_samples || 'N/A'}</div>
                          <div><strong>Classes:</strong> {accuracyMetrics.evaluation_metadata.classes?.join(', ') || 'N/A'}</div>
                          <div><strong>Method:</strong> {accuracyMetrics.evaluation_metadata.evaluation_method || 'N/A'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                  ) : (
                    <div className="content-panel" style={{ 
                      padding: '2rem', 
                      textAlign: 'center',
                      background: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 12
                    }}>
                      <div style={{ fontSize: '1.1rem', color: 'var(--text-subtle)', marginBottom: '0.5rem' }}>
                        {accuracyMetrics === null ? 'Loading accuracy metrics...' : 'Accuracy metrics unavailable'}
                      </div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-subtle)' }}>
                        {accuracyMetrics === null 
                          ? 'Please wait while we fetch evaluation results.'
                          : 'The evaluation system may be temporarily unavailable. Please try again later.'}
                      </div>
                    </div>
                  )
                )}

                {!insights && !loading && !error && activeTab !== 'accuracy' && (
                  <div className="empty-state">No insights data available</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </motion.section>
    </>
  );
};

export default Prediction;






