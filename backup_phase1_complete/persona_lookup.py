#!/usr/bin/env python3
"""
Thijs Brainjar - Persona Lookup Helper

Zoekt charactersheets in een folder voor een gegeven IC-naam.
Gebruikt fuzzy matching omdat filenames inconsistent zijn:
"Charactersheet_Bernard.pdf", "Vault_25_Charactersheet.docx", etc.

Gebruik:
    python persona_lookup.py "Bernard"
    python persona_lookup.py "Bernard Blok"
    python persona_lookup.py --list   # toon alle gevonden sheets

Default zoekpad: ./charactersheets/
Pas SHEETS_DIR aan als je een andere folder gebruikt.
"""

import sys
import re
from pathlib import Path

SHEETS_DIR = Path("charactersheets")  # pas aan naar jouw folder

# Extensies om te scannen
EXTS = [".docx", ".pdf", ".odt", ".txt", ".md"]


def normalize(s: str) -> str:
    """Lower-case, strip punctuatie, vervang underscores en streepjes."""
    s = s.lower()
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_sheets():
    if not SHEETS_DIR.exists():
        print(f"❌ Folder niet gevonden: {SHEETS_DIR.absolute()}")
        print(f"   Pas SHEETS_DIR bovenaan dit script aan, of leg je sheets in {SHEETS_DIR}/")
        sys.exit(1)
    files = []
    for ext in EXTS:
        files.extend(SHEETS_DIR.rglob(f"*{ext}"))
    return sorted(files)


def list_all():
    files = find_sheets()
    print(f"Gevonden {len(files)} sheets in {SHEETS_DIR}:")
    for f in files:
        print(f"  {f.name}")


def search(query: str):
    files = find_sheets()
    needle = normalize(query)
    needle_parts = needle.split()

    scored = []
    for f in files:
        name = normalize(f.stem)
        # Score = aantal needle-woorden dat in filename voorkomt
        score = sum(1 for part in needle_parts if part in name)
        if score > 0:
            scored.append((score, f))

    scored.sort(key=lambda x: (-x[0], x[1].name))

    if not scored:
        print(f"❌ Geen sheet gevonden voor '{query}'")
        print(f"   Probeer 'python persona_lookup.py --list' om beschikbare sheets te zien")
        return

    print(f"🔍 Resultaten voor '{query}':")
    for score, f in scored[:5]:
        rel = f.relative_to(SHEETS_DIR) if SHEETS_DIR in f.parents else f
        print(f"   [{score}]  {rel}")

    if len(scored) > 5:
        print(f"   ... en nog {len(scored) - 5} matches")

    # Best match details
    best = scored[0][1]
    print(f"\n✓ Beste match: {best.name}")
    print(f"   Pad: {best.absolute()}")
    print(f"   Grootte: {best.stat().st_size} bytes")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    arg = sys.argv[1]
    if arg in ("--list", "-l"):
        list_all()
    else:
        search(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
