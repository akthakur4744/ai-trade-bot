# Trading Strategy — Living Rulebook

> The binding rulebook. Every agent run reads this before scoring signals.
> Rules are promoted here only after validation in [LEARNINGS.md](LEARNINGS.md).
> Every rule cites the config key it maps to in `config/default.yaml`.

## Active Rules

<!-- Append rules below as they graduate from LEARNINGS.md via weekly review -->

### R000 — Baseline filters (seeded from config)
- **Confidence floor:** `confidence >= 0.65` → `scoring.min_confidence`
- **Market confirmation:** `>= 0.6` → `scoring.min_market_confirmation`
- **Liquidity:** `>= 0.6` → `scoring.min_liquidity_score`
- **Risk penalty cap:** `<= 0.4` → `scoring.max_risk_penalty`
- **Bear-regime bullish cap:** confidence capped at `0.6` when regime == bear → `scoring.bear_regime_confidence_cap`

*Why:* Starting thresholds from the original alpha model. Never bypass.
*How to apply:* Reject any signal failing any one. Surface reason in `risks`.

---

## Retired Rules

<!-- Rules that failed in the wild. Keep for audit. -->
