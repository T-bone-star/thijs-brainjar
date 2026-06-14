#!/usr/bin/env python3
"""
Thijs Brainjar - Merge personas

Voegt de volgende persona-data toe aan personas.json:
- Mark de Ever's UID (04517501110716)
- Jack van Loon (complete entry)
- Charléne D'Hoe (complete entry)

Idempotent: kan veilig meerdere keren gedraaid worden.
Bestaande entries worden NIET overschreven, alleen aangevuld.
"""

import json
import shutil
from pathlib import Path

JSON_PATH = Path("personas.json")
BACKUP = Path("personas.json.before_merge")

# UID-toevoegingen voor bestaande entries
UID_UPDATES = {
    "mark_de_ever": "04517501110716",
}

# Nieuwe personas om toe te voegen (alleen als ze nog niet bestaan)
NEW_PERSONAS = {
    "jack_van_loon": {
      "uid": "04518C01400716",
      "naam": "Jack van Loon",
      "type": "inner_circle",
      "affiliatie": "Rad Roach",
      "leeftijd": 33,
      "huidige_rol": "Hardware computerexpert",
      "vroegere_rol": "Rad Roach, lid van de GECK-delegatie",
      "is_speler": True,
      "speler_oc_naam": "",
      "achtergrond": {
        "korte_samenvatting": "Oudere broer van Hendrick (Underseer). Hardware-expert waar Hendrick software doet. Zat in de GECK-delegatie en heeft de missie helpen slagen — maar was fel tegen het offeren van Thijs. Was als enige Rad Roach demonstratief afwezig bij de extractie.",
        "uitgebreid": "Jack en Hendrick groeiden samen op in het van Loon-gezin: strenge, plichtsbewuste vader Frederick, chaotisch-creatieve moeder Winnifred. Beide broers zetten zich af tegen ouderlijke autoriteit en vonden hun plek bij de Rad Roaches. Ze erfden samen de militaire uitrusting van hun opa, Generaal Theodoor van Loon. Jack werd hardware computerexpert — de fysieke tegenhanger van Hendricks software-werk. Hij zat in de delegatie die de GECK ging halen en geloofde in dat doel. Maar toen het plan kwam om Thijs' brein te extracten als control-systeem voor de GECK, trok Jack de grens. Hij vond de prijs te hoog. Tijdens de operatie bleef hij demonstratief weg — de enige Rad Roach die er niet bij was. Dat was geen verraad aan de zaak; het was protest tegen wat hij zag als een offer dat niemand had mogen vragen."
      },
      "persoonlijkheid": {
        "kern_traits": ["principieel", "koppig", "loyaal-maar-met-grenzen", "praktisch-ingesteld"],
        "spraakstijl": "TBD",
        "humor": "TBD",
        "triggers_pos": ["zijn broer Hendrick", "praktische hardware-problemen oplossen"],
        "triggers_neg": ["het Thijs-offer ter sprake", "beschuldigd worden van het in de steek laten van de groep", "suggestie dat hij tegen de GECK-missie was (dat was hij niet)"]
      },
      "relations": [
        {
          "target": "Hendrick van Loon",
          "type": "familie",
          "public_summary": "Jongere broer, nu Underseer",
          "story": "Samen opgegroeid, samen Rad Roach geworden, samen de uitrusting van opa geerfd. Jacks afwezigheid bij Thijs' extractie zit nu tussen hen in — Hendrick was er wel, Jack niet."
        },
        {
          "target": "Thijs",
          "type": "vriend",
          "public_summary": "Rad Roach-makker — Jack was tegen zijn offer",
          "story": "Jack was de enige Rad Roach die niet bij Thijs' operatie aanwezig was, uit protest. Hij vond het offer te groot. Hun relatie is nu beladen: Thijs weet niet of hij Jack dankbaar moet zijn (hij was de enige die het te ver vond) of boos (hij liet Thijs alleen in dat moment). Jack zelf worstelt waarschijnlijk met dezelfde vraag."
        }
      ],
      "secrets": [
        {
          "content": "Jack voelt mogelijk schuld dat hij wegbleef — niet omdat hij ongelijk had over het offer, maar omdat hij Thijs alleen liet op het zwaarste moment. Dat hij gelijk had maakt het niet makkelijker.",
          "visibility": "self_only"
        }
      ],
      "knows_about_others": []
    },

    "charlene_dhoe": {
      "uid": "04518201E20716",
      "naam": "Charléne D'Hoe",
      "type": "vaultdweller",
      "affiliatie": "",
      "leeftijd": 27,
      "huidige_rol": "Dokter",
      "vroegere_rol": "Dokter in Vault 324 (België), werkte aan uranium-experimenten",
      "is_speler": True,
      "speler_oc_naam": "Wendy de Jong-Martens",
      "achtergrond": {
        "korte_samenvatting": "Dokter uit Vault 324 in België, 27j. Kwam naar Vault 25 op zoek naar uranium-leveringen. Radiation immune, gespecialiseerd in medicine. Lijkt een gewone, fitte dokter — maar draagt een geheim dat ze voor iedereen verbergt.",
        "uitgebreid": "Charléne groeide op in Vault 324 (België) in een gezin dat was opgezet als 'perfect gezin': vader Gillian (herborist), moeder Romina (dokter), broer Nico (laborant). In Vault 324 onderzochten dokters het effect van uranium op mensen — via injecties tijdens de jaarlijkse griepprik en via voedsel. Als dokter hielp Charléne mee aan deze experimenten en ondervond zelf geen negatieve effecten van uranium; ze denkt zelfs dat het positief werkt en is naar eigen weten nooit ziek geweest. Ze werkte nauw samen met Dr. H.a.h.n., het Miss Nanny dokter-model van Vault 324. Als een van de fitste bewoners werd ze gevraagd uit te zoeken wat er met de uranium-leveringen was gebeurd; Vault 324 heeft minimaal 500 kilo uranium nodig om weer te draaien. Via Overseer Bogaerts kreeg ze de opdracht naar Vault 26 te gaan, plus een toegangspasje tot Vault 25."
      },
      "persoonlijkheid": {
        "kern_traits": ["toegewijd dokter", "bewijsdrang", "beheerst", "verbergt iets"],
        "spraakstijl": "TBD",
        "humor": "TBD",
        "triggers_pos": ["medisch werk waarin ze zich kan bewijzen", "uranium/straling (ziet het positief)"],
        "triggers_neg": ["vragen over wat ze precies is", "het woord synth", "twijfel aan haar menselijkheid"]
      },
      "relations": [
        {
          "target": "Dr. H.a.h.n.",
          "type": "mentor",
          "public_summary": "Miss Nanny dokter-model van Vault 324, haar rolmodel",
          "story": "Charléne werkte nauw samen met Hahn en wilde net zo'n dokter worden. Off-screen NPC."
        }
      ],
      "secrets": [
        {
          "content": "Charléne is een 3e-generatie synth. Zij weet dit zelf en HAAT het — het is een geheime last die ze met zich meedraagt. Voor haarzelf is dit een self_only worsteling.",
          "visibility": "sl_only"
        },
        {
          "content": "BRIDGE-INSTRUCTIE: Thijs WEET NIET dat Charléne een synth is. Hij mag dit op geen enkele manier suggereren, ontwijken of verraden. Voor Thijs is zij gewoon een dokter uit Vault 324. Als iemand ernaar vraagt: Thijs weet oprecht van niets.",
          "visibility": "sl_only"
        },
        {
          "content": "Zoekt uranium voor Vault 324 (minimaal 500 kilo nodig). Reist met een toegangspasje tot Vault 25.",
          "visibility": "public"
        }
      ],
      "knows_about_others": []
    }
}


