# Barter Exchange Reference · 易货换算尺

**A neutral reference for barter when money stops working.**
**当货币失灵时，一把中立的以物换物换算尺。**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![ci](https://github.com/stainberg/barter-exchange/actions/workflows/ci.yml/badge.svg)](https://github.com/stainberg/barter-exchange/actions/workflows/ci.yml)
[![datapack-daily](https://github.com/stainberg/barter-exchange/actions/workflows/datapack-daily.yml/badge.svg)](https://github.com/stainberg/barter-exchange/actions/workflows/datapack-daily.yml)
[![Latest data pack](https://img.shields.io/badge/datapack-daily-brightgreen)](https://github.com/stainberg/barter-exchange/releases/tag/latest)

[English](#english) · [中文](#中文) · [Keywords / Palabras clave / Ключевые слова / کلیدواژه‌ها](#keywords)

---

## English

When a currency collapses, what breaks is not trade but the **price signal**.
A farmer holding wheat and a driver holding diesel both know their goods have
value — what they lack is a shared, neutral answer to *"how much of yours for
how much of mine?"*

This tool answers that question. Input both goods; get:

- **a reference price** — yesterday's fair ratio, anchored to global commodity
  spot benchmarks (never to any collapsing currency);
- **a negotiation band** — the acceptable range around it, hard-capped at
  hi/lo ≤ 1.40. If a narrow band can't be produced, the tool degrades
  gracefully or stays silent rather than inventing precision.

It never touches goods, money, matching, or settlement. **It is a ruler,
not a currency.**

### Quick start

```bash
python -m venv .venv && .venv/bin/pip install pandas numpy matplotlib openpyxl

# Fetch the latest daily data pack
curl -L -o data/datapack_latest.json \
  https://github.com/stainberg/barter-exchange/releases/download/latest/datapack-latest.json

# How much diesel for 1 tonne of wheat?
python -m barter.cli wheat 1 diesel        # English
python -m barter.cli 小麦 1 柴油            # 中文

# Is the counterparty's offer fair?
python -m barter.cli eggs 30 flour --qty-b 100
```

### Documentation

| Doc | Content |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | Design philosophy — what it is, what it is not, and why |
| [docs/MATH.md](docs/MATH.md) | Formal proofs of core invariants (T1–T8, engineering clauses E1–E5) |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | Parameter calibration: 4 currency collapses + 2020 oil crash + 2025/2026 Iran conflicts — 302 trading days, zero total failures |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Data pipeline: sources, gaps, trust model, distribution |

### Three rules

1. **Structure is proven** ([MATH.md](docs/MATH.md)); backtests only
   calibrate parameters.
2. **Band width ≤ 40%** — degrade or stay silent rather than fake precision.
3. **Public-history trust** — every data pack binds to a git commit; clients
   verify existence, settlement period, and multi-mirror agreement.
   No private keys anywhere in the system.

---

## 中文

法币崩溃时，失效的不是贸易本身，而是**价格信号**。
拿着小麦的农民和拿着柴油的司机都知道自己的货有价值——
缺的是一个中立的答案："我的多少换你的多少？"

这个工具回答这个问题。输入双方的货物，得到：

- **参考成交价**——基于全球商品现货锚定的昨日公道比率（不经过任何崩溃货币）；
- **议价区间**——围绕参考价的可接受范围，硬性约束上限/下限 ≤ 1.40。
  给不出窄区间时，工具会优雅降级或保持沉默，绝不假装精确。

不经手货物、不碰资金、不做结算。**它是换算尺，不是货币。**

### 三条铁律

1. **数学结构可证明**（[MATH.md](docs/MATH.md)），回测只负责标定参数范围；
2. **区间全宽 ≤ 40%**——给不出窄区间就降级或沉默；
3. **公开历史即信任根**——数据包绑定 git commit，客户端验证存在性、
   沉淀期与多镜像一致性。系统内无私钥。

---

## Keywords

**English:** barter, barter trade, exchange reference, currency collapse,
hyperinflation, commodity-backed, price anchor, negotiation band,
reference price, fair trade ratio, Venezuela, Argentina, Iran, Russia,
sanctions, parallel exchange rate, commodity index, unit of account

**Español:** trueque, intercambio de bienes, colapso monetario,
hiperinflación, precio de referencia, tipo de cambio paralelo,
Venezuela, Argentina, comercio sin dinero

**Русский:** бартер, обмен товарами, гиперинфляция, обвал валюты,
справедливая цена, справочный курс обмена, товарный якорь

**فارسی:** تهاتر، مبادله کالا، فروپاشی ارز، تورم شدید، قیمت مرجع،
نرخ ارز موازی، ایران

**العربية:** مقايضة، تبادل السلع، انهيار العملة، تضخم مفرط، سعر مرجعي

**中文：** 以物换物、易货贸易、货币崩溃、恶性通胀、参考成交价、
议价区间、平行汇率、商品锚定

## License

Apache 2.0 — see [LICENSE](LICENSE).
