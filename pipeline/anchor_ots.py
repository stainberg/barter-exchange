#!/usr/bin/env python3
"""OpenTimestamps 锚定：把每日数据包哈希锚定到比特币链上。

角色：保险丝，不是承重墙（DATA_SOURCES §信任根）。
- 主信任链是 git 公开历史 + 多镜像一致性；
- OTS 提供"连 GitHub 都无法改写的存在性证明"——零成本、零维护、
  不进日常验证关键路径，只在"历史是否被重写"的争议中作为公开证据。

用法：
  python pipeline/anchor_ots.py            # 锚定今天的包
  python pipeline/anchor_ots.py --upgrade  # 尝试升级未确认的 .ots（确认需数小时）
需要：pip install opentimestamps（OTS 日历服务器聚合上链，发布者零费用）。
"""
import glob
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def find_packs() -> list[str]:
    return sorted(p for p in glob.glob("dist/datapack-*.json")
                  if not p.endswith(".sig.json"))


def stamp(path: str) -> bool:
    """对文件做 OTS 锚定（生成 <file>.ots）。"""
    if os.path.exists(path + ".ots"):
        print(f"已存在锚定: {path}.ots")
        return True
    r = subprocess.run(["ots", "stamp", path], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"✓ 已锚定: {path}.ots")
        return True
    print(f"✗ 锚定失败: {path}: {r.stderr.strip()}")
    return False


def upgrade_pending() -> int:
    """升级所有未确认的 .ots（OTS 需要等比特币出块，通常几小时）。
    返回仍待确认的数量。每日任务调用一次即可收敛。"""
    pending = 0
    for ots_file in glob.glob("dist/*.ots"):
        r = subprocess.run(["ots", "upgrade", ots_file],
                           capture_output=True, text=True)
        if "Success" in r.stdout:
            print(f"✓ 已确认上链: {ots_file}")
        else:
            pending += 1
    return pending


if __name__ == "__main__":
    if "--upgrade" in sys.argv:
        n = upgrade_pending()
        print(f"待确认: {n}")
        sys.exit(0)
    packs = find_packs()
    if not packs:
        sys.exit("dist/ 下无数据包")
    ok = sum(stamp(p) for p in packs)
    print(f"{ok}/{len(packs)} 已提交锚定（上链确认需数小时，用 --upgrade 收敛）")
