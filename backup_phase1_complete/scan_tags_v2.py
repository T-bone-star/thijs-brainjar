#!/usr/bin/env python3
"""
Thijs Brainjar - RFID tag inscan-tool v2

v2 changes:
- Type 'a' (ally) toegevoegd: spelers met eigen persona én groepsbinding
- Nieuw veld 'affiliatie' voor ally en groep types

Gebruik:
    python scan_tags_v2.py

Stop met Ctrl+C.
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import NoCardException, CardConnectionException

CSV_PATH = Path("tags/tags.csv")
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

FIELDS = ["uid", "label", "type", "affiliatie", "notes", "scanned_at"]


def ensure_csv():
    CSV_PATH.parent.mkdir(exist_ok=True)
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
        return

    # Check header — migreer indien oud schema
    with CSV_PATH.open("r", newline="") as f:
        first = f.readline().strip()
    if first.split(",") == FIELDS:
        return

    print("Oude CSV gedetecteerd — migreren naar nieuw schema (affiliatie toevoegen)...")
    with CSV_PATH.open("r", newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)

    backup = CSV_PATH.with_suffix(".csv.premigration")
    CSV_PATH.rename(backup)
    print(f"  Backup oude CSV: {backup}")

    with CSV_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for row in rows:
            w.writerow([
                row.get("uid", ""),
                row.get("label", ""),
                row.get("type", ""),
                "",  # affiliatie leeg voor bestaande rijen
                row.get("notes", ""),
                row.get("scanned_at", ""),
            ])
    print(f"  ✓ Migratie klaar — {len(rows)} rijen.\n")


def load_existing_uids():
    uids = {}
    if not CSV_PATH.exists():
        return uids
    with CSV_PATH.open("r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            uids[row["uid"]] = row
    return uids


def append_row(uid, label, tag_type, affiliatie, notes):
    with CSV_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            uid, label, tag_type, affiliatie, notes,
            datetime.now().isoformat(timespec="seconds"),
        ])


def get_reader():
    r = readers()
    if not r:
        print("Geen reader gevonden. Is de ACR122U ingeplugd en draait pcscd?")
        sys.exit(1)
    print(f"Reader: {r[0]}")
    return r[0]


def read_uid(reader):
    try:
        conn = reader.createConnection()
        conn.connect()
        data, sw1, sw2 = conn.transmit(GET_UID_APDU)
        conn.disconnect()
        if sw1 == 0x90 and sw2 == 0x00:
            return toHexString(data).replace(" ", "")
        return None
    except (NoCardException, CardConnectionException):
        return None
    except Exception as e:
        print(f"  ! Onverwachte fout: {e}")
        return None


def prompt_label(uid, existing):
    if uid in existing:
        prev = existing[uid]
        print(f"  ⚠  Deze UID is al ingelezen als: {prev['label']} "
              f"({prev['type']}{', ' + prev.get('affiliatie', '') if prev.get('affiliatie') else ''})")
        again = input("  Overschrijven? [j/N]: ").strip().lower()
        if again != "j":
            return None

    label = input("  Label (naam speler of groep): ").strip()
    if not label:
        print("  Geen label, overgeslagen.")
        return None

    print("  Type:")
    print("    [r] inner_circle  — Thijs' eigen kring (Rad Roach etc.)")
    print("    [v] vaultdweller  — overige vault-bewoners met eigen persona")
    print("    [a] ally          — externe persona + groepsbinding (Blauwe Garde etc.)")
    print("    [g] groep         — generieke groepstag, geen vaste speler")
    print("    [x] ander         — overig")
    t = input("  Type [r/v/a/g/x]: ").strip().lower()
    type_map = {
        "r": "inner_circle",
        "v": "vaultdweller",
        "a": "ally",
        "g": "groep",
        "x": "ander",
    }
    tag_type = type_map.get(t, "ander")

    affiliatie = ""
    if tag_type in ("inner_circle", "ally", "groep"):
        default_hint = "bv. 'Rad Roach', 'Blauwe Garde', 'Orde Oranje Leeuw'"
        affiliatie = input(f"  Affiliatie ({default_hint}): ").strip()

    notes = input("  Notities (optioneel): ").strip()
    return label, tag_type, affiliatie, notes


def main():
    ensure_csv()
    reader = get_reader()
    existing = load_existing_uids()
    print(f"Reeds ingelezen: {len(existing)} tags")
    print(f"CSV: {CSV_PATH.absolute()}")
    print("\nLeg een tag op de reader. Ctrl+C om te stoppen.\n")

    last_uid = None
    while True:
        uid = read_uid(reader)

        if uid is None:
            last_uid = None
            time.sleep(0.3)
            continue

        if uid == last_uid:
            time.sleep(0.3)
            continue

        last_uid = uid
        print(f"\n● Tag gedetecteerd — UID: {uid}")

        result = prompt_label(uid, existing)
        if result is None:
            print("  → niet opgeslagen.\n")
            while read_uid(reader) is not None:
                time.sleep(0.3)
            continue

        label, tag_type, affiliatie, notes = result
        append_row(uid, label, tag_type, affiliatie, notes)
        existing[uid] = {
            "uid": uid, "label": label, "type": tag_type,
            "affiliatie": affiliatie, "notes": notes,
        }
        total = len(existing)
        aff_str = f" — {affiliatie}" if affiliatie else ""
        print(f"  ✓ opgeslagen: {label} ({tag_type}{aff_str}) — {total} tags totaal\n")
        print("  Haal de tag eraf en leg de volgende erop...\n")

        while read_uid(reader) is not None:
            time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGestopt. Bekijk tags/tags.csv voor de resultaten.")
