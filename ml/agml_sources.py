"""Write agri/data/extra_sources.json: licence and citation for every dataset used by the extra model.

    python ml/agml_sources.py
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ml"))
from fetch_agml import DATASETS  # noqa: E402


def readme(name):
    req = urllib.request.Request(f"https://huggingface.co/datasets/Project-AgML/{name}/raw/main/README.md",
                                 headers={"User-Agent": "smart-agri-assistant"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def citation(text):
    body = text.split("---", 2)[2] if text.startswith("---") else text
    m = re.search(r"title\s*=\s*\{(.+?)\}", body)
    title = m.group(1) if m else None
    a = re.search(r"author\s*=\s*\{(.+?)\}", body, re.S)
    authors = " ".join(a.group(1).split()) if a else None
    y = re.search(r"year\s*=\s*\{?(\d{4})", body)
    j = re.search(r"(journal|booktitle|publisher)\s*=\s*\{(.+?)\}", body)
    doi = re.search(r"(10\.\d{4,9}/[^\s\"<>,}]+)", body)
    if authors and len(authors) > 90:
        authors = authors.split(" and ")[0] + " et al."
    return {"title": title, "authors": authors, "year": y.group(1) if y else None,
            "venue": j.group(2) if j else None, "doi": doi.group(1).rstrip(".") if doi else None}


def main():
    out = []
    for crop, sources in DATASETS.items():
        for name, licence, _ in sources:
            try:
                cite = citation(readme(name))
            except Exception as exc:  # noqa: BLE001
                cite = {"error": str(exc)}
            out.append({"crop": crop, "dataset": name, "licence": licence,
                        "url": f"https://huggingface.co/datasets/Project-AgML/{name}", **cite})
            print(crop, name, licence, "|", cite.get("title"), cite.get("year"))
    with open(os.path.join(ROOT, "agri", "data", "extra_sources.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
