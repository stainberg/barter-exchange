#!/usr/bin/env python3
"""合并所有日频回测为统一数据集，标注事件分级。

事件分级（按油价年化波动率 + 事件性质）：
  normal   常态（vol < 40%）
  elevated 紧张（40% ≤ vol < 60%）
  crisis   危机（60% ≤ vol < 100%，如 2026 美伊冲突大部分时段）
  extreme  极端（vol ≥ 100%，如 2020-04 负油价、2026-04-17 单日-15.5%）

输出：backtest_out/all_backtests.csv（统一 schema）
"""
import pandas as pd

def classify(vol):
    if vol < 0.40:
        return "normal"
    if vol < 0.60:
        return "elevated"
    if vol < 1.00:
        return "crisis"
    return "extreme"

EVENTS = {
    "covid2020": {
        "file": "backtest_out/covid2020_daily.csv", "actual_col": "actual",
        "name": "2020-04 原油崩盘（COVID + 负油价）",
        "window": ("2020-03-09", "2020-05-20"),
        "peak_note": "WTI 04-20 负油价，Brent -85%",
    },
    "iran2025": {
        "file": "backtest_out/iran2025_daily.csv", "actual_col": "actual_ratio",
        "name": "2025-06 以伊冲突（12 天战争）",
        "window": ("2025-06-13", "2025-06-24"),
        "peak_note": "Brent +13.5% 后 -15%",
    },
    "iranwar2026": {
        "file": "backtest_out/iranwar2026_daily.csv", "actual_col": "actual",
        "name": "2026 美伊冲突（7 个月持续战争 + 霍尔木兹封锁）",
        "window": ("2026-02-27", "2026-09-22"),
        "peak_note": "Brent $72→$138，单月 +51%",
    },
}

frames = []
for key, ev in EVENTS.items():
    df = pd.read_csv(ev["file"])
    df["actual"] = df[ev["actual_col"]]
    df["event"] = key
    df["event_name"] = ev["name"]
    df["event_window"] = f"{ev['window'][0]}~{ev['window'][1]}"
    df["level"] = df["vol"].apply(classify)
    frames.append(df[["date", "event", "event_name", "event_window", "brent",
                      "vol", "level", "ok", "partial", "delta",
                      "mid", "lo", "hi", "actual"]])

all_df = pd.concat(frames, ignore_index=True)
all_df.to_csv("backtest_out/all_backtests.csv", index=False)

# 汇总表
print("=== 统一回测数据集 ===")
print(f"总交易日: {len(all_df)}\n")

summary = []
for key, ev in EVENTS.items():
    d = all_df[all_df["event"] == key]
    ok_r = (d["ok"] & ~d["partial"]).mean()
    split_r = d["partial"].mean()
    ref_r = (~d["ok"]).mean()
    summary.append({
        "事件": ev["name"], "交易日": len(d),
        "波动率峰值": f"{d['vol'].max():.0%}",
        "正常报价率": f"{ok_r:.0%}", "L3分拆": f"{split_r:.0%}",
        "完全拒绝": f"{ref_r:.0%}",
    })
print(pd.DataFrame(summary).to_string(index=False))

print("\n=== 按事件分级 × 报价状态 ===")
piv = all_df.groupby("level").apply(
    lambda g: pd.Series({
        "交易日": len(g),
        "正常报价率": f"{(g['ok'] & ~g['partial']).mean():.0%}",
        "L3分拆率": f"{g['partial'].mean():.0%}",
        "拒绝率": f"{(~g['ok']).mean():.0%}",
        "δ均值": f"{g[g['ok']]['delta'].mean():.1%}" if g["ok"].any() else "-",
    }), include_groups=False)
print(piv.to_string())

# 前瞻覆盖（按分级）
print("\n=== t+1 前瞻覆盖率（按分级）===")
for lv in ["normal", "elevated", "crisis", "extreme"]:
    sub_all = []
    for key in EVENTS:
        d = all_df[all_df["event"] == key].reset_index(drop=True)
        for i in range(len(d) - 1):
            r = d.iloc[i]
            if r["level"] == lv and r["ok"] and not r["partial"]:
                hit = r["lo"] <= d.iloc[i + 1]["actual"] <= r["hi"]
                sub_all.append(hit)
    if sub_all:
        print(f"  {lv:9s}: {sum(sub_all)}/{len(sub_all)} = "
              f"{sum(sub_all)/len(sub_all):.0%}")
