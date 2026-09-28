# Barter Exchange Reference · 易货换算尺

**[English](#english) | [中文](#中文)**

---

## English

A neutral reference tool for barter in regions with collapsing currencies.
Input both goods; get a **reference price** (yesterday's fair ratio, anchored
to global spot benchmarks) and a **negotiation band** (hard-capped at
hi/lo ≤ 1.40 — full width never exceeds 40%).

It never touches goods, money, or settlement. It is a ruler, not a currency.

### Quick start

```bash
python -m venv .venv && .venv/bin/pip install pandas numpy matplotlib openpyxl pynacl

# Fetch the latest daily data pack
curl -L -o data/datapack_latest.json \
  https://github.com/stainberg/barter-exchange/releases/download/latest/datapack-latest.json

# How much diesel for 1 tonne of wheat?
.venv/bin/python -m barter.cli wheat 1 diesel

# Is the counterparty's offer fair?
.venv/bin/python -m barter.cli eggs 30 flour --qty-b 100
```

### Documentation

| Doc | Content |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | Design philosophy — what it is, what it is not, and why |
| [docs/MATH.md](docs/MATH.md) | Formal proofs of core invariants (T1–T8, E1–E5) |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | Parameter calibration: 4 currency collapses + 2020 oil crash + 2025 Iran conflict |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Data pipeline: sources, gaps, distribution |

### Three rules

1. **Structure is proven** (MATH.md); backtests only calibrate parameters.
2. **Band width ≤ 40%** — degrade or stay silent rather than fake precision.
3. **Signed packs only** — any data pack must verify before loading.

---

## 中文

为法币崩溃/高通胀地区的交易者提供中立参考的**以物换物换算工具**。
输入双方的货物，输出一个**参考成交价**（基于全球现货锚定的昨日公道价）
和一个**议价区间**（硬性约束：上限/下限 ≤ 1.40，即全宽不超过 40%）。

不经手货物、不碰资金、不做结算。它是换算尺，不是货币。

### 快速开始

```bash
python -m venv .venv && .venv/bin/pip install pandas numpy matplotlib openpyxl pynacl

# 拉取最新每日数据包
curl -L -o data/datapack_latest.json \
  https://github.com/stainberg/barter-exchange/releases/download/latest/datapack-latest.json

# 1 吨小麦大约能换多少升柴油？
.venv/bin/python -m barter.cli 小麦 1 柴油

# 判断对方出价是否公道
.venv/bin/python -m barter.cli 鸡蛋 30 面粉 --qty-b 100
```

### 文档

| 文档 | 内容 |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | 设计哲学——它是什么、不是什么、为什么 |
| [docs/MATH.md](docs/MATH.md) | 核心不变量的形式化证明（T1~T8，E1~E5） |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | 参数标定：四国法币崩溃 + 2020 油崩 + 2025 以伊冲突 |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | 数据管线：数据源、缺口、分发 |

### 三条铁律

1. **数学结构可证明**（MATH.md），回测只负责标定参数范围；
2. **区间全宽 ≤ 40%**——给不出窄区间就降级或沉默，绝不用宽区间假装精确；
3. **只加载验签通过的数据包**——任何渠道传来的数据包必须先验签。

## License

Apache 2.0 — see [LICENSE](LICENSE).
