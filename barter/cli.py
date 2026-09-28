#!/usr/bin/env python3
"""易货换算工具 CLI（中文）。

用法：
  python -m barter.cli                          # 交互模式
  python -m barter.cli 小麦 500 柴油            # 500公斤小麦 → 多少升柴油
  python -m barter.cli 小麦 500 柴油 --qty-b 120   # 判断对方出价120升是否公道
  python -m barter.cli --list                   # 列出全部商品
  python -m barter.cli --calibrate coffee 5.1   # 本地校准 K 值
  python -m barter.cli 小麦 1 柴油 --detail     # 显示计算明细
"""
import argparse
import sys

from .datapack import DataPack, LocalCalibration
from .engine import quote
from .taxonomy import ANCHORS, LINKED, get_item, all_codes

# 中文名 → 代码
NAME2CODE = {v["name"]: k for k, v in {**ANCHORS, **LINKED}.items()}
# 常用别名
NAME2CODE.update({"面": "flour", "油": "soyoil", "金": "gold", "银": "silver"})


def find_code(s: str) -> str | None:
    if s in all_codes():
        return s
    return NAME2CODE.get(s)


def print_list():
    print("锚定品（价格来自全球现货基准）:")
    for c, v in ANCHORS.items():
        print(f"  {v['name']:8s}({c:9s}) 单位:{v['unit']:4s} 品类:{v['cat']}")
    print("\n挂靠品（K 系数锚定，可本地校准）:")
    for c, v in LINKED.items():
        tags = []
        if v.get("perishable"):
            tags.append("易腐")
        if v.get("seasonal"):
            tags.append("季节性")
        print(f"  {v['name']:12s}({c:12s}) 单位:{v['unit']:4s} 锚:{v['anchor']:8s}"
              f" K={v['K']:.3g} {'[' + ','.join(tags) + ']' if tags else ''}")


def show_quote(q, code_a, qty_a, code_b, qty_b, detail=False):
    if not q.ok:
        print(f"\n✗ 无法给出参考值：{q.reason}")
        if q.sides:
            for s in q.sides:
                for w in s.warnings:
                    print(f"  ⚠ {w}")
        return 1
    sa, sb = q.sides
    if q.partial:
        # L3 分拆报价：ratio 描述的是 稳定侧 → 中介锚
        from .taxonomy import get_item
        mi = get_item(q.intermediary)
        total_lo, total_mid, total_hi = (q.ratio_lo * qty_a, q.ratio_mid * qty_a,
                                         q.ratio_hi * qty_a)
        print(f"\n{'=' * 56}")
        print(f"  ⚡ 降级模式：{q.manual_side} 当前剧烈波动，已自动分拆报价")
        print(f"{'=' * 56}")
        print(f"  参考成交价（{sa.as_of} 现货锚定）: "
              f"{qty_a:g} {sa.unit}{sa.name} ≈ {total_mid:.4g} {mi['unit']}{mi['name']}")
        print(f"  ✓ 可信段: {total_lo:.4g} ~ {total_hi:.4g} {mi['unit']}{mi['name']}"
              f"（±{q.delta:.0%}）")
        print(f"  ✗ 波动段: {mi['name']} → {q.manual_side} 请用本地现货知识谈判")
        print(f"  数据新鲜度: {q.freshness_label}")
        print("  ※ 分拆报价只担保稳定侧的价值锚定，不构成完整定价")
        if detail:
            print("\n" + q.detail)
        return 0
    total_mid = q.ratio_mid * qty_a
    total_lo = q.ratio_lo * qty_a
    total_hi = q.ratio_hi * qty_a
    print(f"\n{'=' * 56}")
    # 双输出（v0.5）：参考成交价 + 议价区间（v0.6 对数对称，AB/BA 自洽）
    band = q.ratio_hi / q.ratio_lo
    print(f"  参考成交价: {qty_a:g} {sa.unit}{sa.name} ≈ "
          f"{total_mid:.4g} {sb.unit}{sb.name}")
    print(f"  （基于 {sa.as_of} 全球现货锚定，昨日公道价）")
    print(f"  议价区间:   {total_lo:.4g} ~ {total_hi:.4g} {sb.unit}{sb.name}"
          f"  （上限/下限 = {band:.2f}x）")
    print(f"{'=' * 56}")
    if qty_b is not None:
        if total_lo <= qty_b <= total_hi:
            print(f"  ✓ 对方出价 {qty_b:g} {sb.unit} 在区间内")
        elif qty_b < total_lo:
            print(f"  ✗ 对方出价 {qty_b:g} {sb.unit} 低于区间下限 —— 对你不利")
        else:
            print(f"  ✓ 对方出价 {qty_b:g} {sb.unit} 高于区间上限 —— 对你有利")
    print(f"  数据新鲜度: {q.freshness_label}")
    if q.trend_note:
        print(f"  📈 {q.trend_note}")
    if q.delta >= 0.14:
        print(f"  ⚠ 区间接近宽度上限（上限 hi/lo=1.40x）：建议小额试单")
    print("  ※ 本结果为物物兑换参考区间，不构成定价，请在此区间内自行谈判")
    if detail:
        print("\n" + q.detail)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="易货换算工具 MVP")
    p.add_argument("goods", nargs="*", help="货物A 数量 货物B")
    p.add_argument("--qty-b", type=float, default=None, help="对方出价（判断公道性）")
    p.add_argument("--list", action="store_true", help="列出全部商品")
    p.add_argument("--detail", action="store_true", help="显示计算明细")
    p.add_argument("--calibrate", nargs=2, metavar=("CODE", "K"), help="本地校准K值")
    p.add_argument("--pack", default="data/datapack_latest.json", help="数据包路径")
    p.add_argument("--now", default=None,
                   help="回放模式：指定'当下'日期 YYYY-MM-DD（用于演示历史数据包）")
    args = p.parse_args(argv)

    now = None
    if args.now:
        from datetime import datetime, timezone
        now = datetime.fromisoformat(args.now).replace(tzinfo=timezone.utc)

    if args.list:
        print_list()
        return 0

    calib = LocalCalibration("data/local_calibration.json")
    if args.calibrate:
        code, k = args.calibrate[0], float(args.calibrate[1])
        c = find_code(code)
        if not c or c in ANCHORS:
            print("只能校准挂靠品的 K 值"); return 1
        calib.set_k(c, k)
        print(f"✓ 已本地校准 {get_item(c)['name']}({c}) K={k}")
        return 0

    if len(args.goods) != 3:
        # 交互模式
        print("易货换算工具 MVP · 输入格式: 货物A 数量 货物B（如: 小麦 500 柴油）")
        print("输入 list 查看商品, q 退出")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line in ("q", "quit", "exit"):
                break
            if line == "list":
                print_list(); continue
            parts = line.split()
            if len(parts) != 3:
                print("格式: 货物A 数量 货物B"); continue
            _run(parts[0], parts[1], parts[2], None, True, args.pack, calib)
        return 0

    return _run(args.goods[0], args.goods[1], args.goods[2],
                args.qty_b, args.detail, args.pack, calib, now=now)


def _run(a, qty, b, qty_b, detail, pack_path, calib, now=None):
    ca, cb = find_code(a), find_code(b)
    if not ca:
        print(f"未知商品: {a}（用 --list 查看）"); return 1
    if not cb:
        print(f"未知商品: {b}（用 --list 查看）"); return 1
    pack = DataPack.load(pack_path)
    q = quote(ca, float(qty), cb, qty_b, pack, calib, now=now)
    return show_quote(q, ca, float(qty), cb, qty_b, detail)


if __name__ == "__main__":
    sys.exit(main())
