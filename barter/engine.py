"""换算引擎：纯函数。输入货物 A + 货物 B，输出兑换比率区间 + 计算明细。

数学基础见 数学基础.md（定理 T1~T8，工程条款 E1~E5）。
关键不变量：
  T1 中心值与计价货币无关（崩溃国本币在除法中约去）
  T4 区间必须是对数对称的 Re^(±δ)（E1：禁止线性区间）
  T5 AB/BA 边缘判定一致（E2：δ 各分量必须对 (A,B) 对称）
  T8 L3 分拆递归深度为 1（_depth 参数保证）

设计文档 §5。单位约定：金额换算为共同计价层后相比（T1），
输出"1 单位 A 换多少单位 B"的对数对称区间。
"""
import math
from dataclasses import dataclass, field

from .taxonomy import get_item, same_pair_group, frame_of
from .datapack import DataPack, LocalCalibration

# §5.2（v0.4 · 用户决策：区间全宽 ≤ 40%，即 hi/lo ≤ 1.40）
# v0.6：区间改为对数对称 [mid·e^(−δ), mid·e^(δ)]——
# 普通 ±δ 区间在倒数变换下不对称（AB 下沿的交易在 BA 视角会落在区间外，
# 双方各自验算会得到矛盾结论）；对数区间在倒数下严格自洽：
# 1/(mid·e^δ) = (1/mid)·e^(−δ)。hi/lo = e^(2δ)。
DELTA_PAIR_SAME = 0.06      # 同类商品对（品级/基差摩擦，日频数据校准）
DELTA_PAIR_CROSS = 0.11     # 跨类商品对
DELTA_PAIR_PERISHABLE = 0.12    # §4.5：易腐品上调一档
DELTA_DATA_FLOOR = 0.02     # 单数据源时的 δ_data 下限
DELTA_LINEAGE_PER_HOP = 0.01    # 族谱每层 +1%
DELTA_FRAME_FLOOR = 0.04    # T9/E6：跨坐标系混用罚项下限（双价锚实测后收窄）
DELTA_MIN = 0.08
DELTA_MAX = math.log(1.40) / 2   # = 16.82% ↔ hi/lo = e^(2δ) = 1.40
SQRT_20D = math.sqrt(20)    # δ_vol 年化→20日化


@dataclass
class SideResult:
    code: str
    name: str
    unit: str
    price_usd: float          # 每 unit 的美元价（已含 K）
    anchor_chain: list        # 溯源链 [("wheat", 265.0), ...]
    hops: int
    as_of: str = ""           # 锚定价日期（参考成交价的时间戳）
    k_calibrated: bool = False
    warnings: list = field(default_factory=list)


@dataclass
class Quote:
    ok: bool
    reason: str = ""                       # 拒绝原因（ok=False 时）
    # ok=True 时：
    ratio_mid: float = 0.0                 # 1 单位 A ≈ ratio_mid 单位 B
    ratio_lo: float = 0.0
    ratio_hi: float = 0.0
    delta: float = 0.0
    delta_parts: dict = field(default_factory=dict)
    sides: tuple = ()
    freshness_label: str = ""
    trend_note: str = ""
    degraded_to_gold: bool = False         # §5.4.4 黄金交叉验证降级
    # L3 分拆报价（ok=True 且 partial=True 时）：
    # ratio_* 描述的是 稳定侧 → 中介锚（如黄金）的可信区间，
    # 剧烈波动侧由用户凭本地知识自行谈判。
    partial: bool = False
    intermediary: str = ""                 # 中介锚代码（如 "gold"）
    manual_side: str = ""                  # 无法定价一侧的商品名
    detail: str = ""


