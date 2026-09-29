"""单位换算：用户输入/输出单位 → 族谱规范单位。

原则：只使用国际通用单位（SI + 期货市场惯例）：
  mass   → kg（基准）, g, t (metric ton), lb, oz (troy ounce, 贵金属期货惯例)
  volume → l (liter), ml, gal (US), bbl (oil barrel, 能源期货惯例)

引擎内部永远用族谱规范单位（taxonomy.unit），换算只在 CLI 边界做。
跨量纲换算拒绝（不能把 kg 换成 l）。
"""

# 单位 → (量纲, 换算到该量纲基准单位的系数)
UNITS = {
    # 质量（基准：kg）
    "kg": ("mass", 1.0),
    "g": ("mass", 0.001),
    "t": ("mass", 1000.0), "tonne": ("mass", 1000.0),
    "lb": ("mass", 0.4536),
    "oz": ("mass", 0.0311035), "toz": ("mass", 0.0311035),  # troy ounce
    # 体积（基准：l）
    "l": ("volume", 1.0), "liter": ("volume", 1.0),
    "ml": ("volume", 0.001),
    "gal": ("volume", 3.7854),
    "bbl": ("volume", 158.987),
}


def _factors(unit_a: str, unit_b: str):
    if unit_a not in UNITS:
        raise ValueError(f"未知单位: {unit_a}")
    if unit_b not in UNITS:
        raise ValueError(f"未知单位: {unit_b}")
    dim_a, fa = UNITS[unit_a]
    dim_b, fb = UNITS[unit_b]
    if dim_a != dim_b:
        raise ValueError(f"量纲不符: {unit_a}({dim_a}) vs {unit_b}({dim_b})")
    return fa, fb


def to_canonical(qty: float, unit: str, canonical_unit: str) -> float:
    """任意单位 → 族谱规范单位。量纲不符抛 ValueError。"""
    if unit == canonical_unit:
        return qty
    fa, fb = _factors(unit, canonical_unit)
    return qty * fa / fb


def from_canonical(qty: float, canonical_unit: str, unit: str) -> float:
    """族谱规范单位 → 任意显示单位。"""
    if unit == canonical_unit:
        return qty
    fa, fb = _factors(unit, canonical_unit)
    return qty * fb / fa
