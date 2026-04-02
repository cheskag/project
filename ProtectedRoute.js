import React from 'react';

const Footer = () => (
  <footer className="site-footer" aria-label="Powered by CoinGecko">
    <div className="site-footer__inner">
      <span className="site-footer__text">Powered by CoinGecko</span>
      <img
        src="/coin.jpg"
        alt="CoinGecko logo"
        className="site-footer__logo"
        width="32"
        height="32"
        loading="lazy"
      />
    </div>
  </footer>
);

export default Footer;