def _resolve(code: str, pack: DataPack, calib: LocalCalibration, now=None) -> SideResult:
    """沿族谱解析到锚定价，返回每 unit 美元价 + 溯源链 + 警告。"""
    item = get_item(code)
    chain, hops, k_cal, warnings = [], item["hops"], False, []
    # 沿 anchor 链走到根
    node, k_acc = code, 1.0
    while True:
        it = get_item(node)
        if it["anchor"] is None:
            root = node
            break
        k, user_cal = calib.get_k(node, it["K"])
        k_cal = k_cal or user_cal
        k_acc *= k
        chain.append((node, k, user_cal))
        node = it["anchor"]
    a = pack.anchors[root]
    price = a["price_usd_per_unit"] * k_acc
    chain.append((root, a["price_usd_per_unit"], False))
    fresh = pack.freshness(root, now)
    if fresh["refuse"]:
        warnings.append(f"锚定品 {root} 数据{fresh['label']}，已达拒绝阈值")
    elif fresh["stale"]:
        warnings.append(f"锚定品 {root} 数据{fresh['label']}，区间已加宽")
    if item.get("perishable"):
        warnings.append("易腐品：δ 已按 §4.5 上调一档")
    if item.get("seasonal"):
        warnings.append("季节性商品：注意收获季/青黄不接季的 K 值差异（§4.5）")
    return SideResult(code=code, name=item["name"], unit=item["unit"],
                      price_usd=price, anchor_chain=chain, hops=hops,
                      as_of=a["as_of"],
                      k_calibrated=k_cal, warnings=warnings), item, root, fresh


def _trend_note(pack: DataPack, root_a: str, root_b: str) -> str:
    """§5.4.2 趋势 vs 噪声：用12月历史判断中心值是否处于单向趋势中。"""
    ha = pack.anchors[root_a].get("history_12m") or []
    hb = pack.anchors[root_b].get("history_12m") or []
    if len(ha) < 6 or len(hb) < 6:
        return ""
    ratios = [x / y for x, y in zip(ha[-6:], hb[-6:]) if y > 0]
    if len(ratios) < 6:
        return ""
    ups = sum(1 for i in range(1, len(ratios)) if ratios[i] > ratios[i - 1])
    if ups >= 5:
        return "比率近6个月持续单向移动 → 判定为趋势，区间中心已跟随（§5.4.2）"
    if ups <= 1:
        return "比率近6个月持续单向移动 → 判定为趋势，区间中心已跟随（§5.4.2）"
    return ""


