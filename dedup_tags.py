#!/usr/bin/env python3
"""
Thijs Brainjar - CSV dedup

Houdt per UID alleen de meest recente rij (op basis van scanned_at).
Maakt eerst een backup.

Gebruik:
    python dedup_tags.py
"""

import csv
import shutil
from pathlib import Path

CSV_PATH = Path("tags/tags.csv")
BACKUP = Path("tags/tags.csv.before_dedup")


def main():
    if not CSV_PATH.exists():
        print(f"Geen CSV gevonden op {CSV_PATH}")
        return

    shutil.copy(CSV_PATH, BACKUP)
    print(f"Backup gemaakt: {BACKUP}")

    with CSV_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Per UID: houd de rij met de hoogste scanned_at
    latest = {}
    for row in rows:
        uid = row["uid"]
        if uid not in latest or row["scanned_at"] > latest[uid]["scanned_at"]:
            latest[uid] = row

    # Sorteer op scanned_at voor leesbaarheid
    kept = sorted(latest.values(), key=lambda r: r["scanned_at"])

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    removed = len(rows) - len(kept)
    print(f"Behouden: {len(kept)} unieke tags")
    print(f"Verwijderd: {removed} oudere duplicaten")
    print("\nHuidige inhoud:")
    for r in kept:
        aff = f" [{r['affiliatie']}]" if r['affiliatie'] else ""
        print(f"  {r['uid']}  {r['label']}  ({r['type']}{aff})")


if __name__ == "__main__":
    main()
