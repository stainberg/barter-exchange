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

LANG = "zh"  # 默认中文；--lang en 切换

T = {
    "zh": {
        "ref_price": "参考成交价",
        "based_on": "（基于 {date} 全球现货锚定，昨日公道价）",
        "band": "议价区间",
        "band_ratio": "上限/下限",
        "freshness": "数据新鲜度",
        "disclaimer": "※ 本结果为物物兑换参考区间，不构成定价，请在此区间内自行谈判",
        "offer_in": "✓ 对方出价 {qty:g} {unit} 在区间内",
        "offer_low": "✗ 对方出价 {qty:g} {unit} 低于区间下限 —— 对你不利",
        "offer_high": "✓ 对方出价 {qty:g} {unit} 高于区间上限 —— 对你有利",
        "wide_warn": "⚠ 区间接近宽度上限（上限 hi/lo=1.40x）：建议小额试单",
        "no_ref": "✗ 无法给出参考值",
        "degraded": "⚡ 降级模式：{side} 当前剧烈波动，已自动分拆报价",
        "trust_leg": "✓ 可信段",
        "manual_leg": "✗ 波动段: {via} → {side} 请用本地现货知识谈判",
        "partial_note": "※ 分拆报价只担保稳定侧的价值锚定，不构成完整定价",
    },
    "en": {
        "ref_price": "Reference price",
        "based_on": "(anchored to global spot, {date})",
        "band": "Negotiation band",
        "band_ratio": "hi/lo",
        "freshness": "Data freshness",
        "disclaimer": "※ Reference band for barter negotiation — not a price quote.",
        "offer_in": "✓ Counterparty offer {qty:g} {unit} is within the band",
        "offer_low": "✗ Counterparty offer {qty:g} {unit} below band — unfavorable to you",
        "offer_high": "✓ Counterparty offer {qty:g} {unit} above band — favorable to you",
        "wide_warn": "⚠ Band near width cap (max hi/lo=1.40x): trade small first",
        "no_ref": "✗ No reference available",
        "degraded": "⚡ Degraded mode: {side} is highly volatile — split quote",
        "trust_leg": "✓ Vouched leg",
        "manual_leg": "✗ Volatile leg: {via} → {side} — negotiate with local knowledge",
        "partial_note": "※ Split quote vouches only the stable side.",
    },
}


def t(key, **kw):
    return T[LANG][key].format(**kw) if kw else T[LANG][key]


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


def show_quote(q, code_a, qty_a, code_b, qty_b, detail=False, display=None):
    """display = (用户输入数量, 用户输入单位A, 规范单位B) 用于输出换算。"""
    from .units import to_canonical, from_canonical
    from .taxonomy import get_item as gi

    if not q.ok:
        print(f"\n{t('no_ref')}：{q.reason}")
        if q.sides:
            for s in q.sides:
                for w in s.warnings:
                    print(f"  ⚠ {w}")
        return 1

    # 显示单位：输入侧用用户单位，输出侧用 B 的规范单位
    if display:
        qty_in, unit_a, canon_b = display
    else:
        qty_in, unit_a, canon_b = qty_a, q.sides[0].unit, q.sides[1].unit

    sa, sb = q.sides
    # 把引擎的比率（规范单位）换算为显示单位
    # ratio 是 1 canon_a ≈ r canon_b；显示为 1 unit_a ≈ r' canon_b
    f_a = to_canonical(1, unit_a, sa.unit)   # 1 用户单位 = f_a 规范单位
    disp_mid = q.ratio_mid * f_a
    disp_lo = q.ratio_lo * f_a
    disp_hi = q.ratio_hi * f_a
    unit_b = canon_b

    if q.partial:
        from .taxonomy import get_item
        mi = get_item(q.intermediary)
        print(f"\n{'=' * 56}")
        print(f"  {t('degraded', side=q.manual_side)}")
        print(f"{'=' * 56}")
        print(f"  {t('ref_price')}（{sa.as_of}）: "
              f"{qty_in:g} {unit_a} {sa.name} ≈ {disp_mid*qty_in:.4g} {mi['unit']} {mi['name']}")
        print(f"  {t('trust_leg')}: {disp_lo*qty_in:.4g} ~ {disp_hi*qty_in:.4g} {mi['unit']} {mi['name']}"
              f"（±{q.delta:.0%}）")
        print(f"  {t('manual_leg', via=mi['name'], side=q.manual_side)}")
        print(f"  {t('freshness')}: {q.freshness_label}")
        print(f"  {t('partial_note')}")
        if detail:
            print("\n" + q.detail)
        return 0

    band = q.ratio_hi / q.ratio_lo
    print(f"\n{'=' * 56}")
    print(f"  {t('ref_price')}: {qty_in:g} {unit_a} {sa.name} ≈ "
          f"{disp_mid*qty_in:.4g} {unit_b} {sb.name}")
    print(f"  {t('based_on', date=sa.as_of)}")
    print(f"  {t('band')}: {disp_lo*qty_in:.4g} ~ {disp_hi*qty_in:.4g} {unit_b} {sb.name}"
          f"  ({t('band_ratio')} = {band:.2f}x)")
    print(f"{'=' * 56}")
    print(f"  {t('freshness')}: {q.freshness_label}")
    if q.trend_note:
        print(f"  📈 {q.trend_note}")
    if q.delta >= 0.14:
        print(f"  {t('wide_warn')}")
    print(f"  {t('disclaimer')}")
    if detail:
        print("\n" + q.detail)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="易货换算工具 MVP")
    p.add_argument("goods", nargs="*",
                   help="货物A 数量 [单位] 货物B（单位可选，默认族谱规范单位）")
    p.add_argument("--qty-b", type=float, default=None, help="对方出价（判断公道性）")
    p.add_argument("--unit-b", default=None, help="对方出价的单位")
    p.add_argument("--list", action="store_true", help="列出全部商品")
    p.add_argument("--detail", action="store_true", help="显示计算明细")
    p.add_argument("--calibrate", nargs=2, metavar=("CODE", "K"), help="本地校准K值")
    p.add_argument("--pack", default="data/datapack_latest.json", help="数据包路径")
    p.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言")
    p.add_argument("--now", default=None,
                   help="回放模式：指定'当下'日期 YYYY-MM-DD（用于演示历史数据包）")
    args = p.parse_args(argv)

    global LANG
    LANG = args.lang

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

    # 解析: 货物A 数量 [单位A] 货物B（3 或 4 个位置参数）
    if len(args.goods) not in (3, 4):
        # 交互模式
        print("易货换算工具 MVP · 输入格式: 货物A 数量 [单位] 货物B（如: 小麦 500 kg 柴油）")
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
            if len(parts) not in (3, 4):
                print("格式: 货物A 数量 [单位] 货物B"); continue
            _run_interactive(parts, args.pack, calib)
        return 0

    return _run_cli(args.goods, args.qty_b, args.unit_b, args.detail,
                    args.pack, calib, now=now)


