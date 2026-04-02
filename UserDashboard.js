import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import Navbar from '../components/Navbar';

const FEATURED_ASSETS = ['BTC', 'ETH', 'XRP'];

const News = () => {
  const [allArticles, setAllArticles] = useState([]);
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // all, btc, eth, xrp, others

  const applyFilter = useCallback((collection, scope) => {
    if (scope === 'all') {
      return collection;
    }

    if (scope === 'others') {
      return collection.filter(
        (article) => !article.assetTags.some((tag) => FEATURED_ASSETS.includes(tag)),
      );
    }

    return collection.filter((article) => article.assetTags.includes(scope.toUpperCase()));
  }, []);

  const loadNews = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('https://min-api.cryptocompare.com/data/v2/news/?lang=EN');

      if (!response.ok) {
        throw new Error('Unable to load crypto news right now.');
      }

      const payload = await response.json();

      if (!payload?.Data || !Array.isArray(payload.Data)) {
        throw new Error('Unexpected response when fetching crypto news.');
      }

      const articles = payload.Data.map((item) => {
        const rawCategories =
          typeof item.categories === 'string'
            ? item.categories.split('|').map((cat) => cat.trim().toUpperCase())
            : [];

        const rawTags = Array.isArray(item.tags)
          ? item.tags.map((tag) => String(tag).trim().toUpperCase())
          : [];

        const assetTags = Array.from(
          new Set(rawCategories.concat(rawTags).filter(Boolean)),
        );

        const stripHtml = (text = '') => text.replace(/<[^>]*>/g, '');

        const summaryText = stripHtml(item.body ?? item.title ?? '');

        return {
          id: item.id ?? `${item.title}-${item.published_on}`,
          title: item.title ?? 'Untitled article',
          source: item.source_info?.name ?? 'Unknown source',
          publishedAt: item.published_on
            ? item.published_on * 1000
            : item.published_at ?? item.datetime ?? Date.now(),
          sentiment: item.sentiment ?? item.sentimentTitle ?? 'neutral',
          assetTags: assetTags.length ? assetTags : ['CRYPTO'],
          summary: summaryText.length > 0 ? summaryText : 'No summary provided.',
          url: item.url ?? item.guid ?? '#',
        };
      }).filter((article) => article.url && article.title);

      setAllArticles(articles);
      setArticles(articles);
    } catch (err) {
      setError(err?.message ?? 'Failed to load news articles.');
      setAllArticles([]);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNews();
  }, [loadNews]);

  useEffect(() => {
    setArticles(applyFilter(allArticles, filter));
  }, [allArticles, filter, applyFilter]);

  const getSentimentColor = (sentiment) => {
    // 3-class sentiment system: negative, neutral, positive
    // Legacy "super positive"/"super negative" are handled via normalization
    const normalized = String(sentiment || '').toLowerCase().trim();
    if (normalized.includes('positive') || normalized === 'pos') {
      return '#4ade80';
    }
    if (normalized.includes('negative') || normalized === 'neg') {
      return '#ef4444';
    }
    return '#d1d5db'; // neutral or unknown
  };

  const formatDate = (input) => {
    try {
      let date;

      if (typeof input === 'number') {
        date = new Date(input > 1e12 ? input : input * 1000);
      } else {
        const parsed = Date.parse(input);
        date = Number.isNaN(parsed) ? new Date() : new Date(parsed);
      }

      const now = new Date();
      const diffMs = now - date;
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHours / 24);

      if (diffHours < 1) return 'Just now';
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString();
    } catch {
      return 'Recent';
    }
  };

  const sentimentLabel = (sentiment) => {
    if (!sentiment) {
      return 'neutral';
    }
    return sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
  };

  return (
    <>
      <Navbar />
      <motion.section
        className="page-shell page-shell--wide"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65 }}
        aria-labelledby="news-heading"
      >
        {loading && !error && articles.length === 0 ? (
          <div className="hero-skeleton" role="status" aria-live="polite">
            <span className="hero-skeleton__eyebrow" />
            <span className="hero-skeleton__title" />
            <span className="hero-skeleton__subtitle" />
          </div>
        ) : (
          <header className="page-header" style={{ alignItems: 'center', textAlign: 'center' }}>
            <span className="page-header__eyebrow">Market briefing</span>
            <h1 id="news-heading" className="page-header__title">Crypto News</h1>
            <p className="page-header__subtitle" style={{ margin: '0 auto', maxWidth: '720px' }}>
              {error
                ? 'We could not load the latest headlines right now. Please try again shortly.'
                : 'Latest cryptocurrency headlines with sentiment indicators for Bitcoin, Ethereum, XRP and the broader market.'}
            </p>
          </header>
        )}

        <div className="page-actions" style={{ justifyContent: 'flex-start' }}>
          {['all', 'btc', 'eth', 'xrp', 'others'].map((asset) => (
            <button
              key={asset}
              type="button"
              className={`btn ${filter === asset ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter(asset)}
            >
              {asset === 'all'
                ? 'All News'
                : asset === 'others'
                  ? 'Other Crypto'
                  : asset.toUpperCase()}
            </button>
          ))}
        </div>

        <section className="content-panel" aria-label="News articles">
          {loading && <div className="empty-state">Loading news articles…</div>}
          {error && (
            <div className="empty-state" style={{ borderStyle: 'solid', color: '#f97316' }}>
              {error}
            </div>
          )}
          {!loading && !error && articles.length === 0 && (
            <div className="empty-state">
              No articles found for {filter === 'all' ? 'this filter' : filter.toUpperCase()}.
            </div>
          )}

          {!loading &&
            !error &&
            articles.map((article, index) => (
              <motion.article
                key={article.id}
                className="glass-card"
                initial={{ opacity: 0, x: -18 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + index * 0.1 }}
                onClick={() => article.url && window.open(article.url, '_blank', 'noopener')}
                style={{ cursor: article.url ? 'pointer' : 'default', display: 'grid', gap: '1rem' }}
              >
                <div className="chip-row" style={{ justifyContent: 'space-between' }}>
                  <span
                    className="badge"
                    style={{
                      background: `${getSentimentColor(article.sentiment)}33`,
                      color: getSentimentColor(article.sentiment),
                    }}
                  >
                    {sentimentLabel(article.sentiment)}
                  </span>
                  <span className="chip">
                    {article.assetTags?.slice(0, 2).join(' / ') || 'CRYPTO'}
                    {article.assetTags?.length > 2 ? ' +' : ''}
                  </span>
                </div>
                <div>
                  <h2 className="content-panel__title" style={{ marginTop: 0 }}>
                    {article.title}
                  </h2>
                  <p className="content-panel__text" style={{ marginTop: '0.75rem' }}>
                    {article.summary}
                    {article.summary && article.summary.length >= 280 ? '…' : ''}
                  </p>
                </div>
                <div
                  className="page-actions"
                  style={{ justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}
                >
                  <span className="content-panel__text" style={{ fontSize: '0.85rem', margin: 0 }}>
                    {article.source} • {formatDate(article.publishedAt)}
                  </span>
                  <span className="btn btn-ghost" style={{ padding: '0.5rem 1.1rem' }}>
                    Read more →
                  </span>
                </div>
              </motion.article>
            ))}
        </section>
      </motion.section>
    </>
  );
};

export default News;