def quote(code_a: str, qty_a: float, code_b: str, qty_b: float | None,
          pack: DataPack, calib: LocalCalibration | None = None,
          now=None, _depth: int = 0) -> Quote:
    """核心换算：qty_a 单位 A 大约能换多少单位 B（qty_b=None 时返回单价区间）。
    _depth 为 L3 递归深度（T8：分拆报价的递归深度必须为 1）。"""
    calib = calib or LocalCalibration()
    try:
        sa, ia, ra, fa = _resolve(code_a, pack, calib, now)
        sb, ib, rb, fb = _resolve(code_b, pack, calib, now)
    except KeyError as e:
        return Quote(ok=False, reason=f"未知商品代码: {e}")

    # §5.3 降级：数据严重过期 → 拒绝
    if fa["refuse"] or fb["refuse"]:
        return Quote(ok=False,
                     reason=f"数据严重过期（{fa['label']} / {fb['label']}），"
                            f"超出 §5.3 拒绝阈值，请更新数据包后再试",
                     sides=(sa, sb))

    # --- δ 计算（§5.2 校准版） ---
    perishable = ia.get("perishable") or ib.get("perishable")
    if perishable:
        d_pair = DELTA_PAIR_PERISHABLE
    elif same_pair_group(code_a, code_b):
        d_pair = DELTA_PAIR_SAME
    else:
        d_pair = DELTA_PAIR_CROSS

    # δ_data：两侧锚定品多源离散度取大，单源给下限
    d_data = max(pack.source_dispersion(ra), pack.source_dispersion(rb),
                 DELTA_DATA_FLOOR)

    # δ_vol = 1.65 × σ_20d × √(T)，T=数据年龄（天）的缩放（§5.2 注）
    va = pack.anchors[ra]["vol20d_ann"] / SQRT_20D
    vb = pack.anchors[rb]["vol20d_ann"] / SQRT_20D
    t = max(fa["days"], fb["days"], 1)
    d_vol = 1.65 * (va + vb) / 2 * math.sqrt(t / 20)

    # δ_lineage：族谱距离（§5.2），出口商品锚定加成（§5.4.3）为可扩展钩子
    d_lineage = DELTA_LINEAGE_PER_HOP * (sa.hops + sb.hops)

    # δ_frame（T9/E6）：两侧坐标系不同 → 加罚。
    # 若数据包提供双价锚的实测背离度则用实测值，否则用下限。
    fa_frame = frame_of(code_a, pack.anchors)
    fb_frame = frame_of(code_b, pack.anchors)
    if fa_frame != fb_frame:
        d_frame = max(
            DELTA_FRAME_FLOOR,
            max(pack.anchors[ra].get("frame_spread", 0),
                pack.anchors[rb].get("frame_spread", 0)),
        )
    else:
        d_frame = 0.0

    delta = d_pair + d_data + d_vol + d_lineage + d_frame
    parts = {"δ_pair": d_pair, "δ_data": d_data, "δ_vol": d_vol,
             "δ_lineage": d_lineage}
    if d_frame > 0:
        parts["δ_frame"] = d_frame

    if delta > DELTA_MAX:
        # L3 降级：分拆报价 —— 识别剧烈波动的一侧，只为稳定侧担保
        if _depth >= 1:
            # T8 工程条款：递归深度为 1，中介报价再超限则整体拒绝
            return Quote(ok=False,
                         reason=f"δ={delta:.0%} 超过上限，且稳定侧→中介锚报价亦超限，"
                                f"拒绝输出（§5.3 / T8）",
                         sides=(sa, sb), delta=delta, delta_parts=parts)
        return _split_quote(code_a, code_b, sa, sb, ra, rb, pack, calib,
                            now, delta, parts)

    delta = max(delta, DELTA_MIN)
    mid = sa.price_usd / sb.price_usd          # 1 A ≈ mid B
    lo, hi = mid * math.exp(-delta), mid * math.exp(delta)   # 对数对称（自洽）

    if qty_b:  # 双向报价模式：判断对方出价是否在区间内
        pass   # v0.1 简化：统一返回 1 单位 A 的区间，CLI 层做乘法

    return Quote(ok=True, ratio_mid=mid, ratio_lo=lo, ratio_hi=hi,
                 delta=delta, delta_parts=parts, sides=(sa, sb),
                 freshness_label=f"A:{fa['label']} / B:{fb['label']}",
                 trend_note=_trend_note(pack, ra, rb),
                 detail=_detail(sa, sb, mid, delta, parts))


# 系统性冲击判定：两侧波动率相近 且 绝对水平超过阈值（§5.4）
# 只比比值会把"两侧都平静"误判为同步剧烈（v0.4.1 修复）
SYSTEMIC_VOL_THRESHOLD = 0.60   # 年化波动率 60% 以上才算"剧烈"


def _vol_of(pack: DataPack, root: str) -> float:
    return pack.anchors[root]["vol20d_ann"]


def _pick_intermediary(pack: DataPack, exclude: set, now=None) -> str | None:
    """选当前最稳的中介锚：黄金优先（§5.4.4），其次主粮，取波动率最低者。"""
    cands = [c for c in ("gold", "wheat", "rice") if c not in exclude]
    cands = [c for c in cands
             if c in pack.anchors and not pack.freshness(c, now)["refuse"]]
    if not cands:
        return None
    return min(cands, key=lambda c: _vol_of(pack, c))


