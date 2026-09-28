#!/usr/bin/env python3
"""
易货换算工具 · 历史回测
========================
验证核心假设：法币崩溃期间，以全球大宗商品为锚的"物物兑换比率"
保持在可控区间内，而同一商品的法币价格爆炸式失真。

数据：
  - 大宗商品：世界银行粉单 CMO 月度价格（真实数据，$/unit）
  - ARS：bluelytics 官方+蓝美元（真实日频）
  - RUB：frankfurter/ECB（真实日频，至 2022-03）
  - VES/IRR：无可靠免费历史序列 → 使用公开报道的关键节点
    （标注为 approximate，仅用于展示崩溃量级，不参与 δ 校准）
"""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["font.family"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT = "backtest_out"
import os
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- commodities
def load_commodities():
    raw = pd.read_excel("data/cmo_monthly.xlsx", sheet_name="Monthly Prices",
                        skiprows=4)
    raw = raw.rename(columns={raw.columns[0]: "month"})
    raw = raw[raw["month"].astype(str).str.match(r"\d{4}M\d{2}", na=False)]
    raw["date"] = pd.to_datetime(raw["month"].str.replace("M", "-") + "-01")
    cols = {
        "Rice, Thai 5% ": "rice",          # $/mt
        "Wheat, US HRW": "wheat",          # $/mt
        "Maize": "maize",                  # $/mt
        "Soybean oil": "soyoil",           # $/mt
        "Sugar, world": "sugar",           # $/kg (实际 c/lb→$/kg 无关, 只用相对值)
        "Crude oil, average": "crude",     # $/bbl
        "Gold": "gold",                    # $/toz
        "Silver": "silver",                # $/toz
        "Copper": "copper",                # $/mt
        "Aluminum": "aluminum",            # $/mt
        "Urea ": "urea",                   # $/mt
    }
    df = raw[["date"] + list(cols)].rename(columns=cols).set_index("date")
    df = df.apply(pd.to_numeric, errors="coerce")
    return df.loc["2000":]

# ---------------------------------------------------------------- FX
def load_ars():
    d = json.load(open("data/ars_blue.json"))
    df = pd.DataFrame(d)
    df["date"] = pd.to_datetime(df["date"])
    piv = df.pivot_table(index="date", columns="source",
                         values="value_sell", aggfunc="last").sort_index()
    piv = piv.rename(columns={"Oficial": "ars_official", "Blue": "ars_blue"})
    return piv.resample("MS").mean()

def load_rub():
    d = json.load(open("data/usdrub_frankfurter.json"))["rates"]
    s = pd.Series({pd.Timestamp(k): v["RUB"] for k, v in d.items()}).sort_index()
    return s.resample("MS").mean().rename("rub")

# VES / IRR：公开报道的平行市场年末参考值（approximate，量级展示用）
# 来源：dolartoday/bonbast 等公开报道汇总的常见引用值
VES_EOY = {  # 统一换算为 2018 版 VES（旧 VEF ÷ 1e5）
    2012: 1.5e-4, 2013: 4e-4, 2014: 1.5e-3, 2015: 8e-3, 2016: 3e-2,
    2017: 1.1,    2018: 700,  2019: 45000,  2020: 1.1e6,
    2021: 4.6e6,  2022: 1.7e7, 2023: 3.6e7,
}
IRR_EOY = {  # 平行市场 IRR/USD 年末值
    2015: 36000, 2016: 40000, 2017: 43000, 2018: 110000, 2019: 130000,
    2020: 260000, 2021: 290000, 2022: 400000, 2023: 500000, 2024: 750000,
}

# ---------------------------------------------------------------- 崩溃窗口
PERIODS = {
    "委内瑞拉 VES": {"pre": ("2012-01", "2013-12"),
                    "collapse": ("2016-01", "2019-12"),
                    "post": ("2021-01", "2023-12")},
    "阿根廷 ARS":  {"pre": ("2016-01", "2017-12"),
                    "collapse": ("2018-01", "2023-12"),
                    "post": ("2024-01", "2024-12")},
    "伊朗 IRR":    {"pre": ("2016-01", "2017-12"),
                    "collapse": ("2018-01", "2020-12"),
                    "post": ("2021-01", "2023-12")},
    "俄罗斯 RUB":  {"pre": ("2013-01", "2014-06"),
                    "collapse": ("2014-07", "2015-12"),
                    "post": ("2016-06", "2019-12")},
}

# ---------------------------------------------------------------- 主分析
def main():
    com = load_commodities()
    print(f"商品数据: {len(com)} 个月, {com.index[0]:%Y-%m} ~ {com.index[-1]:%Y-%m}")

    ars = load_ars()
    rub = load_rub()

    # ---------- 1. 法币崩溃量级 ----------
    fx_summary = []
    for name, s, label in [
        ("阿根廷（官方）", ars["ars_official"].dropna(), "official"),
        ("阿根廷（蓝美元）", ars["ars_blue"].dropna(), "blue"),
        ("俄罗斯", rub.dropna(), "market"),
    ]:
        fx_summary.append((name, s))
    # VES / IRR 用年末节点构造月度阶梯序列（approximate）
    def steps_from_eoy(d, start="2012"):
        idx = pd.date_range(start, "2024-12", freq="MS")
        out = pd.Series(index=idx, dtype=float)
        for y, v in d.items():
            out[f"{y}"] = v
        return out.ffill()
    fx_summary.append(("委内瑞拉（平行,approx）", steps_from_eoy(VES_EOY)))
    fx_summary.append(("伊朗（平行,approx）", steps_from_eoy(IRR_EOY, "2015")))

    # ---------- 2. 物物兑换比率 ----------
    # 物理单位换算到有意义的"生活单位"
    # 比率 = 1 单位 A 能换多少单位 B（全用美元价计算，与任何法币无关）
    pairs = [
        ("wheat",  "crude",  "1 桶原油 ≈ ? 公斤小麦",   1000),   # $/bbl vs $/mt→kg
        ("rice",   "crude",  "1 桶原油 ≈ ? 公斤大米",   1000),
        ("gold",   "wheat",  "1 克黄金 ≈ ? 公斤小麦",   1000/31.1035),
        ("gold",   "crude",  "1 盎司黄金 ≈ ? 桶原油",   1),
        ("copper", "wheat",  "1 吨铜 ≈ ? 吨小麦",       1),
        ("maize",  "soyoil", "1 吨豆油 ≈ ? 吨玉米",     1),
        ("sugar",  "wheat",  "糖/小麦 比价",            1),
        ("silver", "wheat",  "1 盎司白银 ≈ ? 公斤小麦", 1000),
    ]
    ratios = {}
    for a, b, label, k in pairs:
        r = (com[b] / (com[a] / k)).dropna()   # units of A per unit of B... 方向见标签
        ratios[label] = r
    ratios_df = pd.DataFrame(ratios)

    # ---------- 3. 比率稳定性统计（按国家窗口） ----------
    stats_rows = []
    for country, wins in PERIODS.items():
        for phase, (t0, t1) in wins.items():
            seg = ratios_df.loc[t0:t1]
            for label in seg.columns:
                s = seg[label].dropna()
                if len(s) < 6:
                    continue
                med = s.median()
                stats_rows.append({
                    "国家": country, "阶段": phase, "窗口": f"{t0}~{t1}",
                    "比率": label,
                    "CV%": round(100 * s.std() / s.mean(), 1),
                    "最大偏离中位数%": round(100 * (s / med - 1).abs().max(), 1),
                    "月数": len(s),
                })
    stats = pd.DataFrame(stats_rows)
    piv = stats.pivot_table(index=["国家", "阶段"], values=["CV%", "最大偏离中位数%"],
                            aggfunc="mean").round(1)
    print("\n=== 各崩溃窗口内 物物兑换比率稳定性（8 组比率平均）===")
    print(piv.to_string())

    # ---------- 4. 对照：法币计价的爆炸 ----------
    fx_deg_rows = []
    for name, s in fx_summary:
        for country, wins in PERIODS.items():
            cn = country.split()[0]
            if cn not in name:
                continue
            for phase, (t0, t1) in wins.items():
                seg = s.loc[t0:t1].dropna()
                if len(seg) > 1:
                    fx_deg_rows.append({
                        "国家": country, "阶段": phase,
                        "法币贬值倍数(x)": round(seg.iloc[-1] / seg.iloc[0], 1)})
    fxdeg = pd.DataFrame(fx_deg_rows)
    print("\n=== 各窗口内法币对美元贬值倍数 ===")
    print(fxdeg.to_string(index=False))

    # ---------- 5. δ 校准 ----------
    # 对每个比率：滚动 12 个月窗口，求"覆盖 95% 月份所需的对称半宽"
    calib_rows = []
    for label in ratios_df.columns:
        s = ratios_df[label].dropna()
        dev = []
        for i in range(12, len(s)):
            win = s.iloc[i-12:i]
            med = win.median()
            dev.append(np.percentile(np.abs(win / med - 1), 95))
        dev = np.array(dev)
        calib_rows.append({
            "比率": label,
            "δ95 中位数": round(np.median(dev) * 100, 1),
            "δ95 P90": round(np.percentile(dev, 90) * 100, 1),
            "δ95 最大": round(dev.max() * 100, 1),
            "最大单月跳变%": round(100 * (s / s.shift(1) - 1).abs().max(), 1),
        })
    calib = pd.DataFrame(calib_rows)
    print("\n=== δ 校准（滚动12月窗口，覆盖95%月份所需半宽，%）===")
    print(calib.to_string(index=False))

    stats.to_csv(f"{OUT}/ratio_stability.csv", index=False)
    fxdeg.to_csv(f"{OUT}/fx_devaluation.csv", index=False)
    calib.to_csv(f"{OUT}/delta_calibration.csv", index=False)

    # ---------- 6. 图表 ----------
    plot_fx(fx_summary)
    plot_ratios(ratios_df)
    return stats, fxdeg, calib, ratios_df

def plot_fx(fx_summary):
    fig, ax = plt.subplots(figsize=(11, 6))
    for name, s in fx_summary:
        s = s.dropna()
        ax.plot(s.index, s / s.iloc[0], label=name, lw=1.4)
    ax.set_yscale("log")
    ax.set_ylabel("本币兑美元贬值倍数（起点=1，对数轴）")
    ax.set_title("四国法币崩溃过程：本币计价失灵的量级")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig1_fx_collapse.png", dpi=130)
    plt.close(fig)

def plot_ratios(ratios_df):
    show = ["1 桶原油 ≈ ? 公斤小麦", "1 克黄金 ≈ ? 公斤小麦",
            "1 吨铜 ≈ ? 吨小麦", "1 盎司黄金 ≈ ? 桶原油"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), sharex=True)
    for ax, label in zip(axes.flat, show):
        s = ratios_df[label].dropna()
        med12 = s.rolling(12, min_periods=6).median()
        ax.plot(s.index, s, lw=1.2, color="#1f77b4", label="月度比率")
        ax.plot(med12.index, med12, lw=1.6, color="#d62728", label="12月中位数")
        ax.fill_between(med12.index, med12*0.85, med12*1.15,
                        color="#d62728", alpha=0.12, label="±15% 区间")
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("物物兑换比率（2010–2024）：含多轮法币崩溃期，比率始终有界", y=0.995)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig2_barter_ratios.png", dpi=130)
    plt.close(fig)

if __name__ == "__main__":
    main()
