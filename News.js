:root {
    --faq-card-bg: rgba(15, 23, 42, 0.78);
    --faq-border: rgba(148, 163, 184, 0.18);
    --faq-shadow: 0 18px 40px rgba(15, 23, 42, 0.35);
  }
  
.faq-sections {
  display: flex;
  flex-direction: column;
  gap: 2.75rem;
}

.faq-section {
  display: grid;
  gap: 1.5rem;
}

.faq-section__header {
  display: grid;
  gap: 0.5rem;
  text-align: center;
  max-width: 760px;
  margin: 0 auto;
}

.faq-container {
  display: grid;
  gap: 1.25rem;
}

@media (min-width: 768px) {
  .faq-container {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1080px) {
  .faq-container {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.faq-card {
  background: var(--faq-card-bg);
  border-radius: 18px;
  border: 1px solid var(--faq-border);
  padding: 1.5rem;
  box-shadow: var(--faq-shadow);
  backdrop-filter: blur(14px);
  display: grid;
  gap: 0.65rem;
  text-align: left;
}

.faq-card h3 {
  margin: 0;
  font-size: 1.1rem;
}

.faq-card p {
  margin: 0;
  line-height: 1.6;
  color: var(--text-muted, #cbd5f5);
  font-size: 0.95rem;
}

.faq-card .highlight {
  color: var(--accent-blue, #60a5fa);
  font-weight: 600;
}

.faq-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 1rem;
  counter-reset: step-counter;
}

.faq-steps li {
  background: var(--faq-card-bg);
  border: 1px solid var(--faq-border);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  box-shadow: var(--faq-shadow);
  backdrop-filter: blur(10px);
  display: grid;
  gap: 0.5rem;
  position: relative;
}

.faq-steps li::before {
  counter-increment: step-counter;
  content: counter(step-counter);
  position: absolute;
  top: 1.25rem;
  left: 1.25rem;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  font-weight: 600;
}

.faq-steps li strong {
  display: block;
  padding-left: 3rem;
  font-size: 1rem;
}

.faq-steps li span {
  padding-left: 3rem;
  color: var(--text-muted, #d1d5f8);
  line-height: 1.6;
}

.terminology-grid {
  display: grid;
  gap: 1.2rem;
}

@media (min-width: 768px) {
  .terminology-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.terminology-card {
  background: var(--faq-card-bg);
  border: 1px solid var(--faq-border);
  border-radius: 18px;
  padding: 1.4rem;
  box-shadow: var(--faq-shadow);
  backdrop-filter: blur(12px);
  display: grid;
  gap: 0.65rem;
}

.terminology-card h3 {
  margin: 0;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent-blue, #60a5fa);
}

.terminology-card p {
  margin: 0;
  line-height: 1.6;
  color: var(--text-muted, #cbd5f5);
}

.terminology-card__meta {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}

.terminology-card__icon {
  font-size: 1.35rem;
  filter: drop-shadow(0 2px 6px rgba(15, 23, 42, 0.3));
}

.terminology-card__tag {
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-blue, #60a5fa);
  background: rgba(96, 165, 250, 0.15);
  border: 1px solid rgba(96, 165, 250, 0.25);
}