#!/usr/bin/env python3
"""
Thijs Brainjar - RFID tag inscan-tool

Wacht op een tag op de ACR122U, leest UID uit, vraagt om een label,
en schrijft de combinatie weg in tags.csv.

Gebruik:
    python scan_tags.py

Stop met Ctrl+C.
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import NoCardException, CardConnectionException

CSV_PATH = Path("tags/tags.csv")
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]  # ACR122U: get UID


def ensure_csv():
    CSV_PATH.parent.mkdir(exist_ok=True)
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["uid", "label", "type", "notes", "scanned_at"])


def load_existing_uids():
    uids = {}
    if not CSV_PATH.exists():
        return uids
    with CSV_PATH.open("r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            uids[row["uid"]] = row
    return uids


def append_row(uid, label, tag_type, notes):
    with CSV_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        w.writerow([uid, label, tag_type, notes, datetime.now().isoformat(timespec="seconds")])


def get_reader():
    r = readers()
    if not r:
        print("Geen reader gevonden. Is de ACR122U ingeplugd en draait pcscd?")
        sys.exit(1)
    print(f"Reader: {r[0]}")
    return r[0]


def read_uid(reader):
    """Probeer een tag te lezen. Returnt UID-hex string of None."""
    try:
        conn = reader.createConnection()
        conn.connect()
        data, sw1, sw2 = conn.transmit(GET_UID_APDU)
        conn.disconnect()
        if sw1 == 0x90 and sw2 == 0x00:
            return toHexString(data).replace(" ", "")
        return None
    except NoCardException:
        return None
    except CardConnectionException:
        return None
    except Exception as e:
        print(f"  ! Onverwachte fout: {e}")
        return None


def prompt_label(uid, existing):
    if uid in existing:
        prev = existing[uid]
        print(f"  ⚠  Deze UID is al ingelezen als: {prev['label']} ({prev['type']})")
        again = input("  Overschrijven? [j/N]: ").strip().lower()
        if again != "j":
            return None

    label = input("  Label (naam speler of groep): ").strip()
    if not label:
        print("  Geen label, overgeslagen.")
        return None

    print("  Type: [v]aultdweller / [g]roep / [a]nder")
    t = input("  Type [v/g/a]: ").strip().lower()
    type_map = {"v": "vaultdweller", "g": "groep", "a": "ander"}
    tag_type = type_map.get(t, "ander")

    notes = input("  Notities (optioneel, enter om over te slaan): ").strip()
    return label, tag_type, notes


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
            # Tag ligt er nog, niet opnieuw vragen
            time.sleep(0.3)
            continue

        last_uid = uid
        print(f"\n● Tag gedetecteerd — UID: {uid}")

        result = prompt_label(uid, existing)
        if result is None:
            print("  → niet opgeslagen.\n")
            # Wacht tot tag eraf is voor we doorgaan
            while read_uid(reader) is not None:
                time.sleep(0.3)
            continue

        label, tag_type, notes = result
        append_row(uid, label, tag_type, notes)
        existing[uid] = {"uid": uid, "label": label, "type": tag_type, "notes": notes}
        total = len(existing)
        print(f"  ✓ opgeslagen ({total} tags totaal)\n")
        print("  Haal de tag eraf en leg de volgende erop...\n")

        # Wacht tot tag eraf is
        while read_uid(reader) is not None:
            time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGestopt. Bekijk tags/tags.csv voor de resultaten.")
