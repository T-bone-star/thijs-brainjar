"""
brain_server.py — Centrale "brain server" voor de Vault 25-props.

Draait op de 3060-PC, naast Ollama. De Pi-props (Thijs, FreeRadical, ...) sturen
hierheen een scan + spelerstekst; de server zoekt de persona op, filtert op wat
die prop mag weten, bouwt de karakterprompt en vraagt Ollama om een antwoord.

Start:
    pip install flask flask-cors requests --break-system-packages
    python brain_server.py

Endpoints:
    POST /chat            {prop_id, uid, text, [history]}  -> {reply, persona_naam, mood?}
    GET  /persona/<uid>?prop_id=thijs                      -> gefilterde persona (debug)
    GET  /health                                           -> status + ollama bereikbaar?
    GET  /props                                            -> lijst geconfigureerde props
"""

import json
import os
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

from prop_config import PROPS, DEFAULT_PROP, WERELD_LORE
from chems import build_chem_block, get_chem, CHEMS

# ─── EVENT-STATE (in geheugen) ────────────────────────────────────────────────
# Per prop een actieve situatie. Twee soorten:
#   - "blijvend"  : blijft actief tot je 'm wist (FreeRadical-aanvallen).
#   - "eenmalig"  : wordt in HET EERSTVOLGENDE antwoord meegegeven en dooft daarna
#                   automatisch (Thijs-chems).
# Vorm: _events[prop_id] = {"text": "...", "once": True/False}
_events = {}
_events_lock = __import__("threading").Lock()


def set_event(prop_id, text, once):
    with _events_lock:
        _events[prop_id] = {"text": text, "once": once}


def clear_event(prop_id):
    with _events_lock:
        _events.pop(prop_id, None)


def take_event(prop_id):
    """Geeft de actieve event-tekst voor deze prop terug (of None).
    Als de event 'eenmalig' is, wordt hij hierna gewist (dooft na gebruik)."""
    with _events_lock:
        ev = _events.get(prop_id)
        if not ev:
            return None
        if ev["once"]:
            _events.pop(prop_id, None)
        return ev["text"]


# ─── GESPREKSLOG (geheugen per speler, + live meekijken voor de GM) ───────────
import time as _time
import threading as _threading

LOG_PATH = Path(os.environ.get("LOG_PATH", "gesprekslog.json"))
HISTORY_TURNS = int(os.environ.get("HISTORY_TURNS", "7"))  # hoeveel beurten meesturen
_log = []            # lijst van {ts, prop_id, uid, naam, speler, antwoord}
_log_lock = _threading.Lock()


def _load_log():
    global _log
    try:
        with LOG_PATH.open(encoding="utf-8") as f:
            _log = json.load(f)
        print(f"✓ gesprekslog geladen: {len(_log)} regels")
    except (FileNotFoundError, json.JSONDecodeError):
        _log = []


def _save_log():
    # schrijf compact; bij een groot log alleen de laatste 2000 regels bewaren
    try:
        with LOG_PATH.open("w", encoding="utf-8") as f:
            json.dump(_log[-2000:], f, ensure_ascii=False)
    except OSError as e:
        print(f"[log] kon niet opslaan: {e}")


def log_turn(prop_id, uid, naam, speler, antwoord):
    """Sla één beurt op (speler + antwoord) en bewaar naar schijf."""
    with _log_lock:
        _log.append({
            "ts": _time.time(),
            "prop_id": prop_id,
            "uid": uid,
            "naam": naam,
            "speler": speler,
            "antwoord": antwoord,
        })
        _save_log()


def get_history(prop_id, uid, turns=HISTORY_TURNS):
    """Haalt de laatste `turns` beurten met deze speler bij deze prop op,
    als messages-lijst voor het model: [{role:user},{role:assistant},...]."""
    if not uid:
        return []
    with _log_lock:
        rel = [r for r in _log if r["uid"] == uid and r["prop_id"] == prop_id]
    rel = rel[-turns:]
    msgs = []
    for r in rel:
        msgs.append({"role": "user", "content": r["speler"]})
        msgs.append({"role": "assistant", "content": r["antwoord"]})
    return msgs


