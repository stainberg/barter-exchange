#!/usr/bin/env python3
"""极限压力测试：2020-04 原油崩盘 + 日频数据
=============================================
回答：如果保证日频数据，系统能否扛住史上最剧烈的油价波动？

场景：2020-03~05，WTI 4-20 跌至负值（-37.6$），布伦特 4-21 单日 -24%。
方法：与以伊冲突回测相同，逐日构建 T=1 的数据包（日频推送场景），
      报价「原油 → 小麦」，观察 δ 演化、降级触发、前瞻覆盖率。
      其他锚定品用世界银行 2020 月度真实值。
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

CRASH = datetime(2020, 4, 20)   # WTI 负油价日


def vol_ann(prices, day, w=20):
    h = prices.loc[:day].iloc[-(w + 1):]
    if len(h) < 6:
        return 0.20
    r = [math.log(h.iloc[i] / h.iloc[i - 1]) for i in range(1, len(h))]
    m = sum(r) / len(r)
    v = sum((x - m) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(v) * math.sqrt(252)


def main():
    brent = pd.read_csv("data/brent_2020.csv", na_values=".")
    brent.columns = ["date", "brent"]
    brent["date"] = pd.to_datetime(brent["date"])
    brent = brent.dropna().set_index("date").sort_index()

    raw = pd.read_excel("data/cmo_monthly.xlsx", sheet_name="Monthly Prices",
                        skiprows=4)
    raw = raw.rename(columns={raw.columns[0]: "month"})
    raw = raw[raw["month"].astype(str).str.match(r"\d{4}M\d{2}", na=False)]
    raw["date"] = pd.to_datetime(raw["month"].str.replace("M", "-") + "-01")
    raw = raw.set_index("date").sort_index()
    row = raw.loc[pd.Timestamp("2020-04-01")]
    anchors = {"wheat": float(row["Wheat, US HRW"]),
               "rice": float(row["Rice, Thai 5% "]),
               "maize": float(row["Maize"]),
               "soyoil": float(row["Soybean oil"]),
               "sugar": float(row["Sugar, world"]),
               "gold": float(row["Gold"]),
               "silver": float(row["Silver"]),
               "copper": float(row["Copper"]),
               "aluminum": float(row["Aluminum"]),
               "urea": float(row["Urea "])}

    days = brent.loc["2020-02-20":"2020-06-15"].index
    rows = []
    for day in days:
        p = float(brent.loc[day, "brent"])
        vol = vol_ann(brent["brent"], day)
        a = {c: {"price_usd_per_unit": pp, "sources": {"WB": pp},
                 "vol20d_ann": 0.15, "as_of": day.strftime("%Y-%m-%d"),
                 "history_12m": [pp] * 12} for c, pp in anchors.items()}
        a["crude"] = {"price_usd_per_unit": p, "sources": {"FRED": p},
                      "vol20d_ann": vol, "as_of": day.strftime("%Y-%m-%d"),
                      "history_12m": [p] * 12}
        pack = DataPack({"generated": day.isoformat(), "anchors": a})
        now = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        q = quote("crude", 1, "wheat", None, pack, now=now)
        rows.append({"date": day, "brent": p, "vol": vol,
                     "actual": p / anchors["wheat"],
                     "ok": q.ok, "partial": q.partial, "delta": q.delta,
                     "mid": q.ratio_mid, "lo": q.ratio_lo, "hi": q.ratio_hi,
                     "manual_side": q.manual_side if q.partial else ""})
    df = pd.DataFrame(rows).set_index("date")

    print("日期        布伦特$  年化波动率   δ      状态        实际比率  区间内?")
    for d, r in df.iterrows():
        st = "正常" if r["ok"] and not r["partial"] else \
             ("L3分拆→担保小麦侧" if r["partial"] else "拒绝")
        band = "-"
        if r["ok"] and not r["partial"]:
            band = "✓" if r["lo"] <= r["actual"] <= r["hi"] else "✗"
        mark = " 💥" if abs((d - CRASH).days) <= 2 else ""
        print(f"{d:%m-%d}  {r['brent']:7.2f}  {r['vol']:9.0%}  {r['delta']:5.1%}  "
              f"{st:14s}  {r['actual']:7.4f}  {band}{mark}")

    print("\n=== 前瞻验证（t 日区间覆盖未来实际比率）===")
    for h in (1, 3, 5):
        ok = df[df["ok"] & ~df["partial"]]
        cov = tot = 0
        idx = list(df.index)
        for i in range(len(df) - h):
            r = df.iloc[i]
            if not (r["ok"] and not r["partial"]):
                continue
            tot += 1
            fut = df.iloc[i + h]["actual"]
            if r["lo"] <= fut <= r["hi"]:
                cov += 1
        print(f"  t+{h}: {cov}/{tot} = {cov/tot:.0%}" if tot else f"  t+{h}: 无正常报价")

    n_ok = int((df["ok"] & ~df["partial"]).sum())
    n_split = int(df["partial"].sum())
    n_ref = int((~df["ok"]).sum())
    win = df.loc["2020-04-15":"2020-04-30"]
    print(f"\n=== 汇总（{len(df)} 个交易日）===")
    print(f"  正常 {n_ok} 天 / L3分拆 {n_split} 天 / 拒绝 {n_ref} 天")
    print(f"  波动率峰值 {df['vol'].max():.0%}（{df['vol'].idxmax():%Y-%m-%d}）")
    print(f"  崩盘窗口 04-15~04-30: 正常 {int((win['ok'] & ~win['partial']).sum())} / "
          f"L3 {int(win['partial'].sum())} / 拒绝 {int((~win['ok']).sum())}")
    df.to_csv(f"{OUT}/covid2020_daily.csv")

    # 图
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1, 1.2]})
    ax = axes[0]
    ax.plot(df.index, df["brent"], lw=1.6, color="#333")
    ax.axvline(CRASH, color="red", ls="--", lw=1)
    ax.annotate("WTI 负油价 04-20", xy=(CRASH, 30), color="darkred", fontsize=9)
    ax.set_ylabel("布伦特 $/桶"); ax.grid(alpha=0.3)
    ax.set_title("2020-04 原油崩盘 · 日频数据压力测试：系统能否扛住？")
    ax = axes[1]
    ax.plot(df.index, df["vol"] * 100, lw=1.4, color="#d62728")
    ax.set_ylabel("年化波动率 %"); ax.grid(alpha=0.3)
    ax = axes[2]
    ok = df[df["ok"] & ~df["partial"]]
    ax.fill_between(ok.index, ok["lo"], ok["hi"], color="#1f77b4", alpha=0.25,
                    label="正常报价区间")
    sp = df[df["partial"]]
    if len(sp):
        ax.scatter(sp.index, sp["actual"], marker="x", s=60, color="orange",
                   zorder=5, label="L3分拆日（只担保小麦侧）")
    ax.plot(df.index, df["actual"], lw=1.4, color="#d62728", label="实际比率")
    ax.set_ylabel("吨小麦/桶原油"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig4_covid_crash.png", dpi=130)
    print(f"\n图表: {OUT}/fig4_covid_crash.png")


if __name__ == "__main__":
    main()
