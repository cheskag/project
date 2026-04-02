import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import Navbar from '../components/Navbar';
import axios from 'axios';
import Chart from 'chart.js/auto';
import zoomPlugin from 'chartjs-plugin-zoom';

Chart.register(zoomPlugin);

const CryptoData = () => {
  const [coins, setCoins] = useState([]);
  const [coinSearch, setCoinSearch] = useState('');
  const [selectedCoin, setSelectedCoin] = useState('');
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [coinsLoading, setCoinsLoading] = useState(false);
  const [error, setError] = useState('');
  const [coinsError, setCoinsError] = useState('');
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');
  const [liveSeries, setLiveSeries] = useState([]);

  const chartCanvasRef = useRef(null);
  const chartInstanceRef = useRef(null);

  // Optional CoinGecko API key support (if provided)
  const hasCoinGeckoKey = Boolean(process.env.REACT_APP_COINGECKO_API_KEY);
  const PRO_BASE = 'https://pro-api.coingecko.com/api/v3';
  const PUBLIC_BASE = 'https://api.coingecko.com/api/v3';

  const requestCoinGecko = React.useCallback(async (endpoint, config = {}) => {
    const headers = {
      Accept: 'application/json',
      ...(config.headers || {}),
    };

    if (hasCoinGeckoKey) {
      headers['x-cg-pro-api-key'] = process.env.REACT_APP_COINGECKO_API_KEY;
    }

    try {
      const res = await axios.get(`${hasCoinGeckoKey ? PRO_BASE : PUBLIC_BASE}${endpoint}`, {
        ...config,
        headers,
      });
      return res;
    } catch (err) {
      const status = err?.response?.status;
      if (hasCoinGeckoKey && (status === 401 || status === 403)) {
        console.warn('[CryptoData] Pro API auth failed, falling back to public endpoint.');
        const fallbackRes = await axios.get(`${PUBLIC_BASE}${endpoint}`, {
          ...config,
          headers: {
            ...config.headers,
            Accept: 'application/json',
          },
        });
        return fallbackRes;
      }
      throw err;
    }
  }, [hasCoinGeckoKey, PRO_BASE, PUBLIC_BASE]);

  const coinsCacheKey = 'cryptogauge_coins_top100_v1';
  const CACHE_TTL_MS = 5 * 60 * 1000;
  const LIVE_REFRESH_INTERVAL = 3 * 1000;
  const LIVE_MAX_POINTS = 180;

  const readCache = React.useCallback((key) => {
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
      console.warn('[CryptoData] Cache read failed', err);
      sessionStorage.removeItem(key);
      return null;
    }
  }, [CACHE_TTL_MS]);

  const writeCache = React.useCallback((key, payload) => {
    try {
      sessionStorage.setItem(key, JSON.stringify({ timestamp: Date.now(), payload }));
    } catch (err) {
      console.warn('[CryptoData] Cache write failed', err);
    }
  }, []);

  const priceCacheKey = (coinId) => `cryptogauge_price_${coinId}`;

  const loadPriceData = React.useCallback(async (coinId) => {
    setLoading(true);
    setError('');
    try {
      const cachedPrice = readCache(priceCacheKey(coinId));
      if (cachedPrice && typeof cachedPrice === 'object') {
        setPriceData(cachedPrice);
        setLoading(false);
        return;
      }

      const res = await requestCoinGecko(
        `/coins/${encodeURIComponent(coinId)}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false`,
        { timeout: 15000 }
      );
      const md = res.data?.market_data;
      if (!md) {
        setPriceData(null);
      } else {
        const toCurrency = (n) => {
          if (n === null || n === undefined || Number.isNaN(n)) return '-';
          return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
        };
        const toNumber = (n, digits = 2) => {
          if (n === null || n === undefined || Number.isNaN(n)) return '-';
          return Number(n).toLocaleString(undefined, { maximumFractionDigits: digits });
        };
        const formatted = {
          price: toCurrency(md.current_price?.usd),
          change24h: `${toNumber(md.price_change_percentage_24h, 2)}%`,
          volume: toCurrency(md.total_volume?.usd),
          marketCap: toCurrency(md.market_cap?.usd),
          high24h: toCurrency(md.high_24h?.usd),
          low24h: toCurrency(md.low_24h?.usd),
        };
        setPriceData(formatted);
        writeCache(priceCacheKey(coinId), formatted);
      }
    } catch (err) {
      if (process.env.NODE_ENV === 'development') {
        console.warn('[CryptoData] Price fetch error:', err?.response?.data || err.message || err);
      }
      const status = err?.response?.status;
      if (status === 429) {
        setError('Rate limit reached. Please wait a moment and try again.');
      } else {
        setError('Unable to load market data. Please try another coin or try again later.');
      }
      setLoading(false);
      return;
    }
    setLoading(false);
  }, [readCache, requestCoinGecko, writeCache]);

  const loadCoins = React.useCallback(async () => {
    setCoinsLoading(true);
    setCoinsError('');
    try {
      const cachedCoins = readCache(coinsCacheKey);
      if (Array.isArray(cachedCoins) && cachedCoins.length) {
        setCoins(cachedCoins);
        setSelectedCoin(cachedCoins.find(c => c.id === 'bitcoin') ? 'bitcoin' : cachedCoins[0].id);
        setCoinsLoading(false);
        return;
      }

      const res = await requestCoinGecko(
        '/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&locale=en',
        { timeout: 20000 }
      );
      const list = Array.isArray(res.data)
        ? res.data
            .filter(c => c && c.id && c.symbol && c.name)
            .map(c => ({
              id: c.id,
              symbol: c.symbol?.toUpperCase() || '',
              name: c.name
            }))
        : [];
      setCoins(list);
      setSelectedCoin(list.find(c => c.id === 'bitcoin') ? 'bitcoin' : (list[0]?.id || ''));
      writeCache(coinsCacheKey, list);
    } catch (e) {
      if (process.env.NODE_ENV === 'development') {
        console.warn('[CryptoData] Coin list error:', e?.response?.data || e.message || e);
      }
      const status = e?.response?.status;
      if (status === 429) {
        setCoinsError('Rate limit hit on CoinGecko. Please wait a moment and try again.');
      } else {
        setCoinsError('Unable to load coin list. Please try again later.');
      }
    } finally {
      setCoinsLoading(false);
    }
  }, [readCache, requestCoinGecko, writeCache]);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        await loadCoins();
      } catch (err) {
        if (cancelled) return;
        if (process.env.NODE_ENV === 'development') {
          console.warn('[CryptoData] Unhandled coin loader error:', err);
        }
        setCoinsError('Unable to load coin list. Please try again later.');
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [loadCoins]);

  useEffect(() => {
    if (!selectedCoin) {
      return;
    }

    loadPriceData(selectedCoin);
  }, [selectedCoin, loadPriceData]);

  const loadLivePrice = async (coinId, { signal, showSpinner = true } = {}) => {
    if (!coinId) return;

    try {
      const res = await requestCoinGecko(
        `/simple/price?ids=${encodeURIComponent(coinId)}&vs_currencies=usd`,
        {
          timeout: 10000,
          signal
        }
      );

      const price = res.data?.[coinId]?.usd;
      if (typeof price !== 'number') {
        setChartError('Live price unavailable for this coin.');
        return;
      }

      setChartError('');
      setLiveSeries(prev => {
        const next = [
          ...prev,
          { timestamp: Date.now(), price: Number(price) }
        ];
        if (next.length > LIVE_MAX_POINTS) {
          return next.slice(next.length - LIVE_MAX_POINTS);
        }
        return next;
      });
    } catch (err) {
      if (err.code === 'ERR_CANCELED') {
        return;
      }
      if (process.env.NODE_ENV === 'development') {
        console.warn('[CryptoData] Live price fetch error:', err?.response?.data || err.message || err);
      }
      const status = err?.response?.status;
      if (status === 429) {
        setChartError('Rate limit reached while loading live price. Please wait and try again.');
      } else {
        setChartError('Unable to fetch live price at this time.');
      }
    } finally {
      if (showSpinner) {
        setChartLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!selectedCoin) {
      return undefined;
    }

    setChartLoading(true);
    setChartError('');
    setLiveSeries([]);

    let controller = new AbortController();

    const fetchPrice = async (showSpinner) => {
      await loadLivePrice(selectedCoin, { signal: controller.signal, showSpinner });
    };

    fetchPrice(true);

    const intervalId = setInterval(() => {
      controller.abort();
      controller = new AbortController();
      fetchPrice(false);
    }, LIVE_REFRESH_INTERVAL);

    return () => {
      clearInterval(intervalId);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCoin]);

  useEffect(() => {
    if (!liveSeries.length) {
      setChartData(null);
      return;
    }

    const dateFormatter = new Intl.DateTimeFormat(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });

    const labels = liveSeries.map(point => dateFormatter.format(point.timestamp));
    const values = liveSeries.map(point => point.price);

    if (values.length === 1) {
      const firstPoint = liveSeries[0];
      const syntheticTimestamp = new Date(firstPoint.timestamp - 1000);
      labels.unshift(dateFormatter.format(syntheticTimestamp));
      values.unshift(firstPoint.price);
    }

    setChartData({ labels, values });
  }, [liveSeries]);

  useEffect(() => {
    if (!chartData || !chartCanvasRef.current) {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
      return;
    }
    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
    }

    chartInstanceRef.current = new Chart(chartCanvasRef.current, {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [
          {
            label: 'Price (USD)',
            data: chartData.values,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            borderWidth: 2,
            pointRadius: chartData.values.length <= 2 ? 3 : 0,
            pointHoverRadius: 5,
            tension: 0.3,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: {
              color: '#e2e8f0',
              maxTicksLimit: 8,
              autoSkip: true
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.2)'
            }
          },
          y: {
            ticks: {
              color: '#e2e8f0',
              callback: (value) => {
                if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
                if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
                if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
                return `$${value}`;
              }
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.2)'
            }
          }
        },
        plugins: {
          legend: {
            labels: {
              color: '#e2e8f0'
            }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `Price: $${ctx.parsed.y.toLocaleString()}`
            }
          },
          zoom: {
            zoom: {
              wheel: {
                enabled: true
              },
              pinch: {
                enabled: true
              },
              drag: {
                enabled: true,
                modifierKey: 'shift'
              },
              mode: 'x'
            },
            pan: {
              enabled: true,
              mode: 'x',
              modifierKey: 'ctrl'
            },
            limits: {
              x: { min: 'original', max: 'original' },
              y: { min: 'original', max: 'original' }
            }
          }
        }
      }
    });

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, [chartData]);

  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
      }
    };
  }, []);

  return (
    <>
      <Navbar />
      <motion.section
        className="page-shell page-shell--wide"
        initial={{ opacity: 0, y: 28 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        aria-labelledby="crypto-data-heading"
      >
        <header className="page-header" style={{ alignItems: 'flex-start' }}>
          <span className="page-header__eyebrow">Live market desk</span>
          <h1 id="crypto-data-heading" className="page-header__title">Crypto Market Data</h1>
          <p className="page-header__subtitle" style={{ margin: 0 }}>
            Real-time cryptocurrency prices, market caps, volumes, and a rolling 7-day performance chart powered by CoinGecko Pro.
          </p>
        </header>

        <section className="card-grid card-grid--two" aria-label="Market controls and snapshot">
          <article className="glass-card">
            <h2 className="content-panel__title" style={{ marginTop: 0 }}>Select cryptocurrency</h2>
            {coinsLoading ? (
              <div className="empty-state">Loading coins…</div>
            ) : coinsError ? (
              <div className="empty-state" style={{ borderStyle: 'solid' }}>{coinsError}</div>
            ) : (
              <>
                <div className="input-group">
                  <label htmlFor="coin-search" className="input-label">Search</label>
                  <input
                    id="coin-search"
                    className="input-control"
                    type="text"
                    value={coinSearch}
                    onChange={(e) => setCoinSearch(e.target.value)}
                    placeholder="Search coin (e.g. BTC, Bitcoin)"
                  />
                </div>
                <div className="input-group">
                  <label htmlFor="coin-select" className="input-label">Available coins</label>
                  <select
                    id="coin-select"
                    className="select-control"
                    value={selectedCoin}
                    onChange={(e) => setSelectedCoin(e.target.value)}
                    size={1}
                  >
                    {coins
                      .filter(c => {
                        if (!coinSearch) return true;
                        const q = coinSearch.toLowerCase();
                        return (c.symbol || '').toLowerCase().includes(q) || (c.name || '').toLowerCase().includes(q);
                      })
                      .map(coin => (
                        <option key={coin.id} value={coin.id}>
                          {(coin.symbol || '').toUpperCase()} — {coin.name}
                        </option>
                      ))}
                  </select>
                </div>
              </>
            )}
          </article>

          <article className="glass-card content-panel" aria-live="polite">
            <h2 className="content-panel__title" style={{ marginTop: 0 }}>Market snapshot</h2>
            {error && (
              <div className="empty-state" style={{ borderStyle: 'solid', color: '#f97316' }}>{error}</div>
            )}
            {loading ? (
              <div className="empty-state">Loading market data…</div>
            ) : priceData ? (
              <div className="card-grid card-grid--two">
                <div className="metric-card">
                  <span className="stat__label">Current price</span>
                  <span className="stat__value">{priceData.price}</span>
                </div>
                <div className="metric-card">
                  <span className="stat__label">24h change</span>
                  <span className="stat__value">{priceData.change24h}</span>
                </div>
                <div className="metric-card metric-card--neutral">
                  <span className="stat__label">24h volume</span>
                  <span className="stat__value">{priceData.volume}</span>
                </div>
                <div className="metric-card metric-card--neutral">
                  <span className="stat__label">Market cap</span>
                  <span className="stat__value">{priceData.marketCap}</span>
                </div>
                <div className="metric-card">
                  <span className="stat__label">24h high</span>
                  <span className="stat__value">{priceData.high24h}</span>
                </div>
                <div className="metric-card">
                  <span className="stat__label">24h low</span>
                  <span className="stat__value">{priceData.low24h}</span>
                </div>
              </div>
            ) : (
              <div className="empty-state">Select a coin to view market data.</div>
            )}
          </article>
        </section>

        <section className="glass-card" aria-label="Live market price">
          <h2 className="content-panel__title" style={{ marginTop: 0 }}>Live Market Price</h2>
          {chartLoading ? (
            <div className="empty-state">Loading chart…</div>
          ) : chartError ? (
            <div className="empty-state" style={{ borderStyle: 'solid' }}>{chartError}</div>
          ) : chartData ? (
            <>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '0.75rem',
                  flexWrap: 'wrap',
                  marginBottom: '0.75rem',
                  color: 'var(--text-subtle)',
                  fontSize: '0.85rem'
                }}
              >
                <span>
                  Scroll to zoom · Hold <strong>Shift</strong> and drag to box-zoom · Hold <strong>Ctrl</strong> and drag to pan
                </span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ padding: '0.45rem 1.2rem' }}
                  onClick={() => {
                    if (chartInstanceRef.current) {
                      chartInstanceRef.current.resetZoom();
                    }
                  }}
                >
                  Reset view
                </button>
              </div>
            <div style={{ height: 360 }}>
                <canvas ref={chartCanvasRef} aria-label="live price chart" />
            </div>
            </>
          ) : (
            <div className="empty-state">No chart data available.</div>
          )}
        </section>
      </motion.section>
    </>
  );
};

export default CryptoData;
