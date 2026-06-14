# Thijs Brain in a Jar

Een AI-aangedreven "brain in a jar" prop voor een Fallout-LARP in Vault 25. Spelers scannen RFID-tags; de server zoekt de bijbehorende persona op en laat een lokaal Ollama-model reageren in karakter.

## Hoe het werkt

1. Een Pi-prop (bijv. Thijs of FreeRadical) scant een RFID-tag van een speler.
2. De prop stuurt de tag-UID + spelerstekst naar deze server (`POST /chat`).
3. De server zoekt de persona op uit `personas.json`, filtert geheimen op basis van wat de prop mag weten, en bouwt een karakterprompt.
4. Ollama genereert een antwoord in karakter.
5. De prop spreekt of toont het antwoord.

## Onderdelen

| Bestand | Functie |
|---|---|
| `brain_server.py` | Centrale Flask-server, draait op de 3060-PC naast Ollama |
| `prop_config.py` | Configuratie per prop (model, zichtbaarheid, systeemprompt) |
| `chems.py` | Chems-database — beïnvloedt Thijs' stemming en gedrag |
| `personas.json` | Alle spelerspersonages met gelaagde geheimen |
| `gm_control.html` | GM-tool: events activeren, chems toedienen, logs bekijken |
| `freeradical.html` | Interface voor de FreeRadical-prop |
| `scan_tags.py` | RFID-scanner script voor de Pi |
| `validate.py` | Valideer de structuur van `personas.json` |

## Installatie

```bash
pip install flask flask-cors requests
python brain_server.py
```

Vereist een lokaal draaiende [Ollama](https://ollama.ai)-instantie.

## Endpoints

| Endpoint | Methode | Beschrijving |
|---|---|---|
| `/chat` | POST | Verwerk een scan + spelerstekst → antwoord in karakter |
| `/persona/<uid>` | GET | Debug: gefilterde persona voor een UID |
| `/health` | GET | Serverstatus + Ollama bereikbaar? |
| `/props` | GET | Lijst van geconfigureerde props |

## Visibility-niveaus (personas.json)

- `public` — iedereen weet dit
- `inner_circle` — alleen de eigen kring (bijv. Rad Roaches)
- `sl_only` — alleen spelleiding; props weten dit niet
- `self_only` — alleen de persoon zelf (of de prop die die persona *is*)

## Nieuwe prop toevoegen

Voeg een entry toe in `prop_config.py`. Er is geen andere code nodig.