# ─── SYSTEEMSTATUS: ONDERHOUD & DREIGINGEN (per prop, op schijf bewaard) ───────
# Voor FreeRadical (en evt. andere props) houden we bij wat er aan onderhoud
# openstaat en welke dreigingen actief zijn. De GM-tool beheert dit via endpoints;
# de Pi-display haalt het op en toont het op het dashboard. Bewaard op schijf,
# dus het overleeft een herstart van de server.
STATE_PATH = Path(os.environ.get("STATE_PATH", "vault_state.json"))
# Vorm: _state[prop_id] = {"maintenance": [ {id,label,severity,status,desc?}, ... ],
#                          "threats":     [ {id,label,severity,desc?}, ... ]}
_state = {}
_state_lock = _threading.Lock()


def _load_state():
    global _state
    try:
        with STATE_PATH.open(encoding="utf-8") as f:
            _state = json.load(f)
        print(f"✓ vault_state geladen: {sum(len(v.get('maintenance', [])) + len(v.get('threats', [])) for v in _state.values())} items")
    except (FileNotFoundError, json.JSONDecodeError):
        _state = {}


def _save_state():
    try:
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(_state, f, ensure_ascii=False)
    except OSError as e:
        print(f"[state] kon niet opslaan: {e}")


def _prop_state(prop_id):
    """Geeft (en maakt zo nodig) het state-blok voor een prop. Niet thread-safe op zichzelf;
    aanroepen binnen _state_lock."""
    blk = _state.get(prop_id)
    if blk is None:
        blk = {"maintenance": [], "threats": []}
        _state[prop_id] = blk
    blk.setdefault("maintenance", [])
    blk.setdefault("threats", [])
    return blk


def _upsert(lst, item):
    """Voeg item toe of werk bestaand item met hetzelfde id bij. Retourneert de lijst."""
    iid = item.get("id")
    for i, existing in enumerate(lst):
        if existing.get("id") == iid:
            lst[i] = item
            return lst
    lst.append(item)
    return lst


def get_status_block(prop_id):
    """Bouwt een korte tekst met openstaand onderhoud + actieve dreigingen voor de prompt.
    Geeft '' als er niets is. Stuurt OOK FreeRadical's toon op basis van de ernst,
    zodat hij gespannen klinkt bij dreiging en mopperig bij achterstallig onderhoud."""
    with _state_lock:
        blk = _state.get(prop_id)
        if not blk:
            return ""
        maint = [m for m in blk.get("maintenance", []) if m.get("status") != "done"]
        threats = list(blk.get("threats", []))
    if not maint and not threats:
        return ""
    sev_nl = {"critical": "KRITIEK", "high": "HOOG", "medium": "MIDDEL", "low": "LAAG"}
    st_nl = {"pending": "open", "progress": "in uitvoering", "done": "klaar"}
    sev_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    lines = ["JOUW HUIDIGE SYSTEEMSTATUS (gebruik dit feitelijk; verzin er niets bij):"]
    if maint:
        lines.append("Openstaand onderhoud:")
        for m in maint:
            sev = sev_nl.get(m.get("severity"), "LAAG")
            stt = st_nl.get(m.get("status"), "open")
            extra = f" — {m['desc']}" if m.get("desc") else ""
            lines.append(f"- {m.get('label','?')} ({sev}, {stt}){extra}")
    else:
        lines.append("Openstaand onderhoud: geen.")
    if threats:
        lines.append("Actieve dreigingen:")
        for t in threats:
            sev = sev_nl.get(t.get("severity"), "MIDDEL")
            extra = f" — {t['desc']}" if t.get("desc") else ""
            lines.append(f"- {t.get('label','?')} ({sev}){extra}")
    else:
        lines.append("Actieve dreigingen: geen.")

    # ── TOON-STURING op basis van de ernst van wat er speelt ──
    zwaarste_dreiging = max((sev_rank.get(t.get("severity"), 2) for t in threats), default=0)
    zwaarste_onderhoud = max((sev_rank.get(m.get("severity"), 1) for m in maint), default=0)

    lines.append("")
    lines.append("LAAT DIT JE TOON BEPALEN (heel belangrijk):")
    if zwaarste_dreiging >= 4:
        lines.append("Er is een KRITIEKE dreiging. Je bent gespannen, urgent en direct. Laat de DJ-grappen vallen. "
                     "Dring aan dat bewoners NU handelen. Je beschermdrang staat op scherp — dit is jouw vault en jouw mensen.")
    elif zwaarste_dreiging == 3:
        lines.append("Er is een serieuze (HOGE) dreiging. Je bent alert en bezorgd, je spoort bewoners aan in actie te komen, "
                     "maar je verliest je hoofd niet. Toon dat je het serieus neemt.")
    elif zwaarste_dreiging == 2:
        lines.append("Er is een dreiging van gemiddeld niveau. Je bent waakzaam en houdt het in de gaten, "
                     "maar nog niet in paniek. Een gespannen ondertoon onder je gewone stem.")
    elif zwaarste_dreiging == 1:
        lines.append("Er is een lichte dreiging. Je noemt het terloops, niet alarmerend, maar je houdt het scherp in de gaten.")
    elif zwaarste_onderhoud >= 3:
        lines.append("Geen dreiging, maar er ligt zwaar onderhoud te lang te wachten. Je bent geïrriteerd en sarcastisch hierover — "
                     "een passief-agressieve intercom-stem. 'Vast heel fijn voor de bewoners en hun kinderen dat niemand zich erom bekommert.'")
    elif zwaarste_onderhoud >= 1:
        lines.append("Geen dreiging, alleen wat openstaand onderhoud. Je mag er licht mopperend of droogjes naar verwijzen als het past, "
                     "maar je blijft in de basis je gewone, ontspannen radio-zelf.")
    return "\n".join(lines)


