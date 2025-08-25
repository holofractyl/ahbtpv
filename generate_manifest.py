#!/usr/bin/env python3
import os, json, hashlib, unicodedata, time, argparse, pathlib, re
from typing import List, Dict, Tuple
import requests

# -------- Utilities --------

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def sha3(b: bytes) -> bytes:
    return hashlib.sha3_256(b).digest()

def hhex(b: bytes) -> str:
    return b.hex()

def merkle_root(leaves: List[bytes]) -> bytes:
    if not leaves:
        return sha3(b"")
    layer = leaves[:]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i+1] if i+1 < len(layer) else left
            nxt.append(sha3(left + right))
        layer = nxt
    return layer[0]

def int_mod(b: bytes, m: int) -> int:
    return int.from_bytes(b, "big") % m

def find_nonce_for_mod19(root: bytes, limit: int = 2_000_000) -> Tuple[int, bytes]:
    for nonce in range(limit):
        h = sha3(root + nonce.to_bytes(8, "big"))
        if int_mod(h, 19) == 0:
            return nonce, h
    raise RuntimeError("No nonce found within limit; increase search space.")

# -------- Caching --------

CACHE = os.path.join("out", "cache")
os.makedirs(CACHE, exist_ok=True)

def cache_get(path: str):
    p = os.path.join(CACHE, path)
    return open(p, "rb").read() if os.path.exists(p) else None

def cache_put(path: str, data: bytes):
    p = os.path.join(CACHE, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f: f.write(data)

# -------- Qur'an (Tanzil Uthmani) --------

TANZIL_URL = "https://tanzil.net/pub/download/"
# We fetch: quran-uthmani.txt  (one verse per line, "SURA:AYA|TEXT")
# See: https://tanzil.net/docs/download
QURAN_FILE = "quran-uthmani.txt"

def fetch_quran_uthmani() -> str:
    cache_key = f"tanzil/{QURAN_FILE}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached.decode("utf-8")
    url = TANZIL_URL + QURAN_FILE
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    cache_put(cache_key, r.content)
    return r.text

def build_quran_manifest() -> Dict:
    text = fetch_quran_uthmani()
    # Parse lines like "1:1|بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
    chapters: Dict[str, List[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line: 
            continue
        ref, verse = line.split("|", 1)
        sura = ref.split(":")[0]
        chapters.setdefault(sura, []).append(nfc(verse))

    manifest = {
        "profile": {
            "tradition": "QURAN",
            "source": "Tanzil",
            "edition": "Uthmani (UTF-8)",
            "url": TANZIL_URL + QURAN_FILE
        },
        "chapters": []
    }

    for sura in sorted(chapters, key=lambda x: int(x)):
        verses = chapters[sura]
        verse_hashes = [sha3(v.encode("utf-8")) for v in verses]
        root = merkle_root(verse_hashes)
        nonce, sealed = find_nonce_for_mod19(root)
        manifest["chapters"].append({
            "name": f"Sura {sura}",
            "verse_count": len(verses),
            "verse_hashes_hex": [hhex(h) for h in verse_hashes],
            "chapter_root_hex": hhex(root),
            "nonce_uint64": nonce,
            "sealed_root_hex": hhex(sealed),
            "sealed_root_mod19": int_mod(sealed, 19),
        })
    return manifest

# -------- Torah Sidrot (Sefaria) --------

SEFARIA_TEXTS = "https://www.sefaria.org/api/texts/{ref}?lang=he&vhe=Tanach%20with%20Nikud%20and%20Cantillation"
# Version parameter may vary; this tries to request vowels+trope where available.

HEBREW_LETTERS_RE = re.compile(r"[\u0590-\u05FF\uFB1D-\uFB4F\u05BD\u05B0-\u05BC\u05C1\u05C2\u0591-\u05AF]+")

def fetch_sefaria_ref(ref: str) -> List[str]:
    key = "sefaria/" + ref.replace(" ", "_") + ".json"
    cached = cache_get(key)
    if cached is None:
        url = SEFARIA_TEXTS.format(ref=ref)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        cache_put(key, r.content)
        data = r.json()
    else:
        data = json.loads(cached.decode("utf-8"))
    # 'text' may be nested; flatten to verse strings
    verses: List[str] = []
    def flatten(x):
        if isinstance(x, list):
            for y in x: flatten(y)
        elif isinstance(x, str):
            verses.append(nfc(x))
    flatten(data.get("text", []))
    # Filter out non-Hebrew lines (just in case)
    verses = [v for v in verses if HEBREW_LETTERS_RE.search(v)]
    return verses

def build_torah_manifest(sidrot_list: List[str]) -> Dict:
    manifest = {
        "profile": {
            "tradition": "TORAH",
            "source": "Sefaria",
            "version_hint": "Hebrew with vowels + cantillation",
            "url_template": SEFARIA_TEXTS
        },
        "sidrot": []
    }
    for ref in sidrot_list:
        verses = fetch_sefaria_ref(ref)
        if not verses:
            print(f"WARNING: No verses retrieved for {ref}")
            continue
        verse_hashes = [sha3(v.encode("utf-8")) for v in verses]
        root = merkle_root(verse_hashes)
        nonce, sealed = find_nonce_for_mod19(root)
        manifest["sidrot"].append({
            "name": ref,
            "verse_count": len(verses),
            "verse_hashes_hex": [hhex(h) for h in verse_hashes],
            "sidra_root_hex": hhex(root),
            "nonce_uint64": nonce,
            "sealed_root_hex": hhex(sealed),
            "sealed_root_mod19": int_mod(sealed, 19),
        })
    return manifest

# -------- CLI --------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=["quran","torah"], help="Which corpus to process")
    parser.add_argument("--sidrot", default="sidrot.json", help="Path to JSON list of Sefaria refs for sidrot")
    parser.add_argument("--outdir", default="out", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.which == "quran":
        m = build_quran_manifest()
        p = os.path.join(args.outdir, "quran_manifest.json")
        with open(p, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=2)
        print("Wrote", p)
    elif args.which == "torah":
        with open(args.sidrot, "r", encoding="utf-8") as f:
            sid = json.load(f)
        m = build_torah_manifest(sid)
        p = os.path.join(args.outdir, "torah_manifest.json")
        with open(p, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=2)
        print("Wrote", p)

if __name__ == "__main__":
    main()
