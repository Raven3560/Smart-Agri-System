"""
Download a small, class-balanced sample of the PlantVillage dataset
(Hughes & Salathe, 2015 - reference [2] in the synopsis) for testing and
evaluating the disease model.

Images come from the public GitHub mirror of the dataset:
https://github.com/spMohanty/PlantVillage-Dataset (raw/color)

Usage:
    python ml/fetch_sample.py --per-class 10 --out data/plantvillage_sample
"""
import argparse
import json
import os
import random
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.github.com/repos/spMohanty/PlantVillage-Dataset/contents/raw/color"
RAW = "https://raw.githubusercontent.com/spMohanty/PlantVillage-Dataset/master/raw/color"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "smart-agri-assistant"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def download(args):
    url, dest = args
    if os.path.exists(dest):
        return dest, True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smart-agri-assistant"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
        return dest, True
    except Exception as exc:  # noqa: BLE001
        print("  failed:", url, exc, file=sys.stderr)
        return dest, False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-class", type=int, default=10, help="images to download per class")
    ap.add_argument("--out", default="data/plantvillage_sample", help="output folder (ImageFolder layout)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    classes = [d["name"] for d in get_json(API) if d["type"] == "dir"]
    print(f"Found {len(classes)} classes")
    jobs = []
    for cls in classes:
        files = [f["name"] for f in get_json(f"{API}/{urllib.parse.quote(cls)}") if f["type"] == "file"]
        picked = rng.sample(files, min(args.per_class, len(files)))
        os.makedirs(os.path.join(args.out, cls), exist_ok=True)
        for name in picked:
            url = f"{RAW}/{urllib.parse.quote(cls)}/{urllib.parse.quote(name)}"
            jobs.append((url, os.path.join(args.out, cls, name)))
        print(f"  {cls}: {len(picked)} of {len(files)} images queued")

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(download, jobs))
    ok = sum(1 for _, good in results if good)
    print(f"Downloaded {ok}/{len(jobs)} images into {args.out}")


if __name__ == "__main__":
    main()
