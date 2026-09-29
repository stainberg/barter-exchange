# Mathematical Foundations

> [README](../README.md) · [Design](DESIGN.md) · [Math](MATH.md) · [Backtesting](BACKTESTING.md) · [Data Sources](DATA_SOURCES.md)

---

> All core calculations rest on theorems, not on backtest luck.
> Backtests calibrate parameter *ranges*; they never justify structure.
> Theorem numbers map to comments in `barter/engine.py`.
> All properties are verified by exhaustive tests over every commodity pair
> (see `barter/tests.py`, clause E5).

## 1. Notation

- Goods $\mathcal{G}$; anchors $\mathcal{A} \subset \mathcal{G}$.
- Each good $g$: unit $u_g$, anchor-resolution chain $g \to a(g)$,
  cumulative coefficient $K_g$ (product of K along the lineage), depth $h_g$.
- Data pack gives each anchor a spot price $P_a$ in *any* currency (see T1).
- Per-unit value: $V_g = P_{a(g)} \cdot K_g$.

**Quote** for pair $(A,B)$: center $R = V_A / V_B$, half-width $\delta$,
band $[R e^{-\delta},\ R e^{\delta}]$ (log-symmetric).

## 2. Structural theorems (data-independent)

**T1 — Numéraire invariance.** $R$ is independent of the pack's pricing
currency. *Proof:* repricing all anchors by factor $x$ scales $V_A, V_B$
by the same $x$, which cancels in the ratio. $\blacksquare$
*Consequence:* a collapsing local currency mathematically cannot enter
the calculation; monetary noise is excluded by construction.

**T2 — Center reciprocity.** $R_{AB} \cdot R_{BA} = 1$. *Proof:* immediate. $\blacksquare$

**T3 — Center transitivity.** $R_{AC} = R_{AB}\cdot R_{BC}$.
*Proof:* $\frac{V_A}{V_B}\cdot\frac{V_B}{V_C} = \frac{V_A}{V_C}$. $\blacksquare$
*Consequence:* no path arbitrage; the L3 split-quote preserves the anchor.

**T4 — Band reciprocity closure.** The reciprocal of
$[R e^{-\delta}, R e^{\delta}]$ is exactly
$[\frac{1}{R} e^{-\delta}, \frac{1}{R} e^{\delta}]$.
*Proof:* $r \mapsto 1/r$ is decreasing on $\mathbb{R}^+$ and maps endpoints to
endpoints. $\blacksquare$
*Uniqueness:* requiring a center-$R$ band closed under reciprocals forces
$f(\delta) = 1/f(-\delta)$; with continuity and monotonicity the only
solution is $f(\delta) = e^{c\delta}$. Linear bands $R(1\pm\delta)$ fail
because $\frac{1}{1-\delta} \neq 1+\delta$.

**T5 — Edge-judgment consistency.** A trade inside the AB band is inside
the BA band. *Proof:* corollary of T4, provided $\delta$ is symmetric in
$(A,B)$ (clause E2). $\blacksquare$
*Meaning:* two parties computing independently can never receive
contradictory verdicts on the same trade.

**T6 — Clamp safety.** $\delta = \text{clamp}(\hat\delta, \delta_{min},
\delta_{max})$ preserves T2–T5 (monotone scalar map applied identically
to both directions). $\blacksquare$

**T7 — Honest monotonicity.** Data age $T$ up ⟹ $\delta$ never shrinks;
volatility up ⟹ $\delta$ never shrinks.
*Proof:* $\delta_{vol} = 1.65\,\sigma\sqrt{T/20}$ is non-decreasing in both;
clamp preserves monotonicity. $\blacksquare$
*Meaning:* the system cannot become "more confident with worse data."

**T8 — Split-quote inheritance.** The L3 credible leg is itself a standard
quote (recursion depth 1, enforced by `_depth`), inheriting T1–T7. $\blacksquare$

**T9 — Frame consistency.** Every price observation belongs to a
*measurement frame*: the benchmark frame $B$ (hub spot benchmarks) or the
PPP frame $P$ (multi-region sampled actual prices). A within-frame ratio
$R^F_{AB} = P^F_A / P^F_B$ inherits correlated sampling errors that
partially cancel; a cross-frame ratio $P^P_A / P^B_B$ carries the
differential frame deviation $e^P/e^B$, a systematic bias that does not
cancel. The deviation is *observable* on dual-priced anchors, so
cross-frame quotes must carry $\delta_{frame}$ estimated from rolling
$|P^P_a / P^B_a - 1|$ statistics. *Rule:* prefer single-frame paths;
mixed frames always pay the measured penalty. $\blacksquare$

## 3. Why δ components add linearly

Each δ component estimates a **bound** on log-space deviation, not a
standard deviation. For deterministic bounds $|e_i| \le \delta_i$, the total
satisfies $|\sum e_i| \le \sum \delta_i$ — the triangle inequality. Root-sum-
square would require probabilistic structure that grade/lineage errors do not
possess. Linear addition is the only assumption-free composition. The cost is
conservatism (wider bands), consistent with "silence over misleading."

## 4. Engineering clauses (invariants the implementation must keep)

- **E1** (T4): bands may only be constructed as $Re^{\pm\delta}$;
  any change here requires re-proving T4.
- **E2** (T5): every δ component must be symmetric in $(A,B)$
  (max/sum/min over both sides). No asymmetric terms (e.g., seller markup).
- **E3** (T7): no δ component may be decreasing in data age or volatility.
- **E4** (T3): chained conversions must go through the unified value layer
  $V_g = P_{a(g)}K_g$; never splice ratios ad hoc.
- **E5**: clauses guarded by exhaustive property tests over all goods.
- **E6** (T9): every quote's numerator and denominator must resolve to the
  same measurement frame; if not, δ_frame must be added. Frames are
  declared in taxonomy/data pack, never inferred.

## 5. Empirical parameters (calibrated by backtests, adjustable)

| Parameter | Value | Basis |
|---|---|---|
| δ_pair same / cross / perishable | 6% / 11% / 12% | daily t+1 error distribution + grade/basis friction |
| δ_data floor | 2% | single-source conservatism |
| δ_vol coefficient | 1.65 | normal 90th percentile (heuristic) |
| δ_lineage | 1% per hop | lineage error estimate |
| δ_min / δ_max | 8% / ln(1.4)/2 | product decision (hi/lo ≤ 1.40) |
| Freshness thresholds | 3d / 45d (daily), 45d / 100d (monthly) | engineering |
| Systemic-shock threshold | vol ≥ 60% ann. & ratio ≤ 1.8 | crisis calibration |
| δ_frame (cross-frame penalty) | floor 4% | benchmark vs PPP divergence stats |

Adjusting these never requires re-proving theorems; changing E1–E4 or E6 does.

---

*Keywords: numéraire invariance, log-symmetric band, reciprocity, formal proof, barter mathematics*
