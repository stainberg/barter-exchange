"""商品族谱：锚定品 + 挂靠品（K 系数）、品类、可储存性。

设计文档 §4。单位体系：
  每个商品声明一个"交易单位"（unit），锚定价为每 unit 的美元现货基准价。
  K = 该商品 1 unit 相当于 anchor 商品 K 个 anchor-unit 的价值系数。
  族谱距离（hops）= 到锚定品的层数，用于 δ_lineage。
"""

# 品类
GRAIN = "谷物"
OILSEED = "油脂油料"
ENERGY = "能源"
PMETAL = "贵金属"
IMETAL = "工业金属"
FERT = "化肥"
SOFT = "软商品"
PROTEIN = "蛋白质"

# 测量坐标系（T9/E6）：每个商品的价格必须声明其来源坐标系
FRAME_BENCH = "benchmark"   # 枢纽现货基准价（FRED/gold-api/WB）
FRAME_PPP = "ppp"           # 多地平价采样价（FAO FPMA 等，v0.3 接入）

# 锚定品：价格直接来自数据包（世界银行现货基准价 / 近月期货收敛价）
# unit: 交易单位; wb_col: 世界银行粉单列名; perishable/seasonal 见 §4.5
ANCHORS = {
    "wheat":  {"name": "小麦",   "cat": GRAIN,  "unit": "t",   "wb_col": "Wheat, US HRW"},
    "rice":   {"name": "大米",   "cat": GRAIN,  "unit": "t",   "wb_col": "Rice, Thai 5% ", "seasonal": True},
    "maize":  {"name": "玉米",   "cat": GRAIN,  "unit": "t",   "wb_col": "Maize", "seasonal": True},
    "soyoil": {"name": "豆油",   "cat": OILSEED,"unit": "t",   "wb_col": "Soybean oil"},
    "sugar":  {"name": "白糖",   "cat": SOFT,   "unit": "kg", "wb_col": "Sugar, world"},
    "crude":  {"name": "原油",   "cat": ENERGY, "unit": "bbl",   "wb_col": "Crude oil, average"},
    "gold":   {"name": "黄金",   "cat": PMETAL, "unit": "oz", "wb_col": "Gold"},
    "silver": {"name": "白银",   "cat": PMETAL, "unit": "oz", "wb_col": "Silver"},
    "copper": {"name": "铜",     "cat": IMETAL, "unit": "t",   "wb_col": "Copper"},
    "aluminum":{"name": "铝",    "cat": IMETAL, "unit": "t",   "wb_col": "Aluminum"},
    "urea":   {"name": "尿素",   "cat": FERT,   "unit": "t",   "wb_col": "Urea "},
}

# 挂靠品：price = anchor_price × K（K 可本地校准，见 §4.3）
# hops = 族谱层数（锚定品为 0）
LINKED = {
    # 谷物加工链
    "flour":   {"name": "面粉",     "cat": GRAIN,   "unit": "kg", "anchor": "wheat",  "K": 1.35e-3, "hops": 1,
                "note": "出粉率+加工费"},
    "noodles": {"name": "面条",     "cat": GRAIN,   "unit": "kg", "anchor": "flour",  "K": 1.8,     "hops": 2},
    "bread":   {"name": "面包",     "cat": GRAIN,   "unit": "kg", "anchor": "flour",  "K": 2.6,     "hops": 2,
                "perishable": True},
    # 油脂链
    "palm_oil":   {"name": "棕榈油", "cat": OILSEED, "unit": "t", "anchor": "soyoil", "K": 0.92, "hops": 1},
    "cook_oil_1l": {"name": "食用油(1L装)", "cat": OILSEED, "unit": "l",
                  "anchor": "soyoil", "K": 1.15e-3, "hops": 2, "note": "分装零售系数"},
    # 能源链
    "diesel":  {"name": "柴油",     "cat": ENERGY,  "unit": "l",   "anchor": "crude",  "K": 7.2e-3, "hops": 1,
                "note": "1桶≈159L, 炼化加成"},
    "gasoline":{"name": "汽油",     "cat": ENERGY,  "unit": "l",   "anchor": "crude",  "K": 8.0e-3, "hops": 1},
    "kerosene":{"name": "煤油",     "cat": ENERGY,  "unit": "l",   "anchor": "crude",  "K": 7.6e-3, "hops": 1},
    # 化肥
    "dap":     {"name": "磷酸二铵", "cat": FERT,    "unit": "t",   "anchor": "urea",   "K": 1.55,   "hops": 1},
    # 蛋白质（高时变，§4.5 上调 δ）
    "eggs":    {"name": "鸡蛋",     "cat": PROTEIN, "unit": "kg", "anchor": "maize",  "K": 6.5e-3, "hops": 1,
                "perishable": True, "note": "饲料粮转化"},
    "chicken": {"name": "鸡肉",     "cat": PROTEIN, "unit": "kg", "anchor": "maize",  "K": 9.0e-3, "hops": 1,
                "perishable": True},
    # 软商品
    "coffee":  {"name": "咖啡豆",   "cat": SOFT,    "unit": "kg", "anchor": "sugar",  "K": 4.2,    "hops": 1,
                "note": "跨品种弱锚定, K 强烈建议本地校准"},
}

# 同类商品对判定（§5.2 δ_pair 分档）
SAME_PAIR_GROUPS = [
    {"wheat", "rice", "maize", "flour", "noodles", "bread"},            # 谷物内
    {"soyoil", "palm_oil", "cook_oil_1l"},                              # 油脂内
    {"crude", "diesel", "gasoline", "kerosene"},                        # 能源内
    {"gold", "silver"},                                                 # 贵金属内
    {"copper", "aluminum"},                                             # 工业金属内
    {"urea", "dap"},                                                    # 化肥内
]


def get_item(code):
    if code in ANCHORS:
        return {**ANCHORS[code], "anchor": None, "K": 1.0, "hops": 0,
                "frame": ANCHORS[code].get("frame", FRAME_BENCH)}
    return LINKED[code]


def frame_of(code: str, pack: dict | None = None) -> str:
    """商品的价格坐标系（T9/E6）。
    规则：
    1. 数据包 linked 段含该商品的 PPP 采样 → ppp
    2. 锚定品读自身声明的 frame
    3. 挂靠品沿族谱继承锚定品的坐标系
    """
    if pack is not None:
        linked = pack.get("linked", {})
        if code in linked and linked[code].get("frame") == "ppp":
            return FRAME_PPP
    node = code
    while node not in ANCHORS:
        node = LINKED[node]["anchor"]
    return ANCHORS[node].get("frame", FRAME_BENCH)


def all_codes():
    return list(ANCHORS) + list(LINKED)


def same_pair_group(a, b):
    for g in SAME_PAIR_GROUPS:
        if a in g and b in g:
            return True
    return False
