import React from 'react';
import Navbar from '../components/Navbar';
import './faq.css';
import { motion } from 'framer-motion';

function Faq() {
  const faqSections = [
    {
      title: 'Platform essentials',
      intro: 'Understand what CryptoGauge offers and how the prediction engine works.',
      items: [
        {
          question: 'What is CryptoGauge?',
          answer:
            'CryptoGauge is an analytics workspace that combines live market feeds, curated sentiment, and forecasting to help you quickly evaluate Bitcoin, Ethereum, XRP, and broader market trends.',
        },
        {
          question: 'How fresh is the market data?',
          answer:
            'Price candles refresh directly from CoinGecko every few seconds. Sentiment scores and news headlines update whenever new signals arrive from our data pipeline or when you refresh the News and Prediction views.',
        },
        {
          question: 'Can I rely on the predictions for trading?',
          answer:
            'Forecasts are scenario estimates from machine-learning models. Treat them as a decision aid—always double-check fundamentals, manage risk, and never invest money you cannot afford to lose.',
        },
        {
          question: 'How does the sentiment scoring engine work?',
          answer:
            'We blend transformer-based models with rule-based classifiers (RoBERTa, VADER) to evaluate tone in news and social chatter. Scores are normalised so that you can compare assets on the same scale.',
        },
        {
          question: 'Which stack powers the platform?',
          answer:
            'The frontend runs on React with framer-motion, the backend aggregates data through Node.js/Express, machine-learning services run in Python, and persistent storage uses PostgreSQL for users plus MongoDB for datasets.',
        },
      ],
    },
    {
      title: 'Prediction workflow',
      intro: 'Dive deeper into backtesting, intervals, and accuracy metrics.',
      items: [
        {
          question: 'What does “interval” mean in the prediction lab?',
          answer:
            'Interval controls the forward-looking window (in days) the system attempts to forecast. Shorter intervals emphasise short-term sentiment and volatility; longer intervals blend momentum with macro indicators.',
        },
        {
          question: 'What is the “backtrack” slider for?',
          answer:
            'Backtrack limits how much historical data is analysed when building each forecast scenario. Use smaller values for a nimble view, larger ranges when you want the model to smooth noise and capture macro moves.',
        },
        {
          question: 'Where do accuracy metrics come from?',
          answer:
            'Accuracy panels compare past predictions against actual market closes using rolling windows. Metrics like precision, recall, and F1 score show how well the classifier caught upward vs. downward movements.',
        },
        {
          question: 'Why might predictions differ from real prices?',
          answer:
            'Crypto markets react instantly to news, regulation, and liquidity shocks. Predictions lag when new information has not yet entered the model, so always cross-check with live charts and order books.',
        },
      ],
    },
  ];

  const quickStartSteps = [
    {
      title: '1. Create your account',
      detail:
        'Register with a valid email, confirm reCAPTCHA, and keep your credentials secure. Once logged in the dashboard opens automatically.',
    },
    {
      title: '2. Explore the dashboard',
      detail:
        'Review the quick links for News, Prediction Lab, Community, and Crypto Data. Each module surfaces the same assets for a consistent workflow.',
    },
    {
      title: '3. Check the latest news & sentiment',
      detail:
        'Open the News page, pick BTC, ETH, XRP, or Other Crypto, and skim the auto-tagged sentiment to understand market mood.',
    },
    {
      title: '4. Run a prediction scenario',
      detail:
        'In the Prediction Lab choose your coin, adjust the interval and backtrack sliders, and inspect both the insights and historical table.',
    },
    {
      title: '5. Share and learn in the community',
      detail:
        'Create a new post in Community to discuss signals, ask for feedback, or log trades. Remember to follow the community guidelines.',
    },
  ];

  const glossary = [
    {
      term: 'Altcoin',
        definition: 'Any cryptocurrency that is not Bitcoin. Often grouped by sector (DeFi, Layer 2, etc.).',
      category: 'Market Structure',
      icon: '🪙',
    },
    {
      term: 'Bearish / Bullish',
      definition: 'Bearish means expecting price declines; bullish indicates confidence that price will rise.',
      category: 'Market Sentiment',
      icon: '📉',
    },
    {
      term: 'FOMO (Fear Of Missing Out)',
      definition: 'The urge to buy assets after strong pumps—often leads to late entries and bad risk.',
      category: 'Psychology',
      icon: '⚠️',
    },
    {
      term: 'HODL',
      definition: 'A mantra meaning “Hold On for Dear Life,” used when investors keep positions through volatility.',
      category: 'Strategy',
      icon: '🛡️',
    },
    {
      term: 'Market Cap',
      definition: 'Total value of a crypto asset: current price multiplied by circulating supply.',
      category: 'Market Structure',
      icon: '🏦',
    },
    {
      term: 'Resistance / Support',
      definition: 'Resistance is a price ceiling where selling pressure appears; support is a floor where buyers step in.',
      category: 'Technical Analysis',
      icon: '📐',
    },
    {
      term: 'Volatility',
      definition: 'The degree of price fluctuations over time. High volatility means rapid and large price swings.',
      category: 'Risk',
      icon: '⚡',
    },
    {
      term: 'Whale',
      definition: 'A trader or wallet holding a very large amount of crypto whose moves can shake the market.',
      category: 'Market Participants',
      icon: '🐋',
    },
  ];

  return (
    <>
      <Navbar />
      <motion.section
        className="page-shell"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        aria-labelledby="faq-heading"
      >
        <header className="page-header" style={{ alignItems: 'center', textAlign: 'center' }}>
          <span className="page-header__eyebrow">Knowledge base</span>
          <h1 id="faq-heading" className="page-header__title">Frequently Asked Questions</h1>
          <p className="page-header__subtitle" style={{ margin: '0 auto', maxWidth: '720px' }}>
            Short answers for the most common questions about the CryptoGauge platform, our data sources, and prediction workflow.
          </p>
        </header>

        <div className="faq-sections">
          {faqSections.map((section, sectionIndex) => (
            <section key={section.title} className="faq-section" aria-labelledby={`faq-section-${sectionIndex}`}>
              <div className="faq-section__header">
                <h2 id={`faq-section-${sectionIndex}`}>{section.title}</h2>
                <p>{section.intro}</p>
              </div>
              <div className="faq-container" role="list">
                {section.items.map((item, index) => (
                  <motion.article
                    key={item.question}
                    role="listitem"
                    className="faq-card"
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.3 }}
                    transition={{ delay: 0.05 * (index + 1) }}
                  >
                    <h3>{item.question}</h3>
                    <p>{item.answer}</p>
                  </motion.article>
                ))}
              </div>
            </section>
          ))}

          <section className="faq-section" aria-labelledby="quick-start-heading">
            <div className="faq-section__header">
              <h2 id="quick-start-heading">Quick start guide</h2>
              <p>Follow these steps to make the most of CryptoGauge within minutes.</p>
            </div>
            <ol className="faq-steps">
              {quickStartSteps.map((step) => (
                <li key={step.title}>
                  <strong>{step.title}</strong>
                  <span>{step.detail}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="faq-section" aria-labelledby="glossary-heading">
            <div className="faq-section__header">
              <h2 id="glossary-heading">Crypto terminology for beginners</h2>
              <p>
                New to trading? Start with these common expressions so you can follow market commentary with confidence.
              </p>
            </div>
            <div className="terminology-grid">
              {glossary.map((entry) => (
                <div key={entry.term} className="terminology-card">
                  <div className="terminology-card__meta">
                    <span className="terminology-card__icon" aria-hidden="true">
                      {entry.icon}
                    </span>
                    <span className="terminology-card__tag">{entry.category}</span>
                  </div>
                  <h3>{entry.term}</h3>
                  <p>{entry.definition}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </motion.section>
    </>
  );
}

export default Faq;