#!/usr/bin/env python3
"""数据包验签（§8：客户端加载前必须验签）。"""
import glob
import hashlib
import json
import os
import sys


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def verify(pack_path: str, sig_path: str) -> bool:
    from nacl.signing import VerifyKey
    payload = json.load(open(pack_path, "rb"))
    sig_meta = json.load(open(sig_path))
    digest = hashlib.sha256(canonical(payload)).digest()
    if digest.hex() != sig_meta["payload_sha256"]:
        return False
    vk = VerifyKey(bytes.fromhex(sig_meta["pubkey"]))
    try:
        vk.verify(digest, bytes.fromhex(sig_meta["sig"]))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    try:
        import nacl  # noqa
    except ImportError:
        os.system(f"{sys.executable} -m pip install --quiet pynacl")
    packs = sorted(p for p in glob.glob("dist/datapack-*.json")
                   if not p.endswith(".sig.json"))
    ok = 0
    for p in packs:
        sig = p.replace(".json", ".sig.json")
        r = os.path.exists(sig) and verify(p, sig)
        print(f"{'✓' if r else '✗'} {p}")
        ok += r
    print(f"{ok}/{len(packs)} 验签通过")
    sys.exit(0 if ok == len(packs) else 1)
