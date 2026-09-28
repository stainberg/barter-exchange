#!/usr/bin/env python3
"""2025-06 以伊冲突 · 石油回测
================================
场景：2025-06-13 以色列空袭伊朗 → 布伦特单日 +7~9% → 06-23 停火单日 -9%。
问题：工具在这 12 天里的表现如何？区间是否仍然有效？降级链是否按设计触发？

数据：
  - 原油日频：FRED DCOILBRENTEU（真实现货日价）
  - 其他锚定品：世界银行粉单 2025-06 月度值（真实现货基准价）
  - 波动率：油价日收益率 20 日滚动年化（真实计算）
方法：逐日构建数据包（数据龄 T=1，模拟日频数据推送场景），
      每天调用引擎报价「原油 → 小麦」，记录 δ 演化与降级触发，
      并做前瞻验证：t 日报价区间是否覆盖 t+1/t+3/t+5 的实际比率。
"""
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

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

WAR_START = datetime(2025, 6, 13)   # 以色列空袭伊朗
WAR_END = datetime(2025, 6, 24)     # 停火


def load_data():
    brent = pd.read_csv("data/brent_daily.csv", na_values=".")
    brent.columns = ["date", "brent"]
    brent["date"] = pd.to_datetime(brent["date"])
    brent = brent.dropna().set_index("date").sort_index()

    raw = pd.read_excel("data/cmo_new.xlsx", sheet_name="Monthly Prices",
                        skiprows=4)
    raw = raw.rename(columns={raw.columns[0]: "month"})
    raw = raw[raw["month"].astype(str).str.match(r"\d{4}M\d{2}", na=False)]
    raw["date"] = pd.to_datetime(raw["month"].str.replace("M", "-") + "-01")
    raw = raw.set_index("date").sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    return brent, raw


def monthly_anchor_vals(raw, month="2025-06-01"):
    """2025-06 各锚定品月度现货基准价（美元）。"""
    row = raw.loc[pd.Timestamp(month)]
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
        "urea": float(row["Urea "]),
    }


def rolling_vol_ann(prices: pd.Series, day, window=20):
    """截止 day 的过去 window 个交易日的日收益率年化波动率。"""
    hist = prices.loc[:day].iloc[-(window + 1):]
    if len(hist) < 6:
        return 0.20
    rets = [math.log(hist.iloc[i] / hist.iloc[i - 1])
            for i in range(1, len(hist))]
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def make_pack(day, brent_price, crude_vol, anchors):
    as_of = day.strftime("%Y-%m-%d")
    a = {}
    for c, p in anchors.items():
        a[c] = {"price_usd_per_unit": p, "sources": {"WB-CMO": p},
                "vol20d_ann": 0.15, "as_of": as_of,
                "history_12m": [p] * 12}
    a["crude"] = {"price_usd_per_unit": brent_price,
                  "sources": {"FRED-Brent": brent_price},
                  "vol20d_ann": crude_vol, "as_of": as_of,
                  "history_12m": [brent_price] * 12}
    return DataPack({"generated": day.isoformat(), "anchors": a})


