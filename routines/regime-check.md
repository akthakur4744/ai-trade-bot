# Regime Check

## When to run
- Weekly (Sunday)
- Whenever VIX moves > 15% in a day
- After any FOMC / RBI event
- Whenever the `macro-regime-detector` skill reports a transition

## Steps

1. Invoke `macro-regime-detector` skill; capture regime label + confidence.
2. Compare to current regime stored in `src/regime/` (HMM state).
3. If HMM disagrees with the cross-asset skill, dump both confidence scores and the features driving the divergence — do **not** override automatically.
4. Cross-check: yield curve, RSP/SPY, credit spreads, size factor, equity-bond correl.
5. **If transition confirmed (both agree):**
   - Bear → update `config/*.yaml` to cap bullish confidence at 0.6 (per `CLAUDE.md`).
   - Risk-on → consider relaxing cap; do not exceed existing max_capital_deployed.
6. Flag which of the 8 strategies are regime-appropriate vs not; recommend pausing unsuitable ones.

## Output

Regime label, confidence, transition Y/N, proposed config diff (unified format). Wait for user approval before applying.
