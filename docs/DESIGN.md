# Design

> [README](../README.md) · [Design](DESIGN.md) · [Math](MATH.md) · [Backtesting](BACKTESTING.md) · [Data Sources](DATA_SOURCES.md)

---

## Problem

When a currency collapses, what breaks is not trade but the **price signal**.
Both sides of a barter know their goods have value; what they lack is a shared,
neutral answer to *"how much of yours for how much of mine?"*

## What this tool is

A **barter conversion ruler**. Input both goods; get:

- **Reference price** — yesterday's fair ratio, anchored to global commodity
  spot benchmarks (never to any collapsing currency);
- **Negotiation band** — the acceptable range around it, hard-capped at
  hi/lo ≤ 1.40.

It never touches goods, money, matching, or settlement. A ruler, not a currency.

## Core decisions

**1. Anchor to global commodity spot prices, never to collapsing currency.**
Local fiat enters no formula; it cancels in the ratio (proof: T1, MATH.md).
Monetary noise excluded by construction; real scarcity signals preserved.

**2. A band, never a point.**
Precise values are false certainty. The band width itself is information —
a widening band warns of market stress. If a narrow band (≤ 40% full width)
cannot be produced, the tool degrades or stays silent rather than fake
precision. Silence over misleading.

**3. Degradation ladder, not binary failure.**

```
L0  normal quote
L1  band widens + caution
L2  trend-following center (directional move ≠ noise)
L3  split quote: vouch only the stable side
L4  full refusal
```

Refusal only when nothing referenceable remains. One commodity's collapse
never poisons unrelated pairs — the notional unit is transient per quote.

**4. Two measurement frames, never mixed without penalty.**
Benchmark frame (hub spot prices) and PPP frame (multi-region sampled actual
prices) are two coordinate systems. Within-frame ratios inherit correlated
errors that cancel; cross-frame ratios carry a systematic, measurable bias
and pay δ_frame (proof: T9, MATH.md).

**5. Public history as trust root — no private keys.**
Every data pack binds to a git commit. Clients verify existence, settlement
(≥ 24h), and multi-mirror agreement. Wrongdoing is a public broadcast, not a
hidden act. OpenTimestamps anchors the history to Bitcoin as an existence
proof that survives even the platform.

**6. Structure is proven; backtests only calibrate parameters.**
See [MATH.md](MATH.md) (T1–T9, E1–E6) and [BACKTESTING.md](BACKTESTING.md).

## Commodity taxonomy

Anchors (global benchmarks): wheat, rice, maize, soybean oil, sugar, crude
oil, gold, silver, copper, aluminum, urea.

Linked goods hang off anchors via coefficients K (`price = anchor × K`),
calibratable on-device. Perishables get a wider base band; seasonal goods
need season-split K. Far-dated futures are forbidden as anchors — barter
prices the deliverable-now, not expectations.

## Data architecture

Three layers, all public; no user data, ever:

1. **Global anchors (daily)** — FRED spot / gold-api / World Bank;
2. **K coefficients (annually)** — structural ratios (milling, refining,
   feed conversion); physics, not finance;
3. **CPI extrapolation** — benchmark-year measurement + sectoral CPI
   extrapolation, with δ_est growing as √Δt from last survey. Valid only in
   stable-currency markets; a reference frame, never local pricing.

The local basis (how much a good actually trades above/below the global
anchor in a specific town) is deliberately left to negotiation — that
residual is the trader's skill, not the tool's failure.

## Non-goals (v1)

No accounts, no matching, no chat, no fiat display, no non-tradables
(housing, local services, electricity).
