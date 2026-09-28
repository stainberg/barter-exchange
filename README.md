# 易货换算工具（Barter Exchange Reference）

为法币崩溃/高通胀地区的交易者提供**以物换物的价值换算参考**：
输入双方的货物，输出一个**参考成交价**（昨日公道价）和一个**议价区间**
（全宽 ≤ 40% 的硬约束）。不碰货、不碰钱、不撮合——只是一把中立的换算尺。

## 快速开始

```bash
python -m venv .venv && .venv/bin/pip install pandas numpy matplotlib openpyxl pynacl

# 拉取每日数据包（GitHub Releases）
curl -L -o data/datapack_latest.json \
  https://github.com/<org>/barter-exchange/releases/download/latest/datapack-latest.json

# 换算：1 吨小麦 ≈ 多少升柴油
.venv/bin/python -m barter.cli 小麦 1 柴油

# 判断对方出价是否公道
.venv/bin/python -m barter.cli 鸡蛋 30 面粉 --qty-b 100
```

## 文档地图

| 文档 | 内容 |
|---|---|
| [易货换算工具-设计文档.md](易货换算工具-设计文档.md) | 产品定位、架构、族谱、区间算法、降级链 |
| [数学基础.md](数学基础.md) | 核心不变量的形式化证明（T1~T8 + 工程条款 E1~E5） |
| [回测报告.md](回测报告.md) | 四国法币崩溃 + 2020 油崩 + 2025 以伊冲突的参数标定 |
| [数据源方案.md](数据源方案.md) | 数据源实测、分层策略、GitHub Actions 生产线 |
| [MVP-README.md](MVP-README.md) | MVP 结构与设计机制落位对照表 |

## 仓库结构

```
barter/       换算引擎（纯函数、零依赖标准库）+ 族谱 + 数据包 + CLI + 测试
pipeline/     每日数据包生产线（采集 → 打包 → 签名 → 验签）
.github/      Actions 工作流：每日 UTC 06:00 自动构建发布数据包
backtest*.py  回测脚本（可复现）
```

## 三条铁律

1. **数学结构可证明**（数学基础.md），回测只标定参数；
2. **区间全宽 ≤ 40%**——给不出窄区间就降级或沉默，绝不用宽区间假装精确；
3. **数据包签名验签**——任何渠道传来的数据包都必须验签后才加载。
