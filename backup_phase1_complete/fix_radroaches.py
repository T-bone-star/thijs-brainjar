#!/usr/bin/env python3
"""
Thijs Brainjar - Quick fix: Rad Roaches naar inner_circle

Zet de 5 Rad Roach-leden om:
- type: vaultdweller -> inner_circle
- affiliatie: leeg -> Rad Roach
- notes: "Rad Roach," / "Radroach" eruit gehaald (staat nu in affiliatie)
"""

import csv
import re
import shutil
from pathlib import Path

CSV_PATH = Path("tags/tags.csv")
BACKUP = Path("tags/tags.csv.before_radroach_fix")

# UID -> verwachte naam (voor sanity check)
RAD_ROACHES = {
    "0441F101200716": "Bertus de Kleine",
    "04512301360716": "Hendrick van Loon",
    "04512601F00716": "Betty Hageman",
    "04518C01400716": "Jack van Loon",
    "04511801290716": "Jhonny Bilderberg",
}


def clean_notes(notes: str) -> str:
    """Verwijder 'Rad Roach' / 'Radroach' varianten uit notes."""
    # Verwijder met omliggende komma's en spaties
    patterns = [
        r"\s*,\s*Rad Roach\s*",
        r"\s*,\s*Radroach\s*",
        r"^Rad Roach\s*,\s*",
        r"^Radroach\s*,\s*",
        r"^Rad Roach$",
        r"^Radroach$",
    ]
    out = notes
    for p in patterns:
        out = re.sub(p, "", out, flags=re.IGNORECASE)
    # Opruimen van dubbele komma's / trailing
    out = re.sub(r",\s*,", ",", out).strip(" ,")
    return out


def main():
    if not CSV_PATH.exists():
        print(f"Geen CSV gevonden op {CSV_PATH}")
        return

    shutil.copy(CSV_PATH, BACKUP)
    print(f"Backup: {BACKUP}\n")

    with CSV_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    for row in rows:
        if row["uid"] in RAD_ROACHES:
            expected = RAD_ROACHES[row["uid"]]
            if row["label"] != expected:
                print(f"  ⚠  UID {row['uid']}: label is '{row['label']}', verwacht '{expected}' — overgeslagen")
                continue
            old_notes = row["notes"]
            row["type"] = "inner_circle"
            row["affiliatie"] = "Rad Roach"
            row["notes"] = clean_notes(old_notes)
            print(f"  ✓ {row['label']}")
            print(f"      type: vaultdweller -> inner_circle")
            print(f"      affiliatie: -> Rad Roach")
            if old_notes != row["notes"]:
                print(f"      notes: '{old_notes}'")
                print(f"          -> '{row['notes']}'")
            print()
            changed += 1

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Klaar — {changed} tags aangepast.\n")
    print("Huidige inhoud:")
    for row in rows:
        aff = f" [{row['affiliatie']}]" if row['affiliatie'] else ""
        print(f"  {row['uid']}  {row['label']:25s} ({row['type']}{aff})")


if __name__ == "__main__":
    main()
