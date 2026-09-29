# Data Sources & Daily Pack Pipeline

> [README](../README.md) · [Design](DESIGN.md) · [Math](MATH.md) · [Backtesting](BACKTESTING.md) · [Data Sources](DATA_SOURCES.md)

---

Server role is minimized to "pack builder": GitHub Actions cron +
Releases/IPFS distribution. Zero cost, CDN-friendly, censorship-resilient.

## Requirements

- **Daily frequency** (hard requirement at the tight band cap)
- **Spot benchmarks**, never far-dated futures
- **Multi-source** wherever possible (δ_data + manipulation resistance)
- **Free / near-zero cost**, reachable from target regions

## Probed availability (empirically tested)

| Source | Coverage | Frequency | Notes |
|---|---|---|---|
| FRED | WTI, Brent, Henry Hub spot | daily | plain CSV, no anti-bot |
| gold-api.com | gold, silver, copper, Pt, Pd | real-time | no key |
| World Bank / FRED mirror | all anchors | monthly | fallback + history |
| EIA | energy spot | daily | free key; second energy source |

Blocked in practice: stooq, Yahoo, Nasdaq Data Link, USDA MARS.

## The gap lands on the slowest movers

Daily gaps: grains, aluminum, urea. But these are the lowest-volatility
anchors (wheat ~15% ann. vs crude 20–35%+). Since δ_vol = 1.65·σ·√(T/20),
slow movers tolerate data age. Monthly grains remain quotable in normal
times; they go silent first in crises — the right failure order.

## Closing the gap

1. **Tiered strategy (v0.2, zero cost):** daily for high-volatility,
   monthly for low-volatility + crisis warnings.
2. **Free-tier quota discipline (v0.2–0.3):** freemium APIs (~100 calls/mo)
   suffice — one batched pull per day, stored and republished as the pack.
3. **CPI extrapolation for stable markets:** benchmark-year measurements
   (ICP surveys, national statistics) + sectoral CPI extrapolation, with
   δ_est growing as √Δt from last survey. Valid only in stable-currency
   markets — extrapolation breaks precisely where the tool is needed most,
   so it serves as a *reference frame*, never as local pricing.

**Explicitly rejected: user-reported prices.** Collection requires storage,
moderation, anti-fraud, and compliance infrastructure whose cost dwarfs the
value; unstandardized reports can't form a rigorous measurement system; and
in collapsing states, user economic data is a safety liability. The system
stays read-only, stateless, and accountable to public statistics.

## Pipeline

```
collect_daily.py   FRED energy + gold-api metals + FRED/WB monthly
build_pack.py      unit normalization, multi-source median, rolling vol
anchor_ots.py      OpenTimestamps Bitcoin anchoring (optional, zero-cost)
```

Distribution: GitHub Releases (`latest` tag) + IPFS + peer transfer.

## Trust root: public history, not private keys

The daily pack carries a `code_commit` field — the git commit of the build.
Trust chain is **the public history itself**:

- git's hash chain makes history tamper-evident;
- any mirror is self-authenticating (SHA-addressed);
- settlement delay: clients only accept commits that have existed ≥ 24h
  on multiple independent mirrors — attacks are publicly visible *before*
  use.

Fairness comes from "wrongdoing is a public broadcast," not from trusting
the operator. An optional OpenTimestamps anchor to Bitcoin answers exactly
one question: "was the history rewritten?" — with a proof that not even
the platform could produce retroactively. No private keys anywhere.

Client-side verification: `barter/gitaudit.py`.

## Risks

Single-source manipulation → median + 3σ trimming + δ_data floor.
GitHub blocked → IPFS + peer transfer (packs are plain JSON).
Free-tier termination → degrade to monthly for affected anchors only.
