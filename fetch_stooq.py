#!/usr/bin/env python3
"""Solve stooq.com PoW challenge and download CSV data."""
import hashlib, re, sys, time
import urllib.request, urllib.parse, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
opener.addheaders = [("User-Agent", UA)]

def get(url):
    return opener.open(url, timeout=30).read()

def solve_pow(html: bytes):
    m = re.search(rb'const c="([^"]+)",d=(\d+)', html)
    if not m:
        return False
    c, d = m.group(1).decode(), int(m.group(2))
    target = "0" * d
    n = 0
    while True:
        h = hashlib.sha256((c + str(n)).encode()).hexdigest()
        if h.startswith(target):
            break
        n += 1
    body = urllib.parse.urlencode({"c": c, "n": n}).encode()
    req = urllib.request.Request("https://stooq.com/__verify", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    resp = opener.open(req, timeout=30)
    return resp.status == 200

def download(symbol, path, retries=3):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    for attempt in range(retries):
        data = get(url)
        if data.startswith(b"Date,") or b"<html" not in data[:200].lower():
            with open(path, "wb") as f:
                f.write(data)
            return True
        print(f"  [{symbol}] PoW challenge, solving...", flush=True)
        if not solve_pow(data):
            time.sleep(2)
    # final try
    data = get(url)
    if data.startswith(b"Date,"):
        with open(path, "wb") as f:
            f.write(data)
        return True
    return False

if __name__ == "__main__":
    symbols = sys.argv[1:]
    ok, fail = [], []
    for s in symbols:
        p = f"data/{s.replace('.', '_')}.csv"
        if download(s, p):
            lines = open(p).read().strip().split("\n")
            print(f"OK  {s}: {len(lines)-1} rows, {lines[1][:10]} .. {lines[-1][:10]}")
            ok.append(s)
        else:
            print(f"FAIL {s}")
            fail.append(s)
        time.sleep(1)
    print(f"\n{len(ok)} ok, {len(fail)} fail: {fail}")
