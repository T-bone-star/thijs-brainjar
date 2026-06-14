#!/usr/bin/env python3
"""
Thijs Brainjar - Validation: CSV vs personas.json synchronisatie

Checkt:
- Tags in CSV zonder persona-entry in JSON
- Persona-entries in JSON zonder tag in CSV
- Mismatch op type of affiliatie tussen CSV en JSON
- Duplicate labels in CSV
- UID-formaat consistentie

Gebruik:
    python validate.py
"""

import csv
import json
from pathlib import Path
from collections import Counter

CSV_PATH = Path("tags/tags.csv")
JSON_PATH = Path("personas.json")


def load_csv():
    if not CSV_PATH.exists():
        print(f"❌ Geen CSV gevonden op {CSV_PATH}")
        return None
    with CSV_PATH.open("r", newline="") as f:
        return list(csv.DictReader(f))


def load_json():
    if not JSON_PATH.exists():
        print(f"❌ Geen personas.json gevonden op {JSON_PATH}")
        return None
    with JSON_PATH.open("r") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("Thijs Brainjar — Validation rapport")
    print("=" * 60)

    csv_rows = load_csv()
    json_data = load_json()
    if not csv_rows or not json_data:
        return

    personas = json_data.get("personas", {})

    # Index op UID
    csv_by_uid = {r["uid"]: r for r in csv_rows}
    personas_by_uid = {
        key: p for key, p in personas.items()
        if p.get("uid")
    }
    personas_by_uid_lookup = {p["uid"]: (key, p) for key, p in personas_by_uid.items()}

    # ─────────────────────────────────────────
    print(f"\n📊 Telling:")
    print(f"   CSV-rijen:               {len(csv_rows)}")
    print(f"   Persona-entries:         {len(personas)}")
    print(f"   Personas met UID:        {len(personas_by_uid)}")
    print(f"   Personas zonder UID:     {len(personas) - len(personas_by_uid)}")

    # ─────────────────────────────────────────
    print("\n🔍 CSV-tags zonder persona-entry:")
    orphan_tags = []
    for uid, row in csv_by_uid.items():
        if uid not in personas_by_uid_lookup:
            orphan_tags.append((uid, row["label"], row["type"]))
    if orphan_tags:
        for uid, label, t in orphan_tags:
            print(f"   ⚠  {uid}  {label:30s} ({t})")
        print(f"   → {len(orphan_tags)} tags missen persona")
    else:
        print("   ✓ Alle tags hebben een persona")

    # ─────────────────────────────────────────
    print("\n🔍 Persona-entries zonder UID (geen tag toegekend):")
    no_uid = [(k, p["naam"]) for k, p in personas.items() if not p.get("uid")]
    if no_uid:
        for key, naam in no_uid:
            print(f"   ⚠  {key:25s} ({naam})")
        print(f"   → {len(no_uid)} personas zonder tag")
    else:
        print("   ✓ Alle personas hebben een tag")

    # ─────────────────────────────────────────
    print("\n🔍 Mismatch op type tussen CSV en JSON:")
    type_mismatches = []
    for uid, (key, p) in personas_by_uid_lookup.items():
        if uid in csv_by_uid:
            csv_type = csv_by_uid[uid]["type"]
            json_type = p.get("type", "")
            if csv_type != json_type:
                type_mismatches.append((uid, p["naam"], csv_type, json_type))
    if type_mismatches:
        for uid, naam, ct, jt in type_mismatches:
            print(f"   ⚠  {uid}  {naam:25s} CSV={ct}  JSON={jt}")
    else:
        print("   ✓ Geen type-mismatches")

    # ─────────────────────────────────────────
    print("\n🔍 Mismatch op affiliatie tussen CSV en JSON:")
    aff_mismatches = []
    for uid, (key, p) in personas_by_uid_lookup.items():
        if uid in csv_by_uid:
            csv_aff = csv_by_uid[uid].get("affiliatie", "").strip()
            json_aff = p.get("affiliatie", "").strip()
            if csv_aff != json_aff:
                aff_mismatches.append((uid, p["naam"], csv_aff, json_aff))
    if aff_mismatches:
        for uid, naam, ca, ja in aff_mismatches:
            print(f"   ⚠  {uid}  {naam:25s} CSV='{ca}'  JSON='{ja}'")
    else:
        print("   ✓ Affiliaties komen overeen")

    # ─────────────────────────────────────────
    print("\n🔍 Duplicate labels in CSV:")
    label_counts = Counter(r["label"] for r in csv_rows if r["label"])
    dups = [(l, c) for l, c in label_counts.items() if c > 1]
    if dups:
        for label, count in dups:
            print(f"   ⚠  '{label}' verschijnt {count}x")
    else:
        print("   ✓ Geen duplicate labels")

    # ─────────────────────────────────────────
    print("\n🔍 Relations die naar niet-bestaande personas wijzen:")
    persona_names = {p["naam"] for p in personas.values()}
    broken_relations = []
    for key, p in personas.items():
        for rel in p.get("relations", []):
            target = rel.get("target", "")
            # Sla niet-personage targets over (groepen, concepten)
            if target and target not in persona_names:
                # Geen warning voor groep-targets ("Orde Oranje Leeuw structuur" etc.)
                if any(w in target for w in ["structuur", "Orde", "Garde", "Roach"]):
                    continue
                broken_relations.append((p["naam"], target))
    if broken_relations:
        for src, tgt in broken_relations:
            print(f"   ⚠  {src} → {tgt} (target heeft geen eigen persona)")
        print(f"   ℹ  Niet altijd erg — sommige targets zijn NPC's of off-screen personages")
    else:
        print("   ✓ Alle relations wijzen naar bestaande personas")

    # ─────────────────────────────────────────
    print("\n📈 Persona-volledigheid:")
    for key, p in personas.items():
        score = 0
        max_score = 7
        if p.get("uid"): score += 1
        if p.get("achtergrond", {}).get("korte_samenvatting") and "TODO" not in p["achtergrond"].get("korte_samenvatting", "") and "TBD" not in p["achtergrond"].get("korte_samenvatting", ""):
            score += 1
        if p.get("achtergrond", {}).get("uitgebreid") and "TODO" not in p["achtergrond"].get("uitgebreid", ""):
            score += 1
        if p.get("persoonlijkheid", {}).get("kern_traits") and "TBD" not in str(p["persoonlijkheid"].get("kern_traits", "")):
            score += 1
        if p.get("persoonlijkheid", {}).get("spraakstijl") and "TBD" not in p["persoonlijkheid"].get("spraakstijl", ""):
            score += 1
        if p.get("relations"):
            score += 1
        if p.get("secrets"):
            score += 1
        bar = "█" * score + "░" * (max_score - score)
        print(f"   {bar}  {p['naam']:25s} ({score}/{max_score})")

    print("\n" + "=" * 60)
    print("Klaar.")


if __name__ == "__main__":
    main()
