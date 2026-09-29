#!/usr/bin/env python3
"""生成 CI 用的小型合成世界银行粉单（替代 700KB 真实文件）。
只含引擎需要的锚定品列 + 25 个月合成数据。"""
import pandas as pd

MONTHS = [f"2024M{m:02d}" for m in range(1, 13)] + \
         [f"2025M{m:02d}" for m in range(1, 13)] + ["2026M01"]

# 列名必须与 barter/build_datapack.py + taxonomy.py 的 wb_col 一致
COLS = {
    "Wheat, US HRW": 265.0,
    "Rice, Thai 5% ": 540.0,
    "Maize": 190.0,
    "Soybean oil": 980.0,
    "Sugar, world": 0.44,
    "Crude oil, average": 78.0,
    "Gold": 2600.0,
    "Silver": 31.0,
    "Copper": 9100.0,
    "Aluminum": 2500.0,
    "Urea ": 330.0,
}

rows = []
for i, m in enumerate(MONTHS):
    row = {"month": m}
    for c, base in COLS.items():
        # 微波动，避免零方差
        row[c] = base * (1 + 0.01 * ((i % 5) - 2))
    rows.append(row)

df = pd.DataFrame(rows)
df.to_excel("data/cmo_monthly_test.xlsx", sheet_name="Monthly Prices",
            index=False, startrow=4, header=True)
print(f"测试夹具已生成: data/cmo_monthly_test.xlsx ({len(MONTHS)} 个月)")
