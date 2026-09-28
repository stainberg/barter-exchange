"""从世界银行粉单构建真实数据包（含波动率与12月历史）。

锚定价口径 §4.1：CMO 为实物现货基准价（FOB 出口价），不是远月期货价。
多源问题：CMO 为单源，δ_data 在引擎里给下限 2%；
v0.2 接入第二源（如近月期货结算价）后自动生效。
"""
import json
import math
from datetime import datetime

import pandas as pd

from .taxonomy import ANCHORS

HISTORY_N = 12


def build(xlsx_path: str, as_of: str | None = None) -> dict:
    raw = pd.read_excel(xlsx_path, sheet_name="Monthly Prices", skiprows=4)
    raw = raw.rename(columns={raw.columns[0]: "month"})
    raw = raw[raw["month"].astype(str).str.match(r"\d{4}M\d{2}", na=False)]
    raw["date"] = pd.to_datetime(raw["month"].str.replace("M", "-") + "-01")
    raw = raw.set_index("date").sort_index()

    anchors = {}
    for code, meta in ANCHORS.items():
        s = pd.to_numeric(raw[meta["wb_col"]], errors="coerce").dropna()
        if as_of:
            s = s[s.index <= pd.Timestamp(as_of)]
        hist = s.iloc[-HISTORY_N:].tolist()
        # 20日年化波动率 ≈ 月收益率波动 × √12（月度数据近似）
        rets = [math.log(s.iloc[i] / s.iloc[i - 1])
                for i in range(max(1, len(s) - 24), len(s))]
        if len(rets) >= 6:
            m = sum(rets) / len(rets)
            var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
            vol_ann = math.sqrt(var) * math.sqrt(12)
        else:
            vol_ann = 0.25  # 数据不足时保守默认
        anchors[code] = {
            "price_usd_per_unit": round(float(s.iloc[-1]), 6),
            "sources": {"WB-CMO": round(float(s.iloc[-1]), 6)},
            "vol20d_ann": round(vol_ann, 4),
            "history_12m": [round(float(v), 6) for v in hist],
            "as_of": s.index[-1].strftime("%Y-%m-%d"),
        }
    return {
        "generated": datetime.utcnow().isoformat() + "Z",
        "source": "World Bank Commodity Markets (Pink Sheet), 现货基准价",
        "anchors": anchors,
    }


if __name__ == "__main__":
    import sys
    pack = build("data/cmo_monthly.xlsx", as_of=sys.argv[1] if len(sys.argv) > 1 else None)
    out = sys.argv[2] if len(sys.argv) > 2 else "data/datapack_latest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    print(f"数据包已生成: {out}")
    for c, a in pack["anchors"].items():
        print(f"  {c:9s} ${a['price_usd_per_unit']:>12.4g}  vol={a['vol20d_ann']:.1%}  as_of={a['as_of']}")
