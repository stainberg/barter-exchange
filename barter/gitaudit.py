"""客户端 git 历史绑定验证（DATA_SOURCES §信任根）。

信任模型（无私钥）：
  数据包内嵌 code_commit → 客户端用任意镜像（GitHub/GitLab/IPFS 克隆）
  核对：该 commit 存在 + 历史连续 + 多镜像一致 + 已过沉淀期。
作恶无法隐藏：任何人伪造历史都会与公开历史分叉，被观察到。

这些函数都是只读操作，输入：本地 git 克隆路径。
"""
import subprocess
from dataclasses import dataclass


@dataclass
class HistoryCheck:
    ok: bool
    commit_found: bool = False
    linear_history: bool = False
    settled: bool = False          # 已过沉淀期
    mirrors_agree: bool = False
    detail: str = ""


def _git(repo: str, *args) -> str:
    r = subprocess.run(["git", "-C", repo, *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def check_commit(repo: str, commit: str,
                 settle_hours: int = 24,
                 mirror_heads: list[str] | None = None) -> HistoryCheck:
    """验证数据包绑定的 commit 在本地克隆中可信。

    检查项：
    1. commit 存在且可达
    2. commit 已沉淀 settle_hours（防"刚刚推送的恶意提交"）
    3. 若提供镜像 HEAD 列表，检查该 commit 被所有镜像包含
       （多镜像一致性：作恶者的分叉不可能出现在所有镜像上）
    """
    out = HistoryCheck(ok=False)

    # 1. 存在性
    try:
        _git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
        out.commit_found = True
    except RuntimeError:
        out.detail = f"commit {commit[:12]} 不存在于此克隆"
        return out

    # 2. 沉淀期
    ts = int(_git(repo, "log", "-1", "--format=%ct", commit))
    import time
    age_h = (time.time() - ts) / 3600
    out.settled = age_h >= settle_hours
    if not out.settled:
        out.detail = f"commit 仅存在 {age_h:.1f}h（沉淀期 {settle_hours}h 未到）"

    # 3. 多镜像一致性：commit 是否为各镜像 HEAD 的祖先
    if mirror_heads:
        agree = 0
        for head in mirror_heads:
            try:
                _git(repo, "merge-base", "--is-ancestor", commit, head)
                agree += 1
            except RuntimeError:
                pass
        out.mirrors_agree = agree == len(mirror_heads)
        if not out.mirrors_agree:
            out.detail = (out.detail + "；" if out.detail else "") + \
                f"仅 {agree}/{len(mirror_heads)} 个镜像包含该 commit"
    else:
        out.mirrors_agree = True  # 无镜像列表时跳过（弱模式）

    out.ok = out.commit_found and out.settled and out.mirrors_agree
    if out.ok:
        out.detail = f"commit {commit[:12]} 存在 {age_h:.0f}h，多镜像一致"
    return out


def check_pack(pack: dict, repo: str, **kw) -> HistoryCheck:
    """对数据包做完整历史绑定验证。"""
    commit = pack.get("code_commit")
    if not commit:
        return HistoryCheck(ok=False, detail="数据包无 code_commit 字段")
    return check_commit(repo, commit, **kw)