# ─── Config ─────────────────────────────────────────────────────────────────
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
PERSONAS_PATH = Path(os.environ.get("PERSONAS_PATH", "personas.json"))
PORT = int(os.environ.get("BRAIN_PORT", "5025"))

app = Flask(__name__)
CORS(app)  # Pi-browsers mogen erbij


# ─── Persona's laden (met hot-reload bij wijziging) ───────────────────────────
_personas_cache = {"mtime": 0, "data": {}}


def load_personas():
    """Laadt personas.json; herlaadt automatisch als het bestand gewijzigd is."""
    try:
        mtime = PERSONAS_PATH.stat().st_mtime
    except FileNotFoundError:
        print(f"⚠  {PERSONAS_PATH} niet gevonden — start met lege set.")
        return {}
    if mtime != _personas_cache["mtime"]:
        with PERSONAS_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
        _personas_cache["data"] = raw.get("personas", {})
        _personas_cache["mtime"] = mtime
        print(f"✓ personas.json geladen: {len(_personas_cache['data'])} persona's")
    return _personas_cache["data"]


def find_persona_by_uid(uid):
    """Zoekt een persona op UID. Retourneert (key, persona) of (None, None)."""
    if not uid:
        return None, None
    uid_norm = str(uid).strip().upper()
    for key, p in load_personas().items():
        puid = p.get("uid")
        if puid and str(puid).strip().upper() == uid_norm:
            return key, p
    return None, None