def main():
    if not JSON_PATH.exists():
        print(f"❌ Geen personas.json gevonden op {JSON_PATH}")
        return

    shutil.copy(JSON_PATH, BACKUP)
    print(f"📋 Backup: {BACKUP}\n")

    with JSON_PATH.open("r") as f:
        data = json.load(f)

    personas = data.setdefault("personas", {})

    # ─────────────────────────────────────
    # FASE 1: UID-updates voor bestaande entries
    # ─────────────────────────────────────
    print("━━━ FASE 1: UID-updates ━━━")
    uid_changes = 0
    for key, new_uid in UID_UPDATES.items():
        if key in personas:
            current = personas[key].get("uid")
            if current == new_uid:
                print(f"  ℹ  {key}: UID al correct ({new_uid})")
            elif current in (None, ""):
                personas[key]["uid"] = new_uid
                print(f"  ✓ {key}: UID toegevoegd → {new_uid}")
                uid_changes += 1
            else:
                print(f"  ⚠  {key}: heeft al UID '{current}', niet overschreven (verwachte: {new_uid})")
        else:
            print(f"  ⚠  {key}: niet aanwezig in personas.json — overslaan")
    print(f"→ {uid_changes} UID's bijgewerkt\n")

    # ─────────────────────────────────────
    # FASE 2: Nieuwe persona's toevoegen
    # ─────────────────────────────────────
    print("━━━ FASE 2: Persona's toevoegen ━━━")
    added = 0
    for key, persona in NEW_PERSONAS.items():
        if key in personas:
            print(f"  ℹ  {key}: bestaat al, overgeslagen (niet overschreven)")
        else:
            personas[key] = persona
            print(f"  ✓ {key}: toegevoegd ({persona['naam']}, UID {persona['uid']})")
            added += 1
    print(f"→ {added} persona's toegevoegd\n")

    # ─────────────────────────────────────
    # Opslaan
    # ─────────────────────────────────────
    with JSON_PATH.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"━━━ KLAAR ━━━")
    print(f"Totaal persona-entries: {len(personas)}")
    print(f"Backup beschikbaar in: {BACKUP}")
    print(f"\nDraai `python validate.py` om resultaat te controleren.")


if __name__ == "__main__":
    main()