def _parse_goods(parts):
    """解析 [货物A, 数量, (单位A)?, 货物B] → (code_a, qty, unit_a, code_b)。"""
    from .units import UNITS
    from .taxonomy import get_item as gi
    a, qty_s = parts[0], parts[1]
    if len(parts) == 4:
        unit_a, b = parts[2], parts[3]
    else:
        unit_a, b = None, parts[2]
    ca, cb = find_code(a), find_code(b)
    if not ca or not cb:
        return None, None, None, None
    unit_a = unit_a or gi(ca)["unit"]
    return ca, float(qty_s), unit_a, cb


def _run_interactive(parts, pack_path, calib):
    try:
        ca, qty, unit_a, cb = _parse_goods(parts)
        if not ca:
            print(f"未知商品（用 --list 查看）"); return
        _do_quote(ca, qty, unit_a, cb, None, None, True, pack_path, calib)
    except ValueError as e:
        print(f"输入错误: {e}")


def _run_cli(goods, qty_b, unit_b, detail, pack_path, calib, now=None):
    ca, qty, unit_a, cb = _parse_goods(goods)
    if not ca:
        bad = goods[0] if not find_code(goods[0]) else goods[-1]
        print(f"未知商品: {bad}（用 --list 查看）"); return 1
    try:
        return _do_quote(ca, qty, unit_a, cb, qty_b, unit_b, detail,
                         pack_path, calib, now)
    except ValueError as e:
        print(f"输入错误: {e}"); return 1


def _do_quote(ca, qty, unit_a, cb, qty_b, unit_b, detail, pack_path, calib, now=None):
    """单位换算边界（units.py）→ 引擎（规范单位）→ 输出（用户单位）。"""
    from .units import to_canonical, from_canonical
    from .taxonomy import get_item as gi

    item_a, item_b = gi(ca), gi(cb)
    canon_a, canon_b = item_a["unit"], item_b["unit"]

    qty_canon = to_canonical(qty, unit_a, canon_a)   # 用户单位 → 规范单位
    pack = DataPack.load(pack_path)
    q = quote(ca, qty_canon, cb, None, pack, calib, now=now)
    rc = show_quote(q, ca, qty, cb, None, detail,   # 展示用原始输入
                    display=(qty, unit_a, canon_b))
    if rc == 0 and qty_b is not None and q.ok and not q.partial:
        # 对方出价换算到同一规范单位再比较
        ub = unit_b or canon_b
        qty_b_canon = to_canonical(qty_b, ub, canon_b)
        total_lo = q.ratio_lo * qty_canon
        total_hi = q.ratio_hi * qty_canon
        if total_lo <= qty_b_canon <= total_hi:
            print(f"  {t('offer_in', qty=qty_b, unit=ub)}")
        elif qty_b_canon < total_lo:
            print(f"  {t('offer_low', qty=qty_b, unit=ub)}")
        else:
            print(f"  {t('offer_high', qty=qty_b, unit=ub)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
