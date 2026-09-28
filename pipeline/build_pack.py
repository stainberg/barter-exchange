#!/usr/bin/env python3
"""打包：原始快照 → 引擎可消费的数据包（barter/datapack.py 的 schema）。

单位归一（对齐 taxonomy.py 的交易单位）：
  gold/silver: gold-api USD/金衡盎司 → 盎司 ✓（同名单位）
  copper:      gold-api HG = USD/磅 → 吨（×2204.62）
  crude:       FRED WTI/Brent USD/桶 → 桶 ✓（多源中位数 → δ_data）
  wheat/rice/maize/soyoil/aluminum/urea: FRED 月频 USD/吨 → 吨 ✓
  sugar:       FRED PSUGAISAUSDM = 美分/磅 → USD/公斤（×0.0220462）
波动率：日频源用 20 日滚动年化；月频源用近 24 个月收益率年化（标注口径差异）。
"""
import glob
import json
import math
import os
import subprocess
from datetime import datetime, timezone


def git_head() -> str:
    """当前构建所在的 git commit——数据包与公开历史的绑定锚点（DATA_SOURCES §信任根）。
    验证者凭此 commit 在任意镜像（GitHub/GitLab/IPFS）核对包的存在性。"""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""

TROY_OZ_PER_GRAM = 1 / 31.1035
LB_PER_TONNE = 2204.62
CENTS_LB_TO_USD_KG = 0.01 * 2.20462


def ann_vol_daily(prices: list[float], window: int = 20) -> float:
    if len(prices) < 6:
        return 0.20
    rets = [math.log(prices[i] / prices[i - 1])
            for i in range(max(1, len(prices) - window), len(prices))]
    if len(rets) < 5:
        return 0.20
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(252), 4)


def ann_vol_monthly(prices: list[float]) -> float:
    if len(prices) < 7:
        return 0.20
    rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(12), 4)


def build(raw_path: str) -> dict:
    snap = json.load(open(raw_path, encoding="utf-8"))
    src = snap["sources"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    anchors = {}

    # --- 能源：WTI + Brent 多源中位数（δ_data 首次真实生效） ---
    crude_sources = {}
    crude_prices = []
    for key, label in (("wti", "FRED-WTI"), ("brent", "FRED-Brent")):
        s = src.get(key, {})
        if "daily" in s and s["daily"]:
            crude_sources[label] = s["daily"][-1][1]
            crude_prices.append(s["daily"][-1][1])
            crude_asof = s["daily"][-1][0]
            crude_hist = [p for _, p in s["daily"]]
            crude_vol = ann_vol_daily(crude_hist)
    if crude_prices:
        anchors["crude"] = {
            "price_usd_per_unit": sorted(crude_prices)[len(crude_prices) // 2],
            "sources": crude_sources,
            "vol20d_ann": crude_vol,
            "history_12m": crude_hist[-12:],
            "as_of": crude_asof,
            "freq": "daily",
        }

    # --- 贵金属 + 铜：gold-api 实时 ---
    conv = {"gold": 1.0, "silver": 1.0, "copper": LB_PER_TONNE}
    for code, factor in conv.items():
        s = src.get(code, {})
        if "price" in s:
            anchors[code] = {
                "price_usd_per_unit": round(s["price"] * factor, 6),
                "sources": {"gold-api": round(s["price"] * factor, 6)},
                "vol20d_ann": 0.15,   # v0.2 无历史，保守默认；v0.3 落库后实算
                "history_12m": [],
                "as_of": s["as_of"][:10],
                "freq": "daily",
            }

    # --- 月频锚定品：FRED 镜像（分层策略 §4 路径一） ---
    monthly_conv = {"wheat": 1.0, "maize": 1.0, "rice": 1.0,
                    "soyoil": 1.0, "aluminum": 1.0, "urea": 1.0,
                    "sugar": CENTS_LB_TO_USD_KG}
    for code, factor in monthly_conv.items():
        s = src.get(code, {})
        if "monthly" in s and s["monthly"]:
            hist = [p * factor for _, p in s["monthly"]]
            anchors[code] = {
                "price_usd_per_unit": round(hist[-1], 6),
                "sources": {"FRED-WB": round(hist[-1], 6)},
                "vol20d_ann": ann_vol_monthly(hist),
                "history_12m": [round(v, 6) for v in hist[-12:]],
                "as_of": s["monthly"][-1][0],
                "freq": "monthly",
            }

    pack = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": "FRED daily (energy) + gold-api (metals) + FRED/WB monthly",
        "code_commit": git_head(),
        "anchors": anchors,
    }
    return pack


if __name__ == "__main__":
    raws = sorted(glob.glob("data/raw/*.json"))
    if not raws:
        raise SystemExit("无原始快照，先跑 collect_daily.py")
    pack = build(raws[-1])
    os.makedirs("dist", exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for path in (f"dist/datapack-{day}.json", "dist/datapack-latest.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=1)
    print(f"打包完成: {len(pack['anchors'])} 个锚定品")
    for c, a in sorted(pack["anchors"].items()):
        ns = len(a["sources"])
        print(f"  {c:9s} ${a['price_usd_per_unit']:>12.4g}  "
              f"vol={a['vol20d_ann']:.1%}  源×{ns}  as_of={a['as_of']}")
