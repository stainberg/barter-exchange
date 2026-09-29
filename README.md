# Barter Exchange Reference

**A neutral reference for barter when money stops working.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![ci](https://github.com/stainberg/barter-exchange/actions/workflows/ci.yml/badge.svg)](https://github.com/stainberg/barter-exchange/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/stainberg/barter-exchange/main/badges/coverage.json)](https://github.com/stainberg/barter-exchange/actions/workflows/ci.yml)
[![datapack-daily](https://github.com/stainberg/barter-exchange/actions/workflows/datapack-daily.yml/badge.svg)](https://github.com/stainberg/barter-exchange/actions/workflows/datapack-daily.yml)
[![Latest data pack](https://img.shields.io/badge/datapack-daily-brightgreen)](https://github.com/stainberg/barter-exchange/releases/tag/latest)

## Is this for you?

You are a farmer with wheat. A driver has diesel. Your country's currency
lost half its value this year, so neither of you trusts a price in it.
**What you need is not a price — it's a fair ratio.**

This tool answers: *"How many liters of diesel is one tonne of my wheat
worth, approximately, today?"*

It gives you two numbers:

- **Reference price** — yesterday's fair ratio, anchored to global commodity
  spot prices (your local currency is never part of the calculation);
- **Negotiation band** — the acceptable range around it. If the tool can't
  produce a tight band, it says so instead of guessing.

It never touches goods, money, or the deal itself. **It's a ruler, not a
currency.**

## Quick start (2 minutes, no install)

Requirements: Python 3.9+. The engine is **pure standard library** — no pip
install needed.

```bash
git clone https://github.com/stainberg/barter-exchange.git
cd barter-exchange

# Download the latest daily data pack
curl -L -o data/datapack_latest.json \
  https://github.com/stainberg/barter-exchange/releases/download/latest/datapack-latest.json

# How much silver for 1 oz of gold?
python3 -m barter.cli gold 1 silver --lang en
```

Output:

```
========================================================
  Reference price: 1 oz gold ≈ 67.7 oz silver
  (anchored to global spot, 2026-09-28)
  Negotiation band: 61.8 ~ 74.3 oz silver  (hi/lo = 1.20x)
========================================================
  Data freshness: A:fresh / B:fresh
  ※ Reference band for barter negotiation — not a price quote.
```

More:

```bash
python3 -m barter.cli wheat 1 diesel --lang en               # grain → fuel
python3 -m barter.cli eggs 30 flour --qty-b 100 --lang en    # is this offer fair?
python3 -m barter.cli --list --lang en                       # all goods
python3 -m barter.cli wheat 1 diesel --detail --lang en      # full breakdown
```

If a quote is refused, the tool tells you why (stale data, extreme
volatility) and what to do. That honesty is the point.

## Documentation

| Doc | Content |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | Design philosophy — what it is, what it is not, and why |
| [docs/MATH.md](docs/MATH.md) | Formal proofs of core invariants (T1–T9, E1–E6) |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | Calibration: 4 currency collapses + 3 oil crises — 302 days, zero failures |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Data pipeline, sources, trust model |

## Three rules

1. **Structure is proven** ([MATH.md](docs/MATH.md)); backtests only
   calibrate parameters.
2. **Band width ≤ 40%** — degrade or stay silent rather than fake precision.
3. **Public-history trust** — every data pack binds to a git commit; no
   private keys anywhere in the system.

## Keywords

barter, barter trade, exchange reference, currency collapse,
hyperinflation, commodity-backed, price anchor, negotiation band,
reference price, fair trade ratio, Venezuela, Argentina, Iran, Russia,
sanctions, parallel exchange rate, commodity index, unit of account,
trueque, hiperinflación, precio de referencia, бартер, гиперинфляция,
تهاتر, تورم شدید, مقايضة, 以物换物, 恶性通胀

## License

Apache 2.0 — see [LICENSE](LICENSE).