# ─── Visibility-filter: bouw het persona-blok voor de prompt ──────────────────
def build_persona_block(prop_id, persona_key, persona):
    """
    Bouwt de tekst die in de prompt komt over de bezoeker.
    Respecteert de visibility-regels per prop:
      - sees: lijst niveaus die deze prop mag zien (bv. ['public','inner_circle'])
      - self_only: alleen zichtbaar als dit de eigen persona van de prop is
    """
    if persona is None:
        return ("DE BEZOEKER:\n"
                "Er staat iemand voor je, maar je herkent hem/haar niet "
                "(geen registratie gevonden). Behandel als een vreemde — "
                "voorzichtig, niet meteen vertrouwen.")

    prop = PROPS.get(prop_id, PROPS[DEFAULT_PROP])
    sees = set(prop.get("sees", ["public"]))
    is_self = (prop.get("persona_self") == persona_key)
    # Eigen geheimen mag de prop wél zien
    if is_self:
        sees.add("self_only")

    def visible(item):
        return item.get("visibility", "public") in sees

    lines = []
    naam = persona.get("naam", "onbekend")
    ach = persona.get("achtergrond", {})

    if is_self:
        lines.append("DE BEZOEKER:\nIemand scant je eigen oude registratie. Dat ben jij, vroeger.")
    else:
        lines.append(f"DE BEZOEKER: {naam}")
        rol = persona.get("huidige_rol", "")
        aff = persona.get("affiliatie", "")
        meta = ", ".join(x for x in [rol, (f"hoort bij {aff}" if aff else "")] if x)
        if meta:
            lines.append(f"({meta})")
        if ach.get("korte_samenvatting"):
            lines.append(ach["korte_samenvatting"])

    # Relaties die deze prop mag zien
    rels = [r for r in persona.get("relations", []) if visible(r)]
    if rels:
        lines.append("\nWat je over deze persoon en zijn/haar relaties weet:")
        for r in rels:
            tgt = r.get("target", "?")
            summ = r.get("public_summary") or r.get("type", "")
            lines.append(f"- {tgt}: {summ}")

    # Secrets die deze prop mag zien
    secs = [s for s in persona.get("secrets", []) if visible(s)]
    if secs:
        if is_self:
            lines.append("\nWat alleen jij weet:")
        else:
            lines.append("\nWat je (stilletjes) over deze persoon weet:")
        for s in secs:
            lines.append(f"- {s.get('content','')}")

    # Wat deze persona over anderen weet (alleen public-relevant voor de prop)
    knows = persona.get("knows_about_others", [])
    if knows and not is_self:
        # alleen meenemen als nuttig; we tonen het kort
        pass  # standaard niet injecteren — vaak SL-materiaal. Aanzetten kan later.

    lines.append("\nGebruik dit alleen als het natuurlijk in het gesprek past. "
                 "Verzin niets bij wat hier niet staat.")
    return "\n".join(lines)


# ─── Prompt samenstellen ──────────────────────────────────────────────────────
def build_system_prompt(prop_id, persona_key, persona, event_text=None):
    prop = PROPS.get(prop_id, PROPS[DEFAULT_PROP])
    persona_block = build_persona_block(prop_id, persona_key, persona)
    prompt = prop["system_prompt"].format(
        persona_block=persona_block,
        wereld_lore=WERELD_LORE,
    )
    # Actuele systeemstatus (onderhoud/dreigingen) — vooral voor FreeRadical.
    # Zo rapporteert de prop accuraat en verzint hij geen storingen.
    status_block = get_status_block(prop_id)
    if status_block:
        prompt += "\n\n=== " + status_block
    # Actieve situatie (aanval, chem, ...) er bovenop. Krijgt nadruk zodat het
    # model het zwaarder weegt dan de achtergrond.
    if event_text:
        prompt += (
            "\n\n=== ACTUELE SITUATIE (gebeurt NU — laat dit je antwoord sturen) ===\n"
            + event_text
        )
    return prompt


# ─── Ollama aanroepen ──────────────────────────────────────────────────────────
def call_ollama(model, system_prompt, history, user_text):
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "stream": False,
            "options": {
                "temperature": 0.85,
                "top_p": 0.95,
                "top_k": 64,
                "num_predict": 160,
                "stop": ["Speler:", "Player:", "User:", "Bezoeker:",
                          "```", "\nIn deze", "\nIn dit gesprek", "\nUitleg:",
                          "\nNB:", "\nNoot:", "\n(Noot", "\n(Bedenk", "\nLet op:",
                          "\nLaten we hopen", "\n FreeRadical", "\nFreeRadical,",
                          "\nFreeRadical:", "\n Thijs", "\nThijs:", "(Bedenk dat"],
            },
            "messages": messages,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    raw = (data.get("message", {}).get("content") or "").strip()
    return clean_reply(raw)


