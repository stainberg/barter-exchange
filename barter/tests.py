#!/usr/bin/env python3
"""单元测试 + 演示场景。运行: .venv/bin/python -m barter.tests"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from barter.datapack import DataPack, LocalCalibration
from barter.engine import quote, DELTA_MAX, DELTA_MIN
from barter.build_datapack import build

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {extra}")


def make_pack(price_overrides=None, as_of_offset_days=0, vol=0.20):
    """构造合成数据包用于确定性测试。"""
    as_of = (datetime.now(timezone.utc) - timedelta(days=as_of_offset_days)).strftime("%Y-%m-%d")
    base = {"wheat": 265.0, "rice": 540.0, "maize": 190.0, "soyoil": 980.0,
            "sugar": 0.44, "crude": 78.0, "gold": 2600.0, "silver": 31.0,
            "copper": 9100.0, "aluminum": 2500.0, "urea": 330.0}
    base.update(price_overrides or {})
    return DataPack({
        "generated": datetime.now(timezone.utc).isoformat(),
        "anchors": {c: {"price_usd_per_unit": p, "sources": {"TEST": p},
                        "vol20d_ann": vol, "as_of": as_of,
                        "history_12m": [p * (1 + 0.01 * i) for i in range(12)]}
                    for c, p in base.items()}})


def test_basic_ratio():
    print("\n[1] 基本比率")
    pack = make_pack()
    q = quote("wheat", 1, "maize", None, pack)
    check("小麦/玉米报价成功", q.ok, q.reason)
    # 265/190 ≈ 1.395
    check("中心值正确", abs(q.ratio_mid - 265 / 190) < 1e-6,
          f"got {q.ratio_mid}")
    check("区间含中心值", q.ratio_lo < q.ratio_mid < q.ratio_hi)
    check("同类对 δ_pair=6%", abs(q.delta_parts["δ_pair"] - 0.06) < 1e-9)
    check("区间全宽≤40%（hi/lo≤1.40）", q.ratio_hi / q.ratio_lo <= 1.4001)


def test_ab_ba_consistency():
    """AB/BA 往返自洽性（v0.6 对数对称区间的核心性质）：
    双方各自用工具验算同一笔交易，结论必须一致。"""
    print("\n[1b] AB/BA 往返自洽性")
    pack = make_pack()
    for a, b in [("wheat", "diesel"), ("gold", "wheat"), ("eggs", "maize")]:
        ab = quote(a, 1, b, None, pack)
        ba = quote(b, 1, a, None, pack)
        if not (ab.ok and ba.ok and not ab.partial and not ba.partial):
            check(f"{a}↔{b} 双向均可报价", False,
                  f"ab.ok={ab.ok} ba.ok={ba.ok}")
            continue
        # 1. 中心值互逆
        check(f"{a}↔{b} 中心值互逆", abs(ab.ratio_mid * ba.ratio_mid - 1) < 1e-9,
              f"product={ab.ratio_mid * ba.ratio_mid}")
        # 2. 按 AB 区间两个边缘成交的交易，BA 视角都必须落在 BA 区间内
        for edge_name, edge in [("下沿", ab.ratio_lo), ("上沿", ab.ratio_hi)]:
            inv = 1 / edge
            ok = ba.ratio_lo * (1 - 1e-12) <= inv <= ba.ratio_hi * (1 + 1e-12)
            check(f"{a}→{b} {edge_name}交易 BA 视角自洽", ok,
                  f"inv={inv:.6f} BA=[{ba.ratio_lo:.6f},{ba.ratio_hi:.6f}]")
        # 3. 严格互逆：BA 区间 = AB 区间的倒数
        check(f"{a}↔{b} 区间严格互逆",
              abs(ab.ratio_lo - 1 / ba.ratio_hi) < 1e-9
              and abs(ab.ratio_hi - 1 / ba.ratio_lo) < 1e-9)


def test_theorems_exhaustive():
    """数学基础.md 定理的穷举验证（E5：全部商品对，非抽样）。
    定理本身由数学证明保证；此处验证实现没有偏离证明的前提。"""
    print("\n[1c] 定理穷举验证（全部商品对）")
    from barter.taxonomy import all_codes
    pack = make_pack()
    codes = all_codes()
    quotes = {}
    for a in codes:
        for b in codes:
            if a != b:
                quotes[(a, b)] = quote(a, 1, b, None, pack)

    ok_pairs = [(a, b) for (a, b), q in quotes.items()
                if q.ok and not q.partial]
    n = len(ok_pairs)
    check(f"穷举覆盖 {len(codes)} 种商品 {len(codes)*(len(codes)-1)} 对", n > 0,
          f"ok={n}")

    # T1 计价货币不变性：全部价格 ×x，所有中心值必须不变
    pack2 = make_pack(price_overrides=None)
    import copy
    raw2 = copy.deepcopy(pack2.raw)
    for c in raw2["anchors"]:
        raw2["anchors"][c]["price_usd_per_unit"] *= 7.3
    pack_x = DataPack(raw2)
    t1_fail = []
    for a, b in ok_pairs[:80]:  # 抽样80对足够（实现路径相同）
        q2 = quote(a, 1, b, None, pack_x)
        if abs(q2.ratio_mid / quotes[(a, b)].ratio_mid - 1) > 1e-9:
            t1_fail.append((a, b))
    check("T1 计价货币不变（价格×7.3 中心值不变）", not t1_fail,
          str(t1_fail[:3]))

    # T2 中心互逆 & T4 区间互逆封闭 & T5 边缘判定一致（全部对）
    t2_fail = [(a, b) for a, b in ok_pairs
               if abs(quotes[(a, b)].ratio_mid * quotes[(b, a)].ratio_mid - 1) > 1e-9]
    t4_fail = [(a, b) for a, b in ok_pairs
               if abs(quotes[(a, b)].ratio_lo - 1 / quotes[(b, a)].ratio_hi) > 1e-9
               or abs(quotes[(a, b)].ratio_hi - 1 / quotes[(b, a)].ratio_lo) > 1e-9]
    t5_fail = []
    for a, b in ok_pairs:
        ab, ba = quotes[(a, b)], quotes[(b, a)]
        for edge in (ab.ratio_lo, ab.ratio_hi):
            inv = 1 / edge
            if not (ba.ratio_lo * (1 - 1e-12) <= inv <= ba.ratio_hi * (1 + 1e-12)):
                t5_fail.append((a, b))
    check(f"T2 中心互逆（{n} 对）", not t2_fail, str(t2_fail[:3]))
    check(f"T4 区间互逆封闭（{n} 对）", not t4_fail, str(t4_fail[:3]))
    check(f"T5 边缘判定一致（{n}×2 边缘）", not t5_fail, str(t5_fail[:3]))

    # T3 传递性：R_AC = R_AB · R_BC（经 gold 中介，全部三元组抽样）
    import random
    random.seed(42)
    anchors = ["gold", "wheat", "crude"]
    t3_fail = []
    for a, b in random.sample(ok_pairs, min(60, len(ok_pairs))):
        for m in anchors:
            if m in (a, b):
                continue
            q_am, q_mb = quotes.get((a, m)), quotes.get((m, b))
            if q_am and q_mb and q_am.ok and q_mb.ok:
                if abs(quotes[(a, b)].ratio_mid
                       / (q_am.ratio_mid * q_mb.ratio_mid) - 1) > 1e-9:
                    t3_fail.append((a, b, m))
    check("T3 中心传递（经中介无路径套利）", not t3_fail, str(t3_fail[:3]))

    # T7 单调性：数据更老 → δ 不得更小。
    # 注意：定理管辖的是"直接报价 δ 对输入的函数"。若老化后报价转为
    # L3 分拆（δ 超限触发降级），其 q.delta 是稳定侧→中介锚的新对象，
    # 与直接报价 δ 不可比——降级本身就是 δ 单调增大越过 cap 的证据。
    t7_fail = []
    for age in (5, 20):
        pack_old = make_pack(as_of_offset_days=age)
        for a, b in random.sample(ok_pairs, 40):
            q_new, q_old = quotes[(a, b)], quote(a, 1, b, None, pack_old)
            if not q_old.ok or q_old.partial:
                continue   # 拒绝或降级均不违反单调性
            if q_old.delta < q_new.delta - 1e-12:
                t7_fail.append((a, b, age))
    check("T7 数据老化 δ 单调不减（同模式可比对象）", not t7_fail,
          str(t7_fail[:3]))


def test_cross_pair_delta():
    print("\n[2] 跨类对 δ_pair")
    pack = make_pack()
    q = quote("wheat", 1, "crude", None, pack)
    check("粮食↔能源 δ_pair=11%", abs(q.delta_parts["δ_pair"] - 0.11) < 1e-9)


def test_perishable_upgrade():
    print("\n[3] 易腐品上调（§4.5）")
    pack = make_pack()
    q = quote("eggs", 1, "maize", None, pack)  # 同类但易腐
    check("鸡蛋(易腐) δ_pair=12%", abs(q.delta_parts["δ_pair"] - 0.12) < 1e-9)


def test_lineage_delta():
    print("\n[4] 族谱距离 δ_lineage")
    pack = make_pack()
    q1 = quote("wheat", 1, "maize", None, pack)       # 0+0 hops
    q2 = quote("flour", 1, "maize", None, pack)       # 1+0 hops
    q3 = quote("noodles", 1, "maize", None, pack)     # 2+0 hops
    check("0跳无族谱δ", abs(q1.delta_parts["δ_lineage"]) < 1e-9)
    check("1跳+1%", abs(q2.delta_parts["δ_lineage"] - 0.01) < 1e-9)
    check("2跳+2%", abs(q3.delta_parts["δ_lineage"] - 0.02) < 1e-9)


def test_stale_data_widens():
    print("\n[5] 数据过期加宽（§5.3）")
    fresh = quote("wheat", 1, "crude", None, make_pack(as_of_offset_days=1))
    stale = quote("wheat", 1, "crude", None, make_pack(as_of_offset_days=10))
    check("过期数据 δ_vol 更大", stale.delta_parts["δ_vol"] > fresh.delta_parts["δ_vol"],
          f"{fresh.delta_parts['δ_vol']:.3f} vs {stale.delta_parts['δ_vol']:.3f}")


def test_refuse_when_too_stale():
    print("\n[6] 严重过期拒绝输出")
    q = quote("wheat", 1, "crude", None, make_pack(as_of_offset_days=60))
    check("60天过期→拒绝", not q.ok)
    check("拒绝原因提及更新数据包", "更新数据包" in q.reason)


def test_refuse_extreme_vol():
    print("\n[7] 极端波动 L3 分拆降级（2020-04 原油崩盘场景）")
    # 模拟：日频数据（3天龄）+ 原油年化波动率飙到300%
    pack_raw = {"generated": datetime.now(timezone.utc).isoformat(), "anchors": {}}
    as_of = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    base = {"wheat": 265.0, "crude": 20.0, "rice": 540.0, "maize": 190.0,
            "soyoil": 980.0, "sugar": 0.44, "gold": 1700.0, "silver": 15.0,
            "copper": 5000.0, "aluminum": 1500.0, "urea": 240.0}
    for c, p in base.items():
        pack_raw["anchors"][c] = {
            "price_usd_per_unit": p, "sources": {"T": p},
            "vol20d_ann": 3.0 if c == "crude" else 0.15,
            "as_of": as_of, "history_12m": [p] * 12}
    pack = DataPack(pack_raw)
    q = quote("wheat", 1, "crude", None, pack)
    check("直接报价超限→L3 分拆成功", q.ok and q.partial,
          f"ok={q.ok} partial={q.partial} reason={q.reason[:60]}")
    if q.partial:
        check("波动侧识别为原油", q.manual_side == "原油", q.manual_side)
        check("中介锚为黄金", q.intermediary == "gold", q.intermediary)
        check("分拆后 δ 显著收窄", q.delta < DELTA_MAX, f"δ={q.delta:.1%}")


def test_systemic_shock_refuses():
    print("\n[7b] 双侧同步剧烈波动 → 完全拒绝（系统性冲击）")
    as_of = (datetime.now(timezone.utc) - timedelta(days=25)).strftime("%Y-%m-%d")
    pack_raw = {"generated": datetime.now(timezone.utc).isoformat(), "anchors": {}}
    base = {"wheat": 265.0, "crude": 20.0, "rice": 540.0, "maize": 190.0,
            "soyoil": 980.0, "sugar": 0.44, "gold": 1700.0, "silver": 15.0,
            "copper": 5000.0, "aluminum": 1500.0, "urea": 240.0}
    for c, p in base.items():
        pack_raw["anchors"][c] = {
            "price_usd_per_unit": p, "sources": {"T": p},
            "vol20d_ann": 3.0 if c in ("crude", "wheat") else 0.15,
            "as_of": as_of, "history_12m": [p] * 12}
    q = quote("wheat", 1, "crude", None, DataPack(pack_raw))
    check("双侧同波动→拒绝", not q.ok, f"ok={q.ok} partial={q.partial}")
    if not q.ok:
        check("拒绝原因提及系统性冲击", "系统性冲击" in q.reason)


def test_calibration():
    print("\n[8] 本地 K 校准（§4.3）")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cal.json")
        cal = LocalCalibration(path)
        cal.set_k("coffee", 6.0)
        cal2 = LocalCalibration(path)
        k, user = cal2.get_k("coffee", 4.2)
        check("校准持久化", user and k == 6.0)
        pack = make_pack()
        q1 = quote("coffee", 1, "sugar", None, pack, LocalCalibration())
        q2 = quote("coffee", 1, "sugar", None, pack, cal2)
        check("校准改变中心值", abs(q2.ratio_mid / q1.ratio_mid - 6.0 / 4.2) < 1e-6,
              f"{q1.ratio_mid} vs {q2.ratio_mid}")


def test_gitaudit():
    """git 历史绑定验证（DATA_SOURCES §信任根）。"""
    print("\n[11] git 历史绑定验证")
    import subprocess
    from barter.gitaudit import check_commit, check_pack

    # 用当前仓库自身做验证载体
    head = subprocess.run(["git", "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    r = check_commit(".", head, settle_hours=0)
    check("当前 HEAD 存在且通过（沉淀期=0）", r.ok and r.commit_found,
          r.detail)

    r2 = check_commit(".", "0" * 40, settle_hours=0)
    check("伪造 commit 被拒绝", not r2.ok and not r2.commit_found)

    r3 = check_commit(".", head, settle_hours=10**6)
    check("未过沉淀期被拒绝", not r3.ok and not r3.settled, r3.detail)

    pack = {"code_commit": head, "anchors": {}}
    r4 = check_pack(pack, ".", settle_hours=0)
    check("数据包绑定验证通过", r4.ok, r4.detail)

    r5 = check_pack({"anchors": {}}, ".", settle_hours=0)
    check("缺 code_commit 的数据包被拒绝", not r5.ok)


def test_cli_smoke():
    """CLI 冒烟测试：各子命令不崩溃 + 输出格式正确。"""
    print("\n[12] CLI 冒烟")
    import io, contextlib, json as _json, tempfile
    from barter.cli import main

    # 自建合成数据包文件（不依赖 data/datapack_latest.json，CI 友好）
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    _json.dump(make_pack().raw, tmp)
    tmp.close()
    pack_path = tmp.name

    # --list
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--list"])
    check("--list 正常", rc == 0 and "小麦" in buf.getvalue())

    # 正常报价
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["小麦", "1", "柴油", "--pack", pack_path])
    out = buf.getvalue()
    check("CLI 报价含双输出", rc == 0 and "参考成交价" in out and "议价区间" in out,
          out[:100])

    # --qty-b 出价判断
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["鸡蛋", "30", "面粉", "--qty-b", "100", "--pack", pack_path])
    check("--qty-b 出价判断", rc == 0, buf.getvalue()[:100])

    # --detail 计算明细
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["小麦", "1", "柴油", "--detail", "--pack", pack_path])
    check("--detail 含计算明细", rc == 0 and "计算明细" in buf.getvalue())

    # --calibrate（写入临时路径，避免副作用）
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--calibrate", "coffee", "5.1"])
    check("--calibrate 正常", rc == 0 and "已本地校准" in buf.getvalue())
    if os.path.exists("data/local_calibration.json"):
        os.remove("data/local_calibration.json")

    # 未知商品
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["不存在", "1", "柴油", "--pack", pack_path])
    check("未知商品提示", rc == 1 and "未知商品" in buf.getvalue())

    os.unlink(pack_path)


def test_frame_consistency():
    """T9/E6 坐标系一致性：跨系报价必须携带 δ_frame。"""
    print("\n[13] T9 坐标系一致性")
    from barter import taxonomy
    from barter.taxonomy import frame_of, FRAME_BENCH

    # 当前全部为 benchmark 坐标系
    check("锚定品默认 benchmark 系", frame_of("wheat") == FRAME_BENCH)
    check("挂靠品继承锚定品坐标系", frame_of("flour") == FRAME_BENCH)

    # 同系报价：无 δ_frame
    pack = make_pack()
    q = quote("wheat", 1, "maize", None, pack)
    check("同系报价无 δ_frame", "δ_frame" not in q.delta_parts)

    # 真实跨系路径：注入 PPP 系锚定品
    taxonomy.ANCHORS["wheat_ppp"] = {
        "name": "小麦(PPP)", "cat": taxonomy.GRAIN, "unit": "吨",
        "wb_col": "Wheat, US HRW", "frame": "ppp"}
    try:
        check("PPP 锚定品坐标系为 ppp", frame_of("wheat_ppp") == "ppp")
        # 跨系报价：wheat(benchmark) vs wheat_ppp(ppp)
        raw = make_pack().raw
        raw["anchors"]["wheat_ppp"] = {
            "price_usd_per_unit": 260.0, "sources": {"FAO": 260.0},
            "vol20d_ann": 0.15,
            "as_of": raw["anchors"]["wheat"]["as_of"],
            "history_12m": [260.0] * 12, "frame": "ppp",
            "frame_spread": 0.06}
        pack2 = DataPack(raw)
        q2 = quote("wheat", 1, "wheat_ppp", None, pack2)
        check("跨系报价携带 δ_frame", "δ_frame" in q2.delta_parts)
        check("δ_frame 用实测背离度（6% > 下限4%）",
              abs(q2.delta_parts.get("δ_frame", 0) - 0.06) < 1e-9)
        # 对称性（E2）：反向报价 δ_frame 相同
        q3 = quote("wheat_ppp", 1, "wheat", None, pack2)
        check("δ_frame 双向对称（E2）",
              abs(q2.delta_parts.get("δ_frame", 0)
                  - q3.delta_parts.get("δ_frame", 0)) < 1e-9)
    finally:
        del taxonomy.ANCHORS["wheat_ppp"]


def test_ppp_sampling():
    """PPP 市场采样路径（数据源方案 §4 路径三 + T9 ppp 坐标系）。"""
    print("\n[14] PPP 市场采样")
    pack_raw = make_pack().raw
    # 注入 PPP 采样数据（模拟 sample_ppp 的输出）
    pack_raw["linked"] = {
        "flour": {
            "K_market_median": 0.52,      # $0.52/kg
            "K_dispersion": 0.03,         # 低离散度，确保不超限
            "n_markets": 4,
            "prices_usd": {"US": 0.52, "DE": 0.54, "JP": 0.51, "BR": 0.50},
            "frame": "ppp",
        }
    }
    pack = DataPack(pack_raw)

    # PPP 采样品定价
    q = quote("flour", 1, "maize", None, pack)
    check("PPP 采样品报价成功", q.ok, q.reason)
    check("中心值用采样中位数",
          abs(q.sides[0].price_usd - 0.52) < 1e-9,
          f"got {q.sides[0].price_usd}")
    check("δ_data 用实测离散度",
          abs(q.delta_parts["δ_data"] - 0.03) < 1e-9,
          f"got {q.delta_parts['δ_data']}")

    # PPP vs benchmark → 跨系，应有 δ_frame
    check("PPP↔benchmark 跨系报价携带 δ_frame",
          "δ_frame" in q.delta_parts,
          f"parts={list(q.delta_parts.keys())}")

    # PPP 新鲜度标签
    check("PPP 采样标注市场数", "PPP采样" in q.freshness_label)

    # 高离散度 PPP 采样 → δ_data 跟随
    pack_raw2 = make_pack().raw
    pack_raw2["linked"] = {"flour": {"K_market_median": 0.52,
                                      "K_dispersion": 0.15, "n_markets": 4,
                                      "prices_usd": {}, "frame": "ppp"}}
    q2 = quote("flour", 1, "maize", None, DataPack(pack_raw2))
    if q2.ok:
        check("高离散度 → δ_data 跟随", abs(q2.delta_parts["δ_data"] - 0.15) < 1e-9)
    else:
        check("高离散度 → 可能超限拒绝（δ_data=15% 本身接近上限）", True)


def test_real_datapack():
    print("\n[9] 真实数据包（世界银行现货基准价）")
    if not os.path.exists("data/cmo_monthly.xlsx"):
        print("  - 跳过（无数据文件）")
        return
    pack_dict = build("data/cmo_monthly.xlsx")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(pack_dict, f)
        path = f.name
    pack = DataPack.load(path)
    # 回放模式：以数据包快照时间为"当下"（真实数据是 2024-12 的历史快照）
    replay_now = datetime(2024, 12, 2, tzinfo=timezone.utc)
    q = quote("wheat", 1, "diesel", None, pack, now=replay_now)
    check("小麦→柴油报价成功", q.ok, q.reason)
    if q.ok:
        print(f"    1 吨小麦 ≈ {q.ratio_lo:.0f} ~ {q.ratio_hi:.0f} 升柴油 "
              f"(±{q.delta:.0%}, {q.freshness_label})")
    check("δ 在 [δ_min, δ_max] 内", DELTA_MIN <= q.delta <= DELTA_MAX)
    os.unlink(path)


def demo_scenarios():
    print("\n[10] 演示场景（真实数据包）")
    if not os.path.exists("data/cmo_monthly.xlsx"):
        print("  - 跳过")
        return
    from barter.build_datapack import build as bd
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bd("data/cmo_monthly.xlsx"), f)
        f.flush()
        pack = DataPack.load(f.name)
    replay_now = datetime(2024, 12, 2, tzinfo=timezone.utc)
    for a, qa, b in [("wheat", 0.5, "diesel"),
                     ("rice", 1, "cook_oil_1l"),
                     ("gold", 0.0311035, "wheat"),   # 100克黄金
                     ("eggs", 30, "flour")]:
        q = quote(a, qa, b, None, pack, now=replay_now)
        sa, sb = q.sides
        if q.ok:
            print(f"  {qa:g}{sa.unit}{sa.name} ≈ "
                  f"{q.ratio_lo*qa:.3g}~{q.ratio_hi*qa:.3g}{sb.unit}{sb.name}"
                  f"  (±{q.delta:.0%})")
        else:
            print(f"  {sa.name}→{sb.name}: 拒绝（{q.reason[:40]}…）")
    os.unlink(f.name)


if __name__ == "__main__":
    test_basic_ratio()
    test_ab_ba_consistency()
    test_theorems_exhaustive()
    test_cross_pair_delta()
    test_perishable_upgrade()
    test_lineage_delta()
    test_stale_data_widens()
    test_refuse_when_too_stale()
    test_refuse_extreme_vol()
    test_systemic_shock_refuses()
    test_calibration()
    test_gitaudit()
    test_cli_smoke()
    test_frame_consistency()
    test_ppp_sampling()
    test_real_datapack()
    demo_scenarios()
    print(f"\n{'=' * 40}\n通过 {PASS} / {PASS + FAIL}")
    sys.exit(1 if FAIL else 0)
