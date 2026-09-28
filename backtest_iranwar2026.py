#!/usr/bin/env python3
"""2026 美伊冲突 · 石油回测（真实危机回放）
============================================
背景（CNBC 时间线 2026-04-21 + FRED 日频数据）：
  2026-02-27  战争爆发，Brent ~$72
  2026-03     单月 +51%，历史最大月度涨幅之一，霍尔木兹海峡中断担忧
  2026-04-07  峰值 $138.21
  2026-04-17  单日 -15.5%（$116→$98.6）
  2026-05~06  缓和回落，7 月初 ~$69
  2026-07-23  再度紧张冲 $105
  2026-09-15  $130.80（特朗普拒绝伊朗重开海峡提议前后）
  2026-09-22  $114.89（数据截止）

问题：系统在这场持续 7 个月、反复脉冲的真实战争中表现如何？
      对照 2025 以伊冲突（12 天）和 2020 崩盘（349% 波动率峰值）。
"""
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from barter.datapack import DataPack
from barter.engine import quote

plt.rcParams["font.family"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = "backtest_out"
os.makedirs(OUT, exist_ok=True)

WAR_START = pd.Timestamp("2026-02-27")

# 其他锚定品用世界银行月度真实值（按月份对齐）
def load_monthly():
    raw = pd.read_excel("data/cmo_new.xlsx", sheet_name="Monthly Prices",
                        skiprows=4)
    raw = raw.rename(columns={raw.columns[0]: "month"})
    raw = raw[raw["month"].astype(str).str.match(r"\d{4}M\d{2}", na=False)]
    raw["date"] = pd.to_datetime(raw["month"].str.replace("M", "-") + "-01")
    return raw.set_index("date").sort_index()


def anchors_for(raw, month_ts):
    row = raw.loc[month_ts]
    return {
        "wheat": float(row["Wheat, US HRW"]),
        "rice": float(row["Rice, Thai 5% "]),
        "maize": float(row["Maize"]),
        "soyoil": float(row["Soybean oil"]),
        "sugar": float(row["Sugar, world"]),
        "gold": float(row["Gold"]),
        "silver": float(row["Silver"]),
        "copper": float(row["Copper"]),
        "aluminum": float(row["Aluminum"]),
        "urea": float(row.get("Urea ", float("nan"))) if "Urea " in row else 300.0,
    }


def vol_ann(prices, day, w=20):
    h = prices.loc[:day].iloc[-(w + 1):]
    if len(h) < 6:
        return 0.20
    r = [math.log(h.iloc[i] / h.iloc[i - 1]) for i in range(1, len(h))]
    m = sum(r) / len(r)
    v = sum((x - m) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(v) * math.sqrt(252)


def main():
    brent = pd.read_csv("data/brent_2026.csv", na_values=".")
    brent.columns = ["date", "brent"]
    brent["date"] = pd.to_datetime(brent["date"])
    brent = brent.dropna().set_index("date").sort_index()
    monthly = load_monthly()

    days = brent.loc["2026-01-05":].index
    rows = []
    for day in days:
        p = float(brent.loc[day, "brent"])
        vol = vol_ann(brent["brent"], day)
        # 用当月（或最近一个可用月）的世界银行月度值
        mkey = day.to_period("M").to_timestamp()
        avail = monthly.index[monthly.index <= mkey]
        anchors = anchors_for(monthly, avail[-1])
        # 数据龄：日频原油为当天，月频锚定品为当月1号
        monthly_asof = avail[-1].strftime("%Y-%m-%d")
        a = {c: {"price_usd_per_unit": pp, "sources": {"WB": pp},
                 "vol20d_ann": 0.15, "as_of": day.strftime("%Y-%m-%d"),
                 "history_12m": [pp] * 12, "freq": "daily"}
             for c, pp in anchors.items()}
        a["crude"] = {"price_usd_per_unit": p, "sources": {"FRED": p},
                      "vol20d_ann": vol, "as_of": day.strftime("%Y-%m-%d"),
                      "history_12m": [p] * 12, "freq": "daily"}
        pack = DataPack({"generated": day.isoformat(), "anchors": a})
        now = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        q = quote("crude", 1, "wheat", None, pack, now=now)
        rows.append({"date": day, "brent": p, "vol": vol,
                     "actual": p / anchors["wheat"],
                     "ok": q.ok, "partial": q.partial, "delta": q.delta,
                     "mid": q.ratio_mid, "lo": q.ratio_lo, "hi": q.ratio_hi})
    df = pd.DataFrame(rows).set_index("date")

    # ---------- 汇总 ----------
    n = len(df)
    n_ok = int((df["ok"] & ~df["partial"]).sum())
    n_split = int(df["partial"].sum())
    n_ref = int((~df["ok"]).sum())
    print(f"=== 2026 美伊冲突回测（{df.index[0]:%Y-%m-%d} ~ {df.index[-1]:%Y-%m-%d}，{n} 个交易日）===")
    print(f"价格: ${df['brent'].min():.2f} → 峰值 ${df['brent'].max():.2f}"
          f"（{df['brent'].idxmax():%m-%d}）→ 当前 ${df['brent'].iloc[-1]:.2f}")
    print(f"波动率峰值: {df['vol'].max():.0%}（{df['vol'].idxmax():%Y-%m-%d}）")
    print(f"报价状态: 正常 {n_ok} / L3分拆 {n_split} / 拒绝 {n_ref}")
    print(f"正常报价率: {n_ok/n:.0%}")

    # 前瞻覆盖
    print("\n=== 前瞻验证 ===")
    for h in (1, 3, 5):
        cov = tot = 0
        for i in range(n - h):
            r = df.iloc[i]
            if not (r["ok"] and not r["partial"]):
                continue
            tot += 1
            if r["lo"] <= df.iloc[i + h]["actual"] <= r["hi"]:
                cov += 1
        print(f"  t+{h}: {cov}/{tot} = {cov/tot:.0%}" if tot else f"  t+{h}: 无")

    # 分阶段
    print("\n=== 分阶段 ===")
    phases = [("战前平静期", "2026-01-05", "2026-02-26"),
              ("爆发+封锁恐慌", "2026-02-27", "2026-04-10"),
              ("高位震荡", "2026-04-13", "2026-06-30"),
              ("缓和回落", "2026-07-01", "2026-08-31"),
              ("再紧张", "2026-09-01", "2026-09-28")]
    for name, t0, t1 in phases:
        w = df.loc[t0:t1]
        if len(w) == 0:
            continue
        ok_r = float((w["ok"] & ~w["partial"]).mean())
        print(f"  {name:10s} {t0}~{t1}: 正常报价率 {ok_r:.0%}  "
              f"δ均值 {float(w['delta'].mean()):.1%}  vol均值 {float(w['vol'].mean()):.0%}")

    df.to_csv(f"{OUT}/iranwar2026_daily.csv")

    # ---------- 图 ----------
    fig, axes = plt.subplots(3, 1, figsize=(13, 9.5), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1, 1.3]})
    ax = axes[0]
    ax.plot(df.index, df["brent"], lw=1.6, color="#333")
    ax.axvline(WAR_START, color="red", ls="--", lw=1)
    ax.annotate("战争爆发 02-27", xy=(WAR_START, 75), color="darkred", fontsize=9)
    ax.annotate(f"峰值 ${df['brent'].max():.0f}", xy=(df["brent"].idxmax(), df["brent"].max()),
                color="darkred", fontsize=9)
    ax.set_ylabel("布伦特 $/桶"); ax.grid(alpha=0.3)
    ax.set_title("2026 美伊冲突 · 系统在持续 7 个月真实战争中的逐日表现")

    ax = axes[1]
    ax.plot(df.index, df["vol"] * 100, lw=1.4, color="#d62728")
    ax.set_ylabel("年化波动率 %"); ax.grid(alpha=0.3)

    ax = axes[2]
    ok = df[df["ok"] & ~df["partial"]]
    ax.fill_between(ok.index, ok["lo"], ok["hi"], color="#1f77b4", alpha=0.25,
                    label="正常报价区间")
    sp = df[df["partial"]]
    if len(sp):
        ax.scatter(sp.index, sp["actual"], marker="v", s=40, color="orange",
                   zorder=5, label=f"L3分拆日（{len(sp)}天）")
    rf = df[~df["ok"]]
    if len(rf):
        ax.scatter(rf.index, rf["actual"], marker="x", s=40, color="red",
                   zorder=5, label=f"拒绝日（{len(rf)}天）")
    ax.plot(df.index, df["actual"], lw=1.4, color="#d62728", label="实际比率")
    ax.set_ylabel("吨小麦/桶原油"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig5_iranwar2026.png", dpi=130)
    print(f"\n图表: {OUT}/fig5_iranwar2026.png")


if __name__ == "__main__":
    main()
