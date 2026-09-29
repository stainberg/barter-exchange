#!/usr/bin/env python3
"""PPP 市场采样：从 WFP 全球食品价格数据库提取多地实际零售价。

设计文档 §4.3 + DATA_SOURCES §4 路径三的前置实现。
T9 坐标系：PPP 采样的价格坐标系 = "ppp"，与 benchmark 系分离。

采样策略：
  - 只取"货币稳定市场"（预定义清单：USD/EUR/GBP/JPY/CHF/AUD/CAD 区 +
    经济数据完整的地区）
  - 只取最近 N 个月的数据
  - 本地货币 → USD 用同期汇率（FRED/frankfurter）
  - 同一商品在多个市场的价格取中位数，离散度即 δ_data

输出：data/ppp_samples.json
  {"flour": {"prices_usd": {"US": 0.52, "DE": 0.61, ...},
             "median": 0.485, "dispersion": 0.18, "n_markets": 4, ...}}
"""
import csv
import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

UA = {"User-Agent": "curl/7.88.1"}

# WFP 商品名 → 我们的商品代码
COMMODITY_MAP = {
    "Wheat flour - Retail": "flour",
    "Bread - Retail": "bread",
    "Rice - Retail": "rice",
    "Maize - Retail": "maize",
    "Sugar - Retail": "sugar",
    "Vegetable oil - Retail": "cook_oil_1l",
    "Eggs - Retail": "eggs",
    "Chicken - Retail": "chicken",
    "Diesel - Retail": "diesel",
    "Gasoline - Retail": "gasoline",
}

# 货币稳定市场清单（治理规则：按数据可用性+货币稳定性，每年重算）
STABLE_MARKETS = {
    "United States": "USD",
    "Germany": "EUR",
    "France": "EUR",
    "Japan": "JPY",
    "United Kingdom": "GBP",
    "Australia": "AUD",
    "Canada": "CAD",
    "Switzerland": "CHF",
    "China": "CNY",
    "South Korea": "KRW",
    # 新兴市场稳定参照（可选）
    "Brazil": "BRL",
    "Mexico": "MXN",
    "South Africa": "ZAR",
}

# 简单汇率表（生产环境应由 frankfurter/FRED 实时获取）
FALLBACK_FX = {  # 兑美元，2026-09 近似
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067,
    "AUD": 0.66, "CAD": 0.72, "CHF": 1.12, "CNY": 0.14,
    "KRW": 0.00072, "BRL": 0.18, "MXN": 0.051, "ZAR": 0.055,
}


def load_fx() -> dict:
    """从 frankfurter 获取实时汇率，失败时用 FALLBACK_FX。"""
    try:
        codes = "+".join(k for k in STABLE_MARKETS.values() if k != "USD")
        url = f"https://api.frankfurter.dev/v1/latest?base=USD&symbols={codes.replace('+', ',')}"
        data = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=15).read())
        fx = {"USD": 1.0}
        for cur, rate in data.get("rates", {}).items():
            fx[cur] = 1.0 / rate  # frankfurter 是 USD→外币，取倒数
        return fx
    except Exception:
        return FALLBACK_FX


def sample_ppp(csv_path: str, months_back: int = 6) -> dict:
    """从 WFP CSV 采样多地实际零售价。"""
    fx = load_fx()
    now = datetime.now(timezone.utc)
    cutoff_year = now.year if now.month > months_back else now.year - 1
    cutoff_month = now.month - months_back if now.month > months_back else now.month + (12 - months_back)

    # 收集：{商品代码: {市场: [usd_prices]}}
    samples = defaultdict(lambda: defaultdict(list))

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row["adm0_name"]
            if country not in STABLE_MARKETS:
                continue
            cm = row["cm_name"]
            if cm not in COMMODITY_MAP:
                continue
            year, month = int(row["mp_year"]), int(row["mp_month"])
            if year < cutoff_year or (year == cutoff_year and month < cutoff_month):
                continue
            cur = STABLE_MARKETS[country]
            price_local = float(row["mp_price"])
            price_usd = price_local * fx.get(cur, 0)
            if price_usd > 0:
                samples[COMMODITY_MAP[cm]][country].append(price_usd)

    # 汇总：中位数 + 离散度
    result = {}
    for code, markets in samples.items():
        market_medians = {}
        for country, prices in markets.items():
            prices.sort()
            market_medians[country] = prices[len(prices) // 2]
        vals = list(market_medians.values())
        if len(vals) < 2:
            continue
        med = sorted(vals)[len(vals) // 2]
        var = sum((v - med) ** 2 for v in vals) / len(vals)
        result[code] = {
            "prices_usd": market_medians,
            "median": round(med, 6),
            "dispersion": round(math.sqrt(var) / med, 4) if med > 0 else 0,
            "n_markets": len(vals),
            "sampled_at": now.isoformat(),
        }
    return result


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/wfp_foodprices.csv"
    if not os.path.exists(csv_path):
        sys.exit(f"数据文件不存在: {csv_path}")
    print(f"采样中: {csv_path}")
    result = sample_ppp(csv_path)
    with open("data/ppp_samples.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\n采样完成: {len(result)} 种商品")
    for code, d in sorted(result.items()):
        print(f"  {code:12s} 中位数 ${d['median']:.4g}  "
              f"离散度 {d['dispersion']:.1%}  市场数 {d['n_markets']}")