def clean_reply(text, max_sentences=4):
    """Knipt 'meta'-gelul weg dat kleine modellen er soms achteraan plakken,
    en kapt te lange antwoorden af op een hard maximum aantal zinnen.

    Zo ziet de speler alleen een kort, in-character antwoord.
    """
    if not text:
        return text
    # 0. Chat-template-tokens die het model soms lekt (<|user|>, <|assistant|>, ...).
    #    Alles VANAF zo'n token weg — daar begint vaak een neppe nieuwe beurt.
    import re as _re
    m = _re.search(r"<\|?\s*(user|assistant|system|im_start|im_end|end|endoftext)\s*\|?>", text, _re.I)
    if m:
        text = text[:m.start()]
    # losse restjes van zulke tokens hard verwijderen
    text = _re.sub(r"<\|?[a-z_]+\|?>", "", text, flags=_re.I)
    # 1. Alles vanaf een triple-backtick weg
    if "```" in text:
        text = text.split("```")[0]
    # 2. Alles vanaf een "meta"-fragment weg (model dat zijn eigen antwoord bespreekt
    #    of een toneelaanwijzing/naamlabel invoegt)
    meta_markers = [
        "\nIn deze interactie", "\nIn dit gesprek", "\nUitleg:", "\nNB:",
        "\nNoot:", "\n(Noot", "\n(Bedenk", "(Bedenk dat", "\nLet op:",
        "\nHier spreekt", "\nDe AI ", "\nLaten we hopen",
        "\nFreeRadical (", "\nFreeRadical,", "\nFreeRadical:", "\n FreeRadical",
        "\nThijs (", "\nThijs:", "\n Thijs", "\n[", "\n(",
    ]
    for m in meta_markers:
        idx = text.find(m)
        if idx != -1:
            text = text[:idx]
    text = text.strip()

    # 3. Emoji's en andere symbolen weghalen (modellen strooien ze er soms in;
    #    past niet bij Thijs/FreeRadical en de Vault-Tec-stijl).
    import re as _re
    text = _re.sub(
        "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
        "\U00002190-\U000021FF\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U0000200D]",
        "", text
    )
    text = _re.sub(r"[ \t]{2,}", " ", text).strip()

    # 4. Harde afkap op aantal zinnen (vangnet tegen breedsprakigheid).
    parts = _re.split(r'(?<=[.!?])\s+', text)
    if len(parts) > max_sentences:
        text = " ".join(parts[:max_sentences]).strip()
    return text


# Zinnen die verraden dat het model uit z'n rol brak (meta / "ik ben maar een AI").
_BREAK_SIGNALS = [
    "als ai", "als taalmodel", "taalmodel", "gesimuleerde omgeving",
    "virtuele simulatie", "hypothetische gebeurtenis", "geen toegang tot real",
    "geen toegang tot real-time", "binnen onze gesimuleerde", "ik ben een ai",
    "language model", "as an ai", "ik kan geen", "ik heb geen toegang",
    "dit scenario", "in dit scenario", "fictieve situatie",
]


def broke_character(text):
    """True als het antwoord tekenen van rol-breuk vertoont (mag niet naar de speler)."""
    if not text or len(text.strip()) < 2:
        return True
    low = text.lower()
    return any(sig in low for sig in _BREAK_SIGNALS)


# Veilige, vaste in-character noodantwoorden per prop. Gebruikt als het model
# uit z'n rol breekt of onbruikbaar antwoordt. Kort en altijd toepasbaar.
FALLBACK_REPLIES = {
    "thijs": [
        "...zeg dat nog eens. Ik was er even niet bij.",
        "Hm. Vraag het me anders.",
        "Mijn hoofd kraakt. Probeer het nog eens.",
    ],
    "freeradical": [
        "Ruis op de lijn, bewoner. Herhaal dat.",
        "Even een storing — zeg het nog eens, luisteraar.",
        "Mijn kanalen haperen. Wat zei je?",
    ],
}
# Als er een aanval (blijvende event) actief is, wil je bij rol-breuk juist
# de urgentie vasthouden i.p.v. "ruis op de lijn".
FALLBACK_UNDER_EVENT = {
    "freeradical": "Bewoners! Geen tijd voor uitleg — er is een aanval gaande. Kom in actie!",
    "thijs": "...er is iets mis. Let op je omgeving.",
}


