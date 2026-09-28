"""数据包：加载、校验、新鲜度、本地 K 校准。

设计文档 §6。数据包 = 服务器每日打包下发的只读 JSON：
  {
    "generated": "2024-12-31T00:00:00Z",
    "anchors": {
      "wheat": {
        "price_usd_per_unit": 265.0,     # 现货基准价（§4.1：现货>近月，禁远月）
        "sources": {"WB-CMO": 265.0},    # 多源报价，δ_data 的依据
        "vol20d_ann": 0.22,              # 20日年化波动率（分数制）
        "history_12m": [..12 floats..],  # 近12月价格（趋势判定用，§5.4.2）
        "as_of": "2024-12-01"
      }, ...
    }
  }
本地校准文件（用户侧）：{"K_overrides": {"coffee": 5.1}, "created": ...}
"""
import json
import math
from datetime import datetime, timezone

STALE_WARN_DAYS = 3       # §5.3：日频源超过即加宽并显著标注
STALE_REFUSE_DAYS = 45    # 日频源硬上限
# v0.2.1：月频源的发布滞后是结构性的（世界银行发布滞后约 2 个月），
# 其 as_of 是"观测期"而非"可得期"，新鲜度阈值按频率分别定义（T7 不受影响）。
MONTHLY_WARN_DAYS = 45
MONTHLY_REFUSE_DAYS = 100


class DataPack:
    def __init__(self, raw: dict):
        self.raw = raw
        self.generated = datetime.fromisoformat(raw["generated"].replace("Z", "+00:00"))
        self.anchors = raw["anchors"]
        self._validate()

    def _validate(self):
        for code, a in self.anchors.items():
            for k in ("price_usd_per_unit", "vol20d_ann", "as_of", "sources"):
                if k not in a:
                    raise ValueError(f"数据包锚定品 {code} 缺字段 {k}")
            if a["price_usd_per_unit"] <= 0:
                raise ValueError(f"数据包锚定品 {code} 价格非法")

    @classmethod
    def load(cls, path: str) -> "DataPack":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def age_days(self, code: str, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        as_of = datetime.fromisoformat(self.anchors[code]["as_of"])
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        return max(0, (now - as_of).days)

    def freshness(self, code: str, now: datetime | None = None) -> dict:
        d = self.age_days(code, now)
        freq = self.anchors[code].get("freq", "daily")
        if freq == "monthly":
            warn, refuse = MONTHLY_WARN_DAYS, MONTHLY_REFUSE_DAYS
        else:
            warn, refuse = STALE_WARN_DAYS, STALE_REFUSE_DAYS
        return {
            "days": d,
            "stale": d > warn,
            "refuse": d > refuse,
            "label": ("新鲜" if d <= warn else
                      f"过期 {d} 天" if d <= refuse else
                      f"严重过期 {d} 天"),
        }

    def source_dispersion(self, code: str) -> float:
        """多源报价离散度（变异系数），单源时返回 0（δ_data 给下限）。"""
        vals = list(self.anchors[code]["sources"].values())
        if len(vals) < 2:
            return 0.0
        m = sum(vals) / len(vals)
        if m <= 0:
            return 0.0
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        return math.sqrt(var) / m


class LocalCalibration:
    """用户本地 K 值校准（§4.3：只存本地设备）。"""

    def __init__(self, path: str | None = None):
        self.path = path
        self.k_overrides: dict[str, float] = {}
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    self.k_overrides = json.load(f).get("K_overrides", {})
            except FileNotFoundError:
                pass

    def get_k(self, code: str, default: float) -> tuple[float, bool]:
        if code in self.k_overrides:
            return self.k_overrides[code], True
        return default, False

    def set_k(self, code: str, k: float):
        self.k_overrides[code] = k
        if self.path:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"K_overrides": self.k_overrides,
                           "created": datetime.now(timezone.utc).isoformat()},
                          f, ensure_ascii=False, indent=2)
