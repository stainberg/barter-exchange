# 易货换算工具 MVP · v0.1

纯 Python 标准库实现（换算引擎零依赖），CLI 交互，真实数据锚定。

## 结构

```
barter/
├── taxonomy.py        商品族谱：11 锚定品 + 10 挂靠品，K 系数，品类，易腐/季节标签
├── datapack.py        数据包：加载/校验/新鲜度判定/多源离散度 + 本地 K 校准持久化
├── engine.py          换算引擎（纯函数）：中心值 + δ 区间 + 降级规则 + 趋势判定
├── build_datapack.py  从世界银行粉单构建真实数据包（含波动率、12月历史）
├── cli.py             中文 CLI：换算 / 出价判断 / K 校准 / 计算明细 / 回放模式
└── tests.py           19 项单元测试 + 演示场景
data/
├── cmo_monthly.xlsx   世界银行粉单原始数据（2000–2024，现货基准价）
└── datapack_latest.json  生成的数据包
```

## 使用

```bash
# 换算：500 吨小麦 ≈ 多少升柴油
.venv/bin/python -m barter.cli 小麦 500 柴油

# 判断对方出价是否公道
.venv/bin/python -m barter.cli 鸡蛋 30 面粉 --qty-b 100

# 查看计算明细（信任与可复核性）
.venv/bin/python -m barter.cli 小麦 500 柴油 --detail

# 列出全部商品
.venv/bin/python -m barter.cli --list

# 本地校准 K 值（只存本地设备）
.venv/bin/python -m barter.cli --calibrate coffee 5.1

# 历史回放（用历史数据包演示）
.venv/bin/python -m barter.cli 小麦 500 柴油 --now 2024-12-15

# 交互模式
.venv/bin/python -m barter.cli
```

## 设计文档机制落位对照

| 机制 | 位置 | 状态 |
|---|---|---|
| §5.1 中心值 R | `engine.quote` | ✅ |
| §5.2 δ_pair 同类/跨类/易腐分档（6%/11%/12%） | `engine` | ✅ 日频校准 |
| §5.2 δ_data 多源离散度 | `datapack.source_dispersion` | ✅ 单源时下限 2% |
| §5.2 δ_vol = 1.65σ√T | `engine` | ✅ |
| §5.2 δ_lineage 族谱每层 +1% | `engine` | ✅ |
| §5.2 δ_min/δ_max 钳位（全宽≤40% 硬约束） | `engine` | ✅ 8%/16.67% |
| §5.3 五级降级链（L0~L4） | `engine` + `datapack.freshness` | ✅ |
| §5.4.2 趋势 vs 噪声判定 | `engine._trend_note` | ✅ 简化版 |
| §5.4.4 L3 自动分拆报价（波动侧识别+中介锚选择） | `engine._split_quote` | ✅ |
| §4.3 本地 K 校准 | `datapack.LocalCalibration` | ✅ 持久化 |
| §4.5 易腐品 δ 上调 / 季节性标签 | `taxonomy` + `engine` | ✅ |
| 数据包签名 | — | ❌ v0.2 |
| 期货曲线形态信号（§4.1） | — | ❌ 需日期频源 |
| 隐含波动率前瞻触发器（§5.4.1） | — | ❌ 需期权数据源 |
| 出口商品锚定加成（§5.4.3） | — | ❌ 需国别配置 |

## 测试

```bash
.venv/bin/python -m barter.tests    # 19 项断言
```

## 已知局限（v0.1）

1. 数据为**月度**现货基准价（世界银行粉单），新鲜度天然 ~14 天。**收紧 δ_max=16.67% 后日频数据成为硬前提**——月度数据下 δ_vol 一项就会吃掉大半预算，系统几乎必然沉默。接日频源是 v0.2 第一优先级。
2. 单数据源，δ_data 只能给下限。
3. 挂靠品 K 值为初值，未实地校准——`--calibrate` 就是为此准备的。
4. 无 UI，无离线打包，无蓝牙/二维码数据包互传（§7 路线图 v0.2+）。