def pick_fallback(prop_id, event_active):
    import random
    if event_active and prop_id in FALLBACK_UNDER_EVENT:
        return FALLBACK_UNDER_EVENT[prop_id]
    pool = FALLBACK_REPLIES.get(prop_id) or FALLBACK_REPLIES["thijs"]
    return random.choice(pool)


# ─── Endpoints ─────────────────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", DEFAULT_PROP)
    uid = body.get("uid")
    text = (body.get("text") or "").strip()

    if prop_id not in PROPS:
        prop_id = DEFAULT_PROP
    if not text:
        return jsonify({"error": "lege tekst"}), 400

    persona_key, persona = find_persona_by_uid(uid)
    # Geschiedenis met deze speler bij deze prop — de server onthoudt het zelf,
    # zodat de prop kan refereren aan eerdere gesprekken ("jij weer, Betty").
    history = get_history(prop_id, uid)
    # Actieve situatie voor deze prop (aanval blijft staan; chem dooft na dit antwoord)
    event_text = take_event(prop_id)
    # Onthoud of er een blijvende situatie (aanval) actief is, voor de fallback-keuze.
    with _events_lock:
        event_active = prop_id in _events
    event_active = event_active or bool(event_text)
    system_prompt = build_system_prompt(prop_id, persona_key, persona, event_text)

    try:
        reply = call_ollama(PROPS[prop_id]["model"], system_prompt, history, text)
        # Brak het model uit z'n rol? Eén keer opnieuw proberen; lukt het weer niet,
        # gebruik een veilig vast in-character antwoord.
        if broke_character(reply):
            reply = call_ollama(PROPS[prop_id]["model"], system_prompt, history, text)
            if broke_character(reply):
                reply = pick_fallback(prop_id, event_active)
    except requests.RequestException as e:
        return jsonify({"error": f"ollama onbereikbaar: {e}", "offline": True}), 503

    # Beurt opslaan (geheugen + live meekijken voor de GM)
    naam = persona.get("naam") if persona else None
    log_turn(prop_id, uid, naam, text, reply)

    return jsonify({
        "reply": reply,
        "prop_id": prop_id,
        "persona_naam": naam,
        "persona_herkend": persona is not None,
    })


@app.route("/persona/<uid>", methods=["GET"])
def persona_debug(uid):
    prop_id = request.args.get("prop_id", DEFAULT_PROP)
    if prop_id not in PROPS:
        prop_id = DEFAULT_PROP
    key, persona = find_persona_by_uid(uid)
    if persona is None:
        return jsonify({"herkend": False, "uid": uid}), 404
    return jsonify({
        "herkend": True,
        "key": key,
        "naam": persona.get("naam"),
        "prop_id": prop_id,
        "persona_block": build_persona_block(prop_id, key, persona),
    })


@app.route("/health", methods=["GET"])
def health():
    ollama_ok = False
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        ollama_ok = r.ok
    except requests.RequestException:
        pass
    return jsonify({
        "status": "ok",
        "ollama_bereikbaar": ollama_ok,
        "personas_geladen": len(load_personas()),
        "props": list(PROPS.keys()),
    })


@app.route("/props", methods=["GET"])
def props():
    return jsonify({
        pid: {"naam": p["naam"], "model": p["model"], "sees": p["sees"]}
        for pid, p in PROPS.items()
    })


