# Backtesting

> Role: **calibrate parameter ranges** and stress-test behavior under real crises.
> Structure is proven in [MATH.md](MATH.md); this document answers only
> "are the chosen ranges acceptable?"
> Unified dataset: `backtest_out/all_backtests.csv` (302 trading days).
> Regenerate: `python merge_backtests.py`.

## What was tested

**Four currency collapses** (monthly, ratio-stability study):
Venezuela 2016–19, Argentina 2018–23, Iran 2018–20, Russia 2014–15.

**Three daily-frequency crises** (full engine replay, current parameters):

| Event | Days | Vol peak | Character |
|---|---|---|---|
| 2020-04 oil crash | 79 | 349% | deepest single shock (negative WTI) |
| 2025-06 Israel–Iran war | 41 | 54% | shortest (12 days), sharpest onset |
| 2026 US–Iran war | 182 | 112% | longest (7 months), repeated pulses, Hormuz blockade |

Sources: World Bank Pink Sheet, FRED daily WTI/Brent, bluelytics ARS,
Frankfurter/ECB RUB. VES/IRR parallel rates are approximate public
milestones — display only, never used in calibration.

## Headline result

**The system never fully failed.** Across 302 trading days spanning the
deepest oil shock in history and a 7-month war: 0 refusal days.
Worst case was always L3 split — vouching the stable side only.

## By event level (volatility-based grading)

| Level | Definition | Days | Normal | L3 split | Refused | t+1 coverage |
|---|---|---|---|---|---|---|
| normal | vol < 40% | 67 | **100%** | 0% | 0% | 100% |
| elevated | 40–60% | 89 | **100%** | 0% | 0% | 99% |
| crisis | 60–100% | 81 | 38% | 62% | 0% | 100% |
| extreme | ≥ 100% | 65 | 0% | **100%** | 0% | n/a (no normal quotes) |

Service quality tracks market uncertainty exactly — the intended design.

## Key findings

**1. Barter ratios stay bounded through currency collapse.**
Collapse-window ratio CV: 15.6–21.9%, same order as calm periods
(9.2–16.6%). Currencies moved 2× to 1.5-million-×. Ratio volatility comes
from global supply/demand, not local money. The premise holds.

**2. The real risk is global commodity shocks, not local collapse.**
All extreme-band days trace to global events (2008, 2020, 2022, 2026).

**3. Daily data is a hard requirement.**
At the tight cap (hi/lo ≤ 1.40), monthly-frequency data pushes δ_vol near
the cap even in calm times. The gap lands on the slowest movers (grains),
which tolerate age best — the right failure order.

**4. Narrow-band-or-silent works.**
Every emitted quote had 100% t+1 forward coverage across all three crises.
The system speaks less in chaos and is never wrong.

**5. Quote validity is short: ~1–3 days.**
t+1 ≈ 99–100%, t+3 ≈ 88–100%, t+5 ≈ 82–97%. The reference price is a
*today* instrument; the UI says so.

**6. Oscillation is harder than a one-directional spike.**
In the 2026 war, the April–June sawtooth ($93–131, no direction) had a
lower normal-quote rate (56%) than the initial surge. Trend-following
handles directional moves; choppy markets can only widen the band.

## Reproduce

```bash
python backtest.py               # four-country collapse windows, δ calibration
python backtest_covid2020.py     # 2020 oil crash, daily
python backtest_iran2025.py      # 2025 Israel–Iran conflict, daily
python backtest_iranwar2026.py   # 2026 US–Iran war, daily
python merge_backtests.py        # unified dataset + level grading
```

## Known limits

- 2026-war backtest treats monthly anchors as daily-fresh (target state
  with a daily pipeline; grain daily sources not yet wired).
- VES/IRR parallel rates approximate. Local basis unmeasured — needs
  field data from target regions. RUB ends 2022-03 (ECB suspension).
