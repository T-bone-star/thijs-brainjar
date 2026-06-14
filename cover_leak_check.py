#!/usr/bin/env python3
"""
cover_leak_check.py — Vault 25 cover-leak controle voor personas.json

Controleert of gevoelige plot-termen (SINISTER, Bokkenrijder, Protean, serum, ...)
voorkomen in velden die Thijs/FreeRadical te zien krijgen. Velden onder
`sl_only` en `self_only` worden overgeslagen — die zijn verborgen voor de props.

Gebruik:
    python3 cover_leak_check.py                      # checkt ./personas.json
    python3 cover_leak_check.py pad/naar/personas.json
    python3 cover_leak_check.py --strict             # warnings tellen ook als fout

Exit code 0 = schoon, 1 = lekken gevonden (handig voor scripts/git hooks).

Tip: draai dit na ELKE wijziging aan personas.json, zeker na retroactieve
canon-correcties die door meerdere personas heen gaan.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

# Velden (keys) waarvan de hele inhoud verborgen is voor de props.
# Alles BUITEN deze velden wordt als Thijs-zichtbaar behandeld en gecheckt.
HIDDEN_FIELDS = {"sl_only", "self_only"}

# Harde lekken: deze termen mogen NOOIT in zichtbare velden staan.
# (regex, label) — case-insensitive.
FORBIDDEN = [
    # SINISTER, ook geschreven als S.I.N.I.S.T.E.R. of S I N I S T E R
    (r"s[\W_]{0,2}i[\W_]{0,2}n[\W_]{0,2}i[\W_]{0,2}s[\W_]{0,2}t[\W_]{0,2}e[\W_]{0,2}r", "SINISTER"),
    (r"bokkenrijder\w*", "Bokkenrijder"),
    (r"protean\w*", "Protean"),
    (r"serum\w*", "serum"),
]

# Zachte signalen: vaak legitiem, maar het waard om even naar te kijken.
# Worden als WAARSCHUWING gerapporteerd (fout bij --strict).
SUSPICIOUS = [
    (r"\bsynth\w*\b", "synth"),
    (r"\binfiltrant\w*\b", "infiltrant"),
    (r"\bspion\w*\b", "spion"),
    (r"\bark\b", "Ark"),
]

# Hoeveel context rond een hit tonen
CONTEXT = 45

# ---------------------------------------------------------------------------

FORBIDDEN_RE = [(re.compile(p, re.IGNORECASE), label) for p, label in FORBIDDEN]
SUSPICIOUS_RE = [(re.compile(p, re.IGNORECASE), label) for p, label in SUSPICIOUS]

NAME_KEYS = ("naam", "name", "ic_naam", "ic_name", "speler", "oc_naam")


def persona_name(obj):
    """Probeer een leesbare naam uit een persona-dict te halen."""
    if isinstance(obj, dict):
        for k in NAME_KEYS:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def snippet(text, start, end):
    a = max(0, start - CONTEXT)
    b = min(len(text), end + CONTEXT)
    s = text[a:b].replace("\n", " ")
    prefix = "…" if a > 0 else ""
    suffix = "…" if b < len(text) else ""
    return f"{prefix}{s}{suffix}"


def scan_text(text, path, owner, hits, warns):
    for rx, label in FORBIDDEN_RE:
        for m in rx.finditer(text):
            hits.append((owner, path, label, snippet(text, m.start(), m.end())))
    for rx, label in SUSPICIOUS_RE:
        for m in rx.finditer(text):
            warns.append((owner, path, label, snippet(text, m.start(), m.end())))


def walk(node, path, owner, hits, warns):
    """Loop recursief door de JSON, sla verborgen velden over."""
    if isinstance(node, dict):
        name = persona_name(node)
        if name:
            owner = name
        for key, value in node.items():
            if key in HIDDEN_FIELDS:
                continue  # verborgen voor Thijs — niet checken
            walk(value, f"{path}.{key}", owner, hits, warns)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk(item, f"{path}[{i}]", owner, hits, warns)
    elif isinstance(node, str):
        scan_text(node, path, owner, hits, warns)
    # getallen/bools/None: niets te checken


def report(title, items):
    print(f"\n{title} ({len(items)}):")
    for owner, path, label, ctx in items:
        who = owner or "(onbekende persona)"
        print(f"  • [{label}] {who}")
        print(f"      veld:    {path}")
        print(f"      context: \"{ctx}\"")


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    json_path = Path(args[0]) if args else Path("personas.json")

    if not json_path.exists():
        print(f"FOUT: bestand niet gevonden: {json_path}")
        return 2

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FOUT: {json_path} is geen geldige JSON: {e}")
        return 2

    hits, warns = [], []
    walk(data, "$", None, hits, warns)

    print(f"Cover-leak check: {json_path}")
    print(f"Verborgen velden (niet gecheckt): {', '.join(sorted(HIDDEN_FIELDS))}")

    if hits:
        report("❌ LEKKEN — termen in Thijs-zichtbare velden", hits)
    if warns:
        report("⚠️  Waarschuwingen — controleer handmatig", warns)

    if not hits and not warns:
        print("\n✅ Schoon. Geen gevoelige termen in zichtbare velden.")
        return 0
    if not hits:
        print("\n✅ Geen harde lekken. Alleen waarschuwingen hierboven.")
        return 1 if strict else 0

    print(f"\n❌ {len(hits)} lek(ken) gevonden. Verplaats deze info naar sl_only "
          f"of herformuleer het zichtbare veld.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