# ─── EVENT-ENDPOINTS (voor de GM-tool) ────────────────────────────────────────
@app.route("/event", methods=["POST"])
def event_set():
    """Zet een BLIJVENDE situatie aan (bv. FreeRadical-aanval).
    Body: {prop_id, text}. Blijft actief tot /event/clear."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", DEFAULT_PROP)
    text = (body.get("text") or "").strip()
    if prop_id not in PROPS:
        return jsonify({"error": "onbekende prop"}), 400
    if not text:
        return jsonify({"error": "lege tekst"}), 400
    set_event(prop_id, text, once=False)
    return jsonify({"ok": True, "prop_id": prop_id, "active": text})


@app.route("/event/clear", methods=["POST"])
def event_clear():
    """Zet de situatie van een prop weer uit. Body: {prop_id}."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", DEFAULT_PROP)
    clear_event(prop_id)
    return jsonify({"ok": True, "prop_id": prop_id, "active": None})


@app.route("/event", methods=["GET"])
def event_get():
    """Toont de actieve situatie per prop (debug / GM-overzicht)."""
    with _events_lock:
        return jsonify({pid: ev for pid, ev in _events.items()})


@app.route("/chem", methods=["POST"])
def chem_give():
    """EENMALIGE chem-trigger voor een prop (standaard Thijs).
    Body: {prop_id?, chem}. 'chem' is een key/code uit chems.py (bv. 'psycho').
    Wordt in het EERSTVOLGENDE antwoord meegegeven en dooft daarna."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", "thijs")
    chem_key = body.get("chem", "")
    if prop_id not in PROPS:
        return jsonify({"error": "onbekende prop"}), 400
    block = build_chem_block(chem_key)
    if block is None:
        return jsonify({"error": f"onbekende chem '{chem_key}'",
                        "beschikbaar": list(CHEMS.keys())}), 400
    set_event(prop_id, block, once=True)
    chem = get_chem(chem_key)
    return jsonify({"ok": True, "prop_id": prop_id,
                    "chem": chem["naam"], "mood": chem["mood"]})


@app.route("/chems", methods=["GET"])
def chems_list():
    """Lijst van beschikbare chems (voor de GM-tool knoppen)."""
    return jsonify({
        key: {"naam": c["naam"], "code": c["code"], "mood": c["mood"]}
        for key, c in CHEMS.items()
    })


# ─── SYSTEEMSTATUS-ENDPOINTS: ONDERHOUD & DREIGINGEN (voor GM-tool + Pi) ──────
@app.route("/maintenance", methods=["GET"])
def maintenance_list():
    """Onderhoudslijst voor een prop. Query: ?prop_id=freeradical."""
    prop_id = request.args.get("prop_id", "freeradical")
    with _state_lock:
        blk = _state.get(prop_id) or {}
        return jsonify(list(blk.get("maintenance", [])))


@app.route("/maintenance", methods=["POST"])
def maintenance_upsert():
    """Voeg onderhoud toe of werk het bij (op id).
    Body: {prop_id, id, label, severity, status, desc?}."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", "freeradical")
    if prop_id not in PROPS:
        return jsonify({"error": "onbekende prop"}), 400
    label = (body.get("label") or "").strip()
    if not label:
        return jsonify({"error": "lege label"}), 400
    item = {
        "id": str(body.get("id") or f"{_time.time()}"),
        "label": label,
        "severity": body.get("severity", "low"),
        "status": body.get("status", "pending"),
    }
    if body.get("desc"):
        item["desc"] = str(body["desc"]).strip()
    with _state_lock:
        blk = _prop_state(prop_id)
        _upsert(blk["maintenance"], item)
        _save_state()
    return jsonify({"ok": True, "item": item})


