#!/usr/bin/env python3
"""
Thijs Brainjar - Fix scan CSV foutjes

Lost op:
1. Label typo's (Sofia, Gene, Barry)
2. Verkeerde types (Sally, Barry)
3. Affiliatie-spelling (blauwe garde -> Blauwe Garde)
4. Interactieve dedup van duplicate labels
"""

import csv
import shutil
from pathlib import Path

CSV_PATH = Path("tags/tags.csv")
BACKUP = Path("tags/tags.csv.before_fix")

# UID-gebaseerde fixes (gebruik UID omdat label varieert)
LABEL_FIXES = {
    "04517201600716": "Sofia \"Soof\" van Gorp",   # PSofia -> Sofia
    "045172015A0716": "Gene Kraft",                  # Gene Kraft. -> Gene Kraft
    "04A119013A4903": "Barry \"D'n Dokter\" van Gorp",  # afgekapt label
}

TYPE_FIXES = {
    "04A1A501384903": ("vaultdweller", ""),               # Sally de Gauw: ander -> vaultdweller
    "04A119013A4903": ("ally", "Familie van Gorp"),       # Barry: ander -> ally + affiliatie
}

# Affiliatie-normalisatie
AFFILIATIE_FIXES = {
    "04517501110716": "Blauwe Garde",  # Mark D'ever: blauwe garde -> Blauwe Garde
}


def main():
    if not CSV_PATH.exists():
        print(f"❌ Geen CSV gevonden op {CSV_PATH}")
        return

    shutil.copy(CSV_PATH, BACKUP)
    print(f"📋 Backup: {BACKUP}\n")

    with CSV_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # ─────────────────────────────────────
    # FASE 1: Label / type / affiliatie fixes
    # ─────────────────────────────────────
    print("━━━ FASE 1: Label/type/affiliatie fixes ━━━\n")
    changed = 0
    for row in rows:
        uid = row["uid"]
        modified = False

        if uid in LABEL_FIXES:
            old = row["label"]
            row["label"] = LABEL_FIXES[uid]
            print(f"  ✓ {uid}  label:  '{old}'")
            print(f"                  → '{row['label']}'")
            modified = True

        if uid in TYPE_FIXES:
            new_type, new_aff = TYPE_FIXES[uid]
            old_type = row["type"]
            old_aff = row["affiliatie"]
            row["type"] = new_type
            row["affiliatie"] = new_aff
            print(f"  ✓ {uid}  type:   '{old_type}' → '{new_type}'")
            if old_aff != new_aff:
                print(f"                  affiliatie: '{old_aff}' → '{new_aff}'")
            modified = True

        if uid in AFFILIATIE_FIXES:
            old = row["affiliatie"]
            row["affiliatie"] = AFFILIATIE_FIXES[uid]
            print(f"  ✓ {uid}  affiliatie: '{old}' → '{row['affiliatie']}'")
            modified = True

        if modified:
            changed += 1

    print(f"\n→ {changed} rijen aangepast in fase 1\n")

    # ─────────────────────────────────────
    # FASE 2: Interactieve duplicate-dedup
    # ─────────────────────────────────────
    print("━━━ FASE 2: Duplicate labels ━━━\n")

    # Groepeer per label
    from collections import defaultdict
    by_label = defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(row)

    duplicates = {label: rs for label, rs in by_label.items() if len(rs) > 1}

    if not duplicates:
        print("  ✓ Geen duplicates meer.\n")
    else:
        rows_to_remove = []
        for label, dup_rows in duplicates.items():
            print(f"\n🔁 Label '{label}' staat {len(dup_rows)}x:")
            for i, r in enumerate(dup_rows, 1):
                print(f"   {i}) UID {r['uid']}  type={r['type']:14s} aff='{r['affiliatie']}'  scanned={r['scanned_at']}")

            print("\n   Wat doen?")
            print("   [k] Allemaal houden (waren bewust 2 tags)")
            print("   [1-N] Alleen deze ene houden, andere(n) verwijderen")
            print("   [r] Hernoemen — geef tweede tag een nieuw label")
            keuze = input("   Keuze: ").strip().lower()

            if keuze == "k":
                print(f"   → '{label}' blijft {len(dup_rows)}x")
            elif keuze == "r":
                new_label = input(f"   Nieuw label voor 2e tag ({dup_rows[1]['uid']}): ").strip()
                if new_label:
                    dup_rows[1]["label"] = new_label
                    print(f"   → UID {dup_rows[1]['uid']} hernoemd naar '{new_label}'")
            elif keuze.isdigit():
                keep_idx = int(keuze) - 1
                if 0 <= keep_idx < len(dup_rows):
                    keep_uid = dup_rows[keep_idx]["uid"]
                    for r in dup_rows:
                        if r["uid"] != keep_uid:
                            rows_to_remove.append(r["uid"])
                            print(f"   ✗ verwijder UID {r['uid']}")
                    print(f"   → behoud UID {keep_uid}")
                else:
                    print(f"   ⚠ Ongeldige keuze, '{label}' blijft ongewijzigd")
            else:
                print(f"   ⚠ Geen keuze, '{label}' blijft ongewijzigd")

        rows = [r for r in rows if r["uid"] not in rows_to_remove]

    # ─────────────────────────────────────
    # Opslaan
    # ─────────────────────────────────────
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n━━━ KLAAR ━━━")
    print(f"Totaal rijen na fix: {len(rows)}")
    print(f"Backup beschikbaar in: {BACKUP}")
    print(f"\nDraai `python validate.py` om resultaat te controleren.")


if __name__ == "__main__":
    main()
