# Data Sources & Daily Pack Pipeline

> Server role is minimized to "pack builder": GitHub Actions cron +
> Releases/IPFS distribution. Zero cost, CDN-friendly, censorship-resilient.

## Requirements (from design constraints)

- **Daily frequency is a hard requirement** (tight band cap → √T term dominates)
- **Spot benchmarks**, never far-dated futures
- **Multi-source** wherever possible (δ_data + manipulation resistance)
- **Free / near-zero cost**, reachable from target regions

## Probed availability (empirically tested, 2026-09)

| Source | Coverage | Frequency | Notes |
|---|---|---|---|
| FRED | WTI, Brent, Henry Hub spot | **daily** | plain CSV, no anti-bot |
| gold-api.com | gold, silver, copper, Pt, Pd | **real-time** | no key |
| World Bank / FRED mirror | all anchors | monthly | fallback + history |
| EIA | energy spot | daily | free key; second energy source |

Blocked in practice: stooq (PoW then deny), Yahoo, Nasdaq Data Link,
crypto exchange APIs from this environment, USDA MARS.

## The gap lands on the slowest movers — which is fortunate

Daily gaps: grains, aluminum, urea. But these are the **lowest-volatility**
anchors (wheat ~15% ann. vs crude 20–35%+). Since δ_vol = 1.65·σ·√(T/20),
slow movers tolerate data age: 30-day-old wheat costs only ~3.4% of δ budget.
Monthly grains remain quotable in normal times; they go silent first in
crises — exactly the right failure order.

## Three paths to close the gap

1. **Tiered strategy (v0.2, zero cost):** daily for high-volatility
   (energy, metals), monthly for low-volatility + crisis warnings.
2. **Free-tier quota discipline (v0.2–0.3):** freemium APIs (~100 calls/mo)
   suffice — one batched pull per day, stored and republished as the pack.
3. **Local spot-report network (v1.0, the real answer):** anonymized
   opt-in trade-ratio reports from users — K-calibration's natural
   byproduct; turns δ_data into locally measured truth. A data flywheel.

## Pipeline

```
collect_daily.py   FRED energy + gold-api metals + FRED/WB monthly
build_pack.py      unit normalization, multi-source median, rolling vol
sign_pack.py       Ed25519 signature (key in GitHub Secrets)
verify_pack.py     client-side verification (also run in CI)
```

Distribution: GitHub Releases (`latest` tag) + IPFS + Bluetooth/QR
peer transfer for offline regions. Pack history in git = audit log.
Multi-signature by independent maintainers is the governance roadmap.

## Trust root: public history, not private keys

The daily pack carries a `code_commit` field — the git commit of the build.
The trust chain is **the public history itself**, not a private key:

- **git's hash chain** makes history tamper-evident: rewriting any commit
  rewrites all subsequent hashes, visible on every mirror;
- **any mirror is self-authenticating**: knowing one trusted commit hash,
  a clone from GitHub, GitLab, IPFS, or a friend's USB stick can all be
  verified against it;
- **settlement delay**: clients only accept commits that have existed
  ≥ 24h on multiple independent mirrors — an attack is publicly visible
  *before* it can be used. Daily packs can afford this delay (δ_vol's √T
  term already prices data age honestly).

This converts unilateral power into public accountability: the maintainer
*can* publish bad data, but cannot do so invisibly. Fairness comes from
"wrongdoing is a public broadcast," not from trusting the operator.

**OpenTimestamps layer (the fuse, not the wall):** each pack's hash is
also anchored to Bitcoin via OpenTimestamps calendar servers — zero cost,
zero maintenance. It answers exactly one question: "was the history
rewritten?" — with a proof that not even GitHub could have produced
retroactively. It is *not* in the daily verification path: RPC access is
blocked in several target regions, and offline (Bluetooth/QR) transfers
can't reach the chain. Pack signatures (Ed25519) remain available as an
optional convenience layer for those who prefer them.

Client-side verification: `barter/gitaudit.py` — commit existence,
settlement period, multi-mirror agreement.

## Risks

Single-source manipulation → median + 3σ trimming + δ_data floor.
GitHub blocked somewhere → IPFS + peer transfer (packs are plain JSON).
Free-tier termination → degrade to monthly for affected anchors only.