def main():
    brent, raw = load_data()
    anchors = monthly_anchor_vals(raw)
    days = brent.loc["2025-05-19":"2025-07-15"].index

    rows = []
    for day in days:
        p = float(brent.loc[day, "brent"])
        vol = rolling_vol_ann(brent["brent"], day)
        pack = make_pack(day, p, vol, anchors)
        now = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        q = quote("crude", 1, "wheat", None, pack, now=now)
        # 实际比率（吨小麦/桶原油）
        actual = p / anchors["wheat"]
        rows.append({
            "date": day, "brent": p, "vol": vol, "actual_ratio": actual,
            "ok": q.ok, "partial": q.partial, "delta": q.delta,
            "mid": q.ratio_mid, "lo": q.ratio_lo, "hi": q.ratio_hi,
            "reason": q.reason if not q.ok else "",
        })
    df = pd.DataFrame(rows).set_index("date")

    # ---------- 逐日状态报告 ----------
    print("日期        布伦特$   年化波动率  δ      报价状态          实际比率  比率在t日区间内?")
    for d, r in df.iterrows():
        in_band = r["lo"] <= r["actual_ratio"] <= r["hi"] if r["ok"] and not r["partial"] else None
        status = ("正常" if r["ok"] and not r["partial"]
                  else "L3分拆" if r["partial"] else "拒绝")
        band = {True: "✓", False: "✗", None: "-"}[in_band]
        mark = " ⚔" if WAR_START <= d <= WAR_END else ""
        print(f"{d:%m-%d}  {r['brent']:7.2f}  {r['vol']:9.0%}  {r['delta']:5.1%}  "
              f"{status:10s}  {r['actual_ratio']:7.4f}  {band}{mark}")

    # ---------- 前瞻验证 ----------
    print("\n=== 前瞻验证：t 日报价区间是否覆盖未来实际比率 ===")
    for horizon in (1, 3, 5):
        covered, total = 0, 0
        for i in range(len(df) - horizon):
            r = df.iloc[i]
            if not r["ok"] or r["partial"]:
                continue
            future = df.iloc[i + horizon]["actual_ratio"]
            total += 1
            if r["lo"] <= future <= r["hi"]:
                covered += 1
        print(f"  t+{horizon} 天: {covered}/{total} = {covered/total:.0%} 覆盖")

    # ---------- 冲突窗口专项 ----------
    war = df.loc["2025-06-12":"2025-06-25"]
    print("\n=== 冲突窗口（06-12 ~ 06-25）专项 ===")
    print(f"  油价: {war['brent'].iloc[0]:.2f} → 峰值 {war['brent'].max():.2f} "
          f"({war['brent'].idxmax():%m-%d}) → 停火后 {war['brent'].iloc[-1]:.2f}")
    print(f"  年化波动率: 战前 {df.loc['2025-06-12','vol']:.0%} → "
          f"峰值 {war['vol'].max():.0%}（{war['vol'].idxmax():%m-%d}）")
    print(f"  δ 演化: {war['delta'].iloc[0]:.1%} → 峰值 {war['delta'].max():.1%} → "
          f"期末 {war['delta'].iloc[-1]:.1%}")
    n_ok = int((war["ok"] & ~war["partial"]).sum())
    n_split = int(war["partial"].sum())
    n_refuse = int((~war["ok"]).sum())
    print(f"  报价状态: 正常 {n_ok} 天 / L3分拆 {n_split} 天 / 拒绝 {n_refuse} 天")
    in_band = war[(war["ok"]) & (~war["partial"])]
    cov = ((in_band["lo"] <= in_band["actual_ratio"])
           & (in_band["actual_ratio"] <= in_band["hi"])).mean()
    print(f"  当日实际比率落在报价区间内: {cov:.0%}")

    df.to_csv(f"{OUT}/iran2025_daily.csv")
    plot(df)
    print(f"\n图表: {OUT}/fig3_iran_war_oil.png")


def plot(df):
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1, 1.2]})
    ax = axes[0]
    ax.plot(df.index, df["brent"], lw=1.6, color="#333", label="布伦特现货（$/桶）")
    ax.axvspan(WAR_START, WAR_END, color="red", alpha=0.08, label="冲突窗口")
    ax.annotate("以色列空袭伊朗\n06-13", xy=(WAR_START, 70), fontsize=9, color="darkred")
    ax.annotate("停火 06-24", xy=(WAR_END, 67), fontsize=9, color="darkgreen")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    ax.set_title("2025-06 以伊冲突 · 石油回测：工具在 12 天战争中的逐日表现")

    ax = axes[1]
    ax.plot(df.index, df["vol"] * 100, lw=1.4, color="#d62728")
    ax.axhline(100, ls="--", lw=1, color="gray")
    ax.text(df.index[1], 105, "100%（≈2020-04 前的一半水平）", fontsize=8, color="gray")
    ax.axvspan(WAR_START, WAR_END, color="red", alpha=0.08)
    ax.set_ylabel("年化波动率 %"); ax.grid(alpha=0.3)

    ax = axes[2]
    ok = df[df["ok"] & ~df["partial"]]
    ax.fill_between(ok.index, ok["lo"], ok["hi"], color="#1f77b4", alpha=0.25,
                    label="报价区间 [lo, hi]")
    ax.plot(df.index, df["actual_ratio"], lw=1.6, color="#d62728",
            label="实际比率（吨小麦/桶原油）")
    ax.plot(ok.index, ok["mid"], lw=1, ls="--", color="#1f77b4", label="中心值")
    ax.axvspan(WAR_START, WAR_END, color="red", alpha=0.08)
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    ax.set_ylabel("比率")
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig3_iran_war_oil.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
