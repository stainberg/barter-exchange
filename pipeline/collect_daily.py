#!/usr/bin/env python3
"""每日采集：从已验证的免费源拉取锚定品价格。

覆盖（数据源方案 v0.2 §2）：
  - FRED：WTI / Brent 原油现货（日频）、天然气（日频）
  - gold-api.com：黄金、白银、铜、铂、钯（实时）
  - FRED 月频镜像：小麦/大米/玉米/豆油/糖/铝/尿素（v0.2 分层策略）
多源设计：能源 = FRED(WTI) + FRED(Brent)，金属暂为单源（δ_data 给下限）。

输出：data/raw/YYYY-MM-DD.json（原始快照，供 build_pack 使用）
"""
import csv
import io
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "curl/7.88.1"}  # FRED 对自定义 UA 会限速/挂起，用中性 UA

FRED_DAILY = {
    "wti": "DCOILWTICO",
    "brent": "DCOILBRENTEU",
    "natgas": "DHHNGSP",
}
FRED_MONTHLY = {   # 世界银行粉单的 FRED 镜像
    "wheat": "PWHEAMTUSDM", "maize": "PMAIZMTUSDM", "rice": "PRICENPQUSDM",
    "sugar": "PSUGAISAUSDM", "soyoil": "PSOYBUSDM", "aluminum": "PALUMUSDM",
    # 尿素：FRED 无对应 WB 序列（PUREAUSDM 非尿素），v0.3 由 commodities-api 补
}
GOLD_API = {  # 实时现货，单位：USD/金衡盎司；铜为 USD/磅
    "gold": "XAU", "silver": "XAG", "copper": "HG",
}


def fetch(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=45).read()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)



def fred_csv(series: str, days: int = 40) -> list[tuple[str, float]]:
    today = datetime.now(timezone.utc).date()
    start = today.toordinal() - days
    from datetime import date as date_t
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
           f"&cosd={date_t.fromordinal(start)}&coed={today}")
    rows = list(csv.reader(io.StringIO(fetch(url).decode())))
    out = []
    for r in rows[1:]:
        if len(r) == 2 and r[1] not in ("", "."):
            out.append((r[0], float(r[1])))
    return out


def collect() -> dict:
    snap = {"collected_at": datetime.now(timezone.utc).isoformat(),
            "sources": {}}

    for name, series in FRED_DAILY.items():
        try:
            data = fred_csv(series)
            snap["sources"][name] = {"series": series, "daily": data[-25:]}
        except Exception as e:
            snap["sources"][name] = {"error": str(e)}

    for name, sym in GOLD_API.items():
        try:
            j = json.loads(fetch(f"https://api.gold-api.com/price/{sym}"))
            snap["sources"][name] = {"price": j["price"],
                                     "as_of": j["updatedAt"]}
        except Exception as e:
            snap["sources"][name] = {"error": str(e)}

    for name, series in FRED_MONTHLY.items():
        try:
            data = fred_csv(series, days=400)
            snap["sources"][name] = {"series": series, "monthly": data[-14:]}
        except Exception as e:
            snap["sources"][name] = {"error": str(e)}

    return snap


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    snap = collect()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"data/raw/{day}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    ok = sum(1 for v in snap["sources"].values() if "error" not in v)
    print(f"采集完成: {path}（{ok}/{len(snap['sources'])} 源成功）")