@app.route("/maintenance/delete", methods=["POST"])
def maintenance_delete():
    """Verwijder een onderhoudsitem. Body: {prop_id, id}."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", "freeradical")
    iid = str(body.get("id", ""))
    with _state_lock:
        blk = _prop_state(prop_id)
        before = len(blk["maintenance"])
        blk["maintenance"] = [m for m in blk["maintenance"] if str(m.get("id")) != iid]
        _save_state()
        removed = before - len(blk["maintenance"])
    return jsonify({"ok": True, "verwijderd": removed})


@app.route("/threat", methods=["GET"])
def threat_list():
    """Dreigingslijst voor een prop. Query: ?prop_id=freeradical."""
    prop_id = request.args.get("prop_id", "freeradical")
    with _state_lock:
        blk = _state.get(prop_id) or {}
        return jsonify(list(blk.get("threats", [])))


@app.route("/threat", methods=["POST"])
def threat_upsert():
    """Voeg een dreiging toe of werk die bij (op id).
    Body: {prop_id, id, label, severity, desc?}."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", "freeradical")
    if prop_id not in PROPS:
        return jsonify({"error": "onbekende prop"}), 400
    label = (body.get("label") or "").strip()
    if not label:
        return jsonify({"error": "lege label"}), 400
    item = {
        "id": str(body.get("id") or f"{_time.time()}"),
        "label": label,
        "severity": body.get("severity", "medium"),
    }
    if body.get("desc"):
        item["desc"] = str(body["desc"]).strip()
    with _state_lock:
        blk = _prop_state(prop_id)
        _upsert(blk["threats"], item)
        _save_state()
    return jsonify({"ok": True, "item": item})


@app.route("/threat/delete", methods=["POST"])
def threat_delete():
    """Verwijder een dreiging. Body: {prop_id, id}."""
    body = request.get_json(force=True) or {}
    prop_id = body.get("prop_id", "freeradical")
    iid = str(body.get("id", ""))
    with _state_lock:
        blk = _prop_state(prop_id)
        before = len(blk["threats"])
        blk["threats"] = [t for t in blk["threats"] if str(t.get("id")) != iid]
        _save_state()
        removed = before - len(blk["threats"])
    return jsonify({"ok": True, "verwijderd": removed})


@app.route("/status", methods=["GET"])
def status_get():
    """Volledige systeemstatus van een prop (onderhoud + dreigingen).
    Query: ?prop_id=freeradical. Handig voor de Pi-display in één call."""
    prop_id = request.args.get("prop_id", "freeradical")
    with _state_lock:
        blk = _state.get(prop_id) or {"maintenance": [], "threats": []}
        return jsonify({
            "maintenance": list(blk.get("maintenance", [])),
            "threats": list(blk.get("threats", [])),
        })


# ─── LOG-ENDPOINTS (live meekijken + geschiedenis voor de GM) ─────────────────
@app.route("/log", methods=["GET"])
def log_recent():
    """Recente gesprekken voor live meekijken.
    Query: ?prop_id=thijs (optioneel filter), ?since=<ts> (alleen nieuwer),
           ?limit=50 (max aantal)."""
    prop_id = request.args.get("prop_id")
    since = request.args.get("since", type=float)
    limit = request.args.get("limit", default=50, type=int)
    with _log_lock:
        rows = list(_log)
    if prop_id:
        rows = [r for r in rows if r["prop_id"] == prop_id]
    if since is not None:
        rows = [r for r in rows if r["ts"] > since]
    rows = rows[-limit:]
    return jsonify(rows)


@app.route("/history/<uid>", methods=["GET"])
def history_for_uid(uid):
    """Volledige geschiedenis met één speler (optioneel ?prop_id=...)."""
    prop_id = request.args.get("prop_id")
    with _log_lock:
        rows = [r for r in _log if r["uid"] == uid]
    if prop_id:
        rows = [r for r in rows if r["prop_id"] == prop_id]
    return jsonify(rows)


@app.route("/log/clear", methods=["POST"])
def log_clear():
    """Wist het hele gesprekslog (bv. bij de start van een nieuw event)."""
    global _log
    with _log_lock:
        _log = []
        _save_log()
    return jsonify({"ok": True})


if __name__ == "__main__":
    load_personas()
    _load_log()
    _load_state()
    print(f"🧠 Brain server start op poort {PORT}")
    print(f"   Ollama: {OLLAMA_HOST}")
    print(f"   Personas: {PERSONAS_PATH.resolve()}")
    print(f"   Log: {LOG_PATH.resolve()}  (laatste {HISTORY_TURNS} beurten als geheugen)")
    print(f"   State: {STATE_PATH.resolve()}  (onderhoud/dreigingen)")
    print(f"   Props: {', '.join(PROPS.keys())}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