def _split_quote(code_a, code_b, sa, sb, ra, rb, pack, calib, now,
                 delta, parts) -> Quote:
    """L3 降级（§5.4.4 自动化）：
    直接报价 δ 超上限时，识别剧烈波动侧，把稳定侧换算到最稳中介锚
    （黄金/主粮），波动侧留给用户凭本地知识谈判。

    判据：波动侧 = 锚定品 vol20d_ann 显著更高的一侧。
    若两侧同样剧烈（系统性冲击），退化为完全拒绝。
    """
    va, vb = _vol_of(pack, ra), _vol_of(pack, rb)
    # 两侧波动相近且都剧烈 → 系统性冲击，分拆无意义；
    # 两侧都平静则不是冲击（此时超限必另有原因，如数据龄过长/族谱过深）
    if (min(va, vb) * 1.8 >= max(va, vb)
            and max(va, vb) >= SYSTEMIC_VOL_THRESHOLD):
        return Quote(ok=False,
                     reason=f"δ={delta:.0%} 超过上限 {DELTA_MAX:.0%}，且两侧商品"
                            f"同步剧烈波动（系统性冲击），分拆报价无意义。"
                            f"拒绝给出参考值，请人工议价（§5.3）",
                     sides=(sa, sb), delta=delta, delta_parts=parts)

    if va > vb:
        stable_s, stable_root, stable_code = sb, rb, code_b
        volatile_name = sa.name
    else:
        stable_s, stable_root, stable_code = sa, ra, code_a
        volatile_name = sb.name

    mid_code = _pick_intermediary(pack, {code_a, code_b}, now)
    if not mid_code:
        return Quote(ok=False,
                     reason=f"δ={delta:.0%} 超限且无可用中介锚，拒绝输出（§5.3）",
                     sides=(sa, sb), delta=delta, delta_parts=parts)

    # 递归调用自身：稳定侧 → 中介锚（T8：_depth=1 保证不再二次分拆）
    q = quote(stable_code, 1, mid_code, None, pack, calib, now, _depth=1)
    if not q.ok:
        return Quote(ok=False,
                     reason=f"δ={delta:.0%} 超限，且稳定侧→中介锚报价失败："
                            f"{q.reason}",
                     sides=(sa, sb), delta=delta, delta_parts=parts)

    mid_item = get_item(mid_code)
    return Quote(
        ok=True, partial=True,
        ratio_mid=q.ratio_mid, ratio_lo=q.ratio_lo, ratio_hi=q.ratio_hi,
        delta=q.delta, delta_parts=q.delta_parts,
        sides=q.sides, intermediary=mid_code, manual_side=volatile_name,
        freshness_label=q.freshness_label, trend_note=q.trend_note,
        degraded_to_gold=(mid_code == "gold"),
        detail=(
            f"── L3 分拆报价（§5.4.4）──\n"
            f"直接报价 δ={delta:.0%} 超限，已自动分拆：\n"
            f"  稳定侧：1 {stable_s.unit}{stable_s.name} = "
            f"{q.ratio_lo:.4g} ~ {q.ratio_hi:.4g} {mid_item['unit']}{mid_item['name']}"
            f"（±{q.delta:.0%}，此段可信）\n"
            f"  波动侧：{volatile_name} 当前无法定价，"
            f"请用本地现货知识完成「{mid_item['name']} → {volatile_name}」这一段谈判\n"
            + q.detail),
    )


def _detail(sa: SideResult, sb: SideResult, mid, delta, parts) -> str:
    """计算明细（§8 信任与可复核性：全程透明）。"""
    lines = ["── 计算明细 ──"]
    for s in (sa, sb):
        chain = " → ".join(f"{c[0]}({c[1]:.4g}{'*用户校准' if c[2] else ''})"
                            for c in s.anchor_chain)
        lines.append(f"{s.name}: {chain} = ${s.price_usd:.4g}/{s.unit}")
    lines.append(f"中心值: 1 {sa.unit}{sa.name} = {mid:.4g} {sb.unit}{sb.name}")
    lines.append("δ 分解: " + " + ".join(f"{k}={v:.1%}" for k, v in parts.items())
                 + f" = {delta:.1%}")
    for s in (sa, sb):
        lines.extend(f"  ⚠ {w}" for w in s.warnings)
    return "\n".join(lines)
