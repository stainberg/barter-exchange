# Backtesting

> Role: **calibrate parameter ranges** and stress-test behavior under real crises.
> Structure is proven in [MATH.md](MATH.md); this document answers only
> "are the chosen ranges acceptable?"

## What was tested

**Four currency collapses** (Venezuela 2016–19, Argentina 2018–23,
Iran 2018–20, Russia 2014–15), three phases each (pre / collapse /
stabilized), plus two daily-frequency crisis studies:

- **2020-04 oil crash** (WTI negative, Brent −85%, annualized vol peak 349%)
- **2025-06 Israel–Iran conflict** (Brent +13.5% then −15% in 12 days)

Sources: World Bank Pink Sheet (monthly spot benchmarks), FRED daily
WTI/Brent, bluelytics ARS official/blue, Frankfurter/ECB RUB.
VES/IRR parallel rates are approximate public milestones — used only to
display collapse magnitude, never in calibration.

## Key findings

**1. Barter ratios stay bounded through currency collapse.**
Ratio dispersion (CV) in collapse windows: 15.6–21.9% — same order as
pre-collapse (9.2–16.6%) and post (9.9–19.1%). Meanwhile the currencies
themselves moved 2× to 1.5-million-×. Ratio volatility comes from global
commodity supply/demand, not from the local currency. That is the entire
premise, confirmed.

**2. The real risk is global commodity shocks, not local collapse.**
All extreme band-widening events trace to 2008, 2020-04, 2022 — global
events. The tool's failure mode is a supply-chain crisis, exactly where
the degradation ladder is designed to engage.

**3. Daily data is a hard requirement at the tight band cap.**
With the hi/lo ≤ 1.40 constraint, monthly-frequency data alone pushes δ
near the cap even in calm times (the √T term in δ_vol). The 2025 Iran
conflict at 14-day data age: δ reached 37.9% of the old cap — within
2 points of refusal. Same conflict with daily data: comfortable.

**4. Narrow-band-or-silent works.**
Replaying both crises with the tight cap: Iran conflict quoted normally on
68% of days; the 2020 crash on 14%. **But every quote emitted had 100%
t+1 forward coverage.** The system speaks less in chaos and is never wrong.

**5. Quote validity is short.**
Forward coverage: t+1 ≈ 96–100%, t+3 ≈ 88%, t+5 ≈ 82%. A reference price
is a *today* instrument; the UI must say so.

## Reproduce

```bash
python backtest.py            # four-country windows, ratio stability, δ calibration
python backtest_iran2025.py   # 2025 Israel–Iran conflict, daily
python backtest_covid2020.py  # 2020 oil crash stress test, daily
```

## Known limits

- VES/IRR parallel-rate series are approximate (no free reliable history).
- Global benchmark vs. local-traded basis is unmeasured — requires
  field data from target regions (the last uncovered piece).
- RUB series ends 2022-03 (ECB suspension).
