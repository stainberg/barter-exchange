#!/usr/bin/env python3
"""数据包签名（设计文档 §8：防传输篡改）。

算法：Ed25519。私钥存 GitHub Secrets（PACK_SIGNING_KEY，hex），
公钥内嵌客户端（barter/datapack.py 的 PACK_PUBLIC_KEY）。

签名内容：canonical JSON（键排序、无空白）的 SHA-256 摘要。
签名写入 dist/datapack-*.sig.json：
  {"sig": hex, "pubkey": hex, "payload_sha256": hex}
"""
import glob
import hashlib
import json
import os
import sys


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def main():
    try:
        from nacl.signing import SigningKey
    except ImportError:
        os.system(f"{sys.executable} -m pip install --quiet pynacl")
        from nacl.signing import SigningKey

    key_hex = os.environ.get("PACK_SIGNING_KEY")
    if not key_hex:
        # 无 key 环境（本地开发）：生成临时密钥并明确标注
        sk = SigningKey.generate()
        print("⚠ 无 PACK_SIGNING_KEY，使用临时密钥（仅本地测试）")
    else:
        sk = SigningKey(bytes.fromhex(key_hex))

    packs = sorted(glob.glob("dist/datapack-*.json"))
    if not packs:
        raise SystemExit("dist/ 下无数据包，先跑 build_pack.py")

    for path in packs:
        payload = open(path, "rb").read()
        digest = hashlib.sha256(canonical(json.loads(payload))).digest()
        sig = sk.sign(digest).signature.hex()
        sig_path = path.replace(".json", ".sig.json")
        with open(sig_path, "w") as f:
            json.dump({"sig": sig,
                       "pubkey": sk.verify_key.encode().hex(),
                       "payload_sha256": digest.hex()}, f, indent=1)
        print(f"签名: {sig_path}")


if __name__ == "__main__":
    main()
