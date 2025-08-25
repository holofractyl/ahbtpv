# ahbtpv
ABRAHAMIC HOLY BOOK TAMPER PROTECTION VALIDATOR
===============================================
(C) 2025 Holofractyl on GitHub, forking welcome

This code was intended as a proof of concept of the 19-based tamper-protection method, claimed to protect the Holy Qur'an and Torah from forgery or changes to their original text. It can be used to generate a demonstration seal on the desired scripture, as a test. No support or warranty can regrettably be provided. Questions: Phoenicia .....a.t.. reborn........dot...com

It builds cryptographic manifests (with 19-integration) for:
  • FULL Qur'an (Uthmani script with diacritics) from Tanzil
  • Torah sidrot from Sefaria (Hebrew with niqqud + cantillation)

Outputs (created under ./out/):
  - quran_manifest.json
  - torah_manifest.json

Requirements
------------
Python 3.9+
pip install -r requirements.txt

Authoritative Sources
---------------------
Qur'an: Tanzil download (Uthmani) – see docs: https://tanzil.net/docs/download
Torah: Sefaria texts API – see: https://developers.sefaria.org/reference/getting-started

How to Run
----------
1) Create a venv (optional) and install deps:
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt

2) Build the FULL QUR'AN manifest:
   python generate_manifest.py quran

   This fetches the Uthmani text from Tanzil and produces:
     out/quran_manifest.json

3) Build the TORAH manifest (by sidra):
   python generate_manifest.py torah

   By default, it uses a sample sidra index (sidrot.json) with refs like:
   ["Bereshit 1:1-6:8", "Noach 6:9-11:32", ...]
   You can replace 'sidrot.json' with your own list of Sefaria refs.
   The script fetches Hebrew with vowels + trope when available.

Data Integrity
--------------
We apply:
  - Unicode NFC normalization
  - SHA3-256 per verse
  - Merkle tree per chapter/sidra
  - Nonce so that sealed root ≡ 0 (mod 19): SHA3(chapter_root || nonce)

The nonce is PUBLIC and committed (no changes to content).

Notes
-----
• Tanzil download terms apply. Version pin defaults to latest; adjust URL if needed.
• Sefaria API rate limits may apply; consider caching (script has simple cache).
• The manifests include profile identifiers stating the exact text provenance.
