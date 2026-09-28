# Design Philosophy

> The barter reference tool: a ruler, not a currency.

## The problem

When a currency collapses, what breaks is not trade itself but the **price signal**.
A merchant holding wheat and a driver holding diesel both know their goods have
value — what they lack is a shared, neutral answer to *"how much of yours for
how much of mine?"* Any price quoted in the local currency is meaningless within
weeks; official exchange rates diverge from reality by orders of magnitude.

## What this tool is

A **barter conversion ruler**. Input both goods; get:

- a **reference price** — yesterday's fair ratio, anchored to global spot benchmarks
- a **negotiation band** — the acceptable range around it (hard-capped at hi/lo ≤ 1.40)

It never touches goods, money, matching, or settlement. The notional unit exists
only for the duration of one calculation and is never shown to users.

## What it deliberately is not

- Not a pricing intermediary, marketplace, or broker
- Not a currency, unit of account, or store of value
- Not a payment or clearing system

This is why the tool carries almost no regulatory surface and almost no trust
burden: users need only trust that the *algorithm* is neutral, not that any
operator will honor redemption.

## Core design decisions and why

### 1. Anchored to global commodity spot prices — never to any collapsing currency

Fiat from a collapsing economy enters no formula. If a local currency appears at
all, it is a pure display-layer scaling factor that cancels in division
(proof: T1 in [MATH.md](MATH.md)). The system is immune to monetary noise by
construction; real scarcity signals (local premia) are preserved and shown, not
smoothed away.

### 2. A band, never a point

Precise values would be false certainty: data has noise, latency, and regional
dispersion. The band width itself is information — a suddenly widening band is a
market-health warning. The band is where negotiation happens.

**Hard constraint: band full-width ≤ 40% (hi/lo ≤ 1.40).** A range where the top
is 2.3× the bottom is not a price reference — it is noise. If the system cannot
produce a narrow band, it degrades or stays silent. Every number it does emit is
trustworthy. (Calibration: [BACKTESTING.md](BACKTESTING.md).)

### 3. Degradation ladder instead of binary failure

```
L0  normal quote
L1  band widens + caution warning        (volatility rising)
L2  trend-following center               (directional move ≠ noise)
L3  split quote: vouch only the stable side
    ("1t wheat ≈ X oz gold (trustworthy) — gold→diesel: negotiate locally")
L4  full refusal
```

Refusal happens only when nothing referenceable remains: stale data (>45d),
systemic shock (both sides spiking together), or no usable intermediary anchor.
Because the notional unit is transient, one commodity's collapse never poisons
unrelated pairs.

### 4. Honesty over availability

The system says "I don't know" rather than inventing precision. Every quote
ships with: data freshness, full δ decomposition, and the anchor chain.
Neutrality is enforced by auditability, not promises.

### 5. Mathematics must be provable; backtests only calibrate parameters

The calculation structure is theorem-proven ([MATH.md](MATH.md)):
numéraire invariance, band reciprocity (AB/BA consistency), transitivity,
monotonic honesty. Backtests (four currency collapses, the 2020 oil crash,
the 2025 Iran conflict) exist solely to calibrate empirical parameters —
band components, volatility windows, refusal thresholds.

## Commodity taxonomy

Anchors (global benchmark prices): wheat, rice, maize, soybean oil, sugar,
crude oil, gold, silver, copper, aluminum, urea.

Linked goods hang off anchors via coefficients K (`price = anchor × K`),
calibratable locally on-device. Perishables get a wider base band; seasonal
goods need season-split K. Far-dated futures are forbidden as anchors — barter
prices the deliverable-now, not expectations.

## Data pipeline

Daily pack built by GitHub Actions from free public sources (FRED, gold-api,
World Bank mirror), Ed25519-signed, distributed via Releases/IPFS/peer transfer.
Full analysis: [DATA_SOURCES.md](DATA_SOURCES.md).

## Non-goals (v1)

No accounts, no matching, no chat, no fiat display, no non-tradables
(housing, local services, electricity).
