# Mathematical Foundations

> [README](../README.md) · [Design](DESIGN.md) · [Math](MATH.md) · [Backtesting](BACKTESTING.md) · [Data Sources](DATA_SOURCES.md)

---

All core calculations rest on theorems, not on backtest luck.
Backtests calibrate parameter *ranges*; they never justify structure.
Theorems map to comments in `barter/engine.py` and are guarded by
exhaustive property tests over every commodity pair (`barter/tests.py`, E5).

## Notation

- Goods $\mathcal{G}$; anchors $\mathcal{A} \subset \mathcal{G}$.
- Each good $g$: unit $u_g$, anchor-resolution chain $g \to a(g)$,
  cumulative coefficient $K_g$, lineage depth $h_g$.
- Per-unit value: $V_g = P_{a(g)} \cdot K_g$.

**Quote** for pair $(A,B)$: center $R = V_A / V_B$, half-width $\delta$,
band $[R e^{-\delta},\ R e^{\delta}]$ (log-symmetric).

## Structural theorems (data-independent)

**T1 — Numéraire invariance.** $R$ is independent of the pack's pricing
currency: repricing all anchors by factor $x$ scales $V_A, V_B$ by the same
$x$, which cancels. $\blacksquare$
*A collapsing currency mathematically cannot enter the calculation.*

**T2 — Center reciprocity.** $R_{AB} \cdot R_{BA} = 1$. $\blacksquare$

**T3 — Center transitivity.** $R_{AC} = R_{AB}\cdot R_{BC}$.
$\frac{V_A}{V_B}\cdot\frac{V_B}{V_C} = \frac{V_A}{V_C}$. $\blacksquare$
*No path arbitrage; the L3 split-quote preserves the anchor.*

**T4 — Band reciprocity closure.** The reciprocal of
$[R e^{-\delta}, R e^{\delta}]$ is exactly
$[\frac{1}{R} e^{-\delta}, \frac{1}{R} e^{\delta}]$,
since $r \mapsto 1/r$ is decreasing and maps endpoints to endpoints.
*Uniqueness:* requiring closure under reciprocals with continuity and
monotonicity forces $f(\delta) = e^{c\delta}$; linear bands $R(1\pm\delta)$
fail because $\frac{1}{1-\delta} \neq 1+\delta$. $\blacksquare$

**T5 — Edge-judgment consistency.** A trade inside the AB band is inside
the BA band (corollary of T4, given $\delta$ symmetric in $(A,B)$, E2).
*Two parties computing independently can never receive contradictory
verdicts on the same trade.* $\blacksquare$

**T6 — Clamp safety.** $\delta = \text{clamp}(\hat\delta, \delta_{min},
\delta_{max})$ preserves T2–T5 (monotone scalar map applied identically
to both directions). $\blacksquare$

**T7 — Honest monotonicity.** Data age $T$ up ⟹ $\delta$ never shrinks;
volatility up ⟹ $\delta$ never shrinks ($\delta_{vol} = 1.65\sigma\sqrt{T/20}$
is non-decreasing in both; clamp preserves monotonicity).
*The system cannot become "more confident with worse data."* $\blacksquare$

**T8 — Split-quote inheritance.** The L3 credible leg is itself a standard
quote (recursion depth 1, enforced by `_depth`), inheriting T1–T7. $\blacksquare$

**T9 — Frame consistency.** Price observations belong to a measurement
frame: benchmark $B$ (hub spot) or PPP $P$ (multi-region sampled actual).
A within-frame ratio inherits correlated sampling errors that cancel;
a cross-frame ratio carries the differential frame deviation $e^P/e^B$,
a systematic bias that does not cancel. The deviation is observable on
dual-priced anchors, so cross-frame quotes carry $\delta_{frame}$ estimated
from rolling $|P^P_a / P^B_a - 1|$ statistics. $\blacksquare$

## Why δ components add linearly

Each δ component estimates a **bound** on log-space deviation, not a
standard deviation. For deterministic bounds $|e_i| \le \delta_i$, the total
satisfies $|\sum e_i| \le \sum \delta_i$ — the triangle inequality. Root-sum-
square would require probabilistic structure that grade/lineage errors do not
possess. Linear addition is the only assumption-free composition; the cost
is conservatism (wider bands), consistent with silence-over-misleading.

## Engineering clauses (invariants the implementation must keep)

- **E1** (T4): bands only as $Re^{\pm\delta}$; changing this requires
  re-proving T4.
- **E2** (T5): every δ component symmetric in $(A,B)$.
- **E3** (T7): no δ component decreasing in data age or volatility.
- **E4** (T3): chained conversions go through the unified value layer
  $V_g = P_{a(g)}K_g$; never splice ratios ad hoc.
- **E5**: all clauses guarded by exhaustive property tests over all goods.
- **E6** (T9): both sides of a quote resolve to the same frame, or
  δ_frame is added; frames are declared, never inferred.

## Empirical parameters (calibrated by backtests, adjustable)

| Parameter | Value | Basis |
|---|---|---|
| δ_pair same / cross / perishable | 6% / 11% / 12% | daily t+1 error distribution + grade/basis friction |
| δ_data floor | 2% | single-source conservatism |
| δ_vol coefficient | 1.65 | normal 90th percentile (heuristic) |
| δ_lineage | 1% per hop | lineage error estimate |
| δ_min / δ_max | 8% / ln(1.4)/2 | product decision (hi/lo ≤ 1.40) |
| δ_frame floor | 4% | benchmark vs PPP divergence statistics |
| Freshness thresholds | 3d / 45d (daily), 45d / 100d (monthly) | engineering |
| Systemic-shock threshold | vol ≥ 60% ann. & ratio ≤ 1.8 | crisis calibration |

Adjusting these never requires re-proving theorems; changing E1–E4 or E6 does.
