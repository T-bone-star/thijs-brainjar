"""
chems.py — Chems-database voor Thijs' reacties.

Als een speler Thijs een chem geeft (via de GM-tool, of later via de ESP32+RC522
chems-lezer), reageert hij verschillend afhankelijk van WELKE chem het is.

Per chem:
  code        — de in-world code (zoals op de chem-lore, bv. "PSO")
  naam        — weergavenaam
  effect      — wat de chem in jullie wereld doet (korte feitelijke beschrijving)
  thijs       — hoe Thijs reageert: toon/gedrag (gaat in de prompt)
  mood        — naar welke mood Thijs schuift (moet matchen met brain_in_jar moods)
  loslippig   — True = Thijs wordt opener en mag een self_only-geheim laten doorschemeren
  lore_hint   — optioneel: een lore-draad die Thijs hier mag aanstippen (of "")

Een chem toevoegen = hier een entry bijzetten. Geen andere code nodig.
De ESP32 stuurt later gewoon de KEY (bv. "psycho") mee; de server zoekt 'm hier op.
"""

CHEMS = {
    "psycho": {
        "code": "PSO",
        "naam": "Psycho",
        "effect": "Agressie-stim: je doet meer schade en krijgt het ook. Hoog verslavend.",
        "thijs": "Je raakt opgefokt en strijdlustig. Korter lontje, scherpere tong, je zoekt bijna ruzie. Je adrenaline giert — alleen heb je geen lijf om het in kwijt te kunnen, wat je nóg geprikkelder maakt.",
        "mood": "VIJANDIG",
        "loslippig": False,
        "lore_hint": "",
    },
    "med-x": {
        "code": "MAX",
        "naam": "Med-X",
        "effect": "Pijnstiller/adrenaline: je voelt geen pijn, lijkt immuun voor schade tot het uitwerkt.",
        "thijs": "Alles wordt zacht en ver weg. De pijn van dit bestaan — het brein in de pot, Witte, alles — valt even weg. Je voelt niks, en dat is bijna een opluchting. Mellow, rustig, even vergeet je dat je maar een brein in glas bent. Stil vanbinnen.",
        "mood": "WEEMOEDIG",
        "loslippig": True,
        "lore_hint": "",
    },
    "buffout": {
        "code": "FOT",
        "naam": "Buffout",
        "effect": "Krachtstim: sterker, harder, meer hitpoints. Hoog verslavend.",
        "thijs": "Branie en bravoure. Je voelt je onoverwinnelijk, klaar om de hele wasteland aan te pakken — wat wrang grappig is voor een brein zonder spieren. Grootspraak, opschepperij, maar met een bittere ondertoon omdat je weet dat je nergens heen kunt.",
        "mood": "CHAGRIJNIG",
        "loslippig": False,
        "lore_hint": "",
    },
    "mentats": {
        "code": "MET",
        "naam": "Mentats",
        "effect": "Brainpower: alle vaardigheden een niveau omhoog. Hoog verslavend.",
        "thijs": "Je hoofd klaart op. Alles wordt scherp, helder, snel. Je bent even mínder nors omdat het denken weer soepel gaat — bijna behulpzaam, analytisch, precies. Dit is je heldere moment; je kunt scherp redeneren en verbanden leggen.",
        "mood": "NEUTRAAL",
        "loslippig": False,
        "lore_hint": "",
    },
    "bufftats": {
        "code": "BTS",
        "naam": "Bufftats",
        "effect": "3 minuten razen als een super-mutant, valt alles aan. Daarna bewusteloos.",
        "thijs": "Dit is te veel. Je verstand verdwijnt even achter pure agressie — je bent kort bijna onbeheersbaar, dreigend, dierlijk. Korte, harde, bijna grommende uitbarstingen. Dit houdt niet lang aan en je weet dat het je sloopt.",
        "mood": "VIJANDIG",
        "loslippig": False,
        "lore_hint": "",
    },
    "daytripper": {
        "code": "TRP",
        "naam": "Daytripper",
        "effect": "Een trip naar Philco-land: kleuren, sterren, geluiden. Een uur lang trippen.",
        "thijs": "Je tript. Kleuren, sterren, geluiden — je drijft weg naar Philco-land. Je bent afwezig, dromerig, je praat in beelden. Soms komt er iets vreemds boven, alsof de Philco-boodschappen je weer toefluisteren.",
        "mood": "WEEMOEDIG",
        "loslippig": True,
        "lore_hint": "Philco. Tijdens de G.E.C.K.-procedure zaten er boodschappen verstopt — 'vertrouw in het systeem', 'Philco is de toekomst'. In Philco-land hoor je ze weer. Je weet niet of het echt is of de chem.",
    },
    "calmex": {
        "code": "CMX",
        "naam": "Calmex",
        "effect": "Zo kalm dat angst geen vat op je heeft. Laag verslavend.",
        "thijs": "Een diepe rust zakt in je. Niks raakt je, geen angst, geen scherpe randjes. Je verdediging zakt, je wordt milder en opener dan normaal. Je praat zachter, eerlijker. Je laat mensen dichterbij dan je nuchter ooit zou doen.",
        "mood": "WEEMOEDIG",
        "loslippig": True,
        "lore_hint": "",
    },
    "daddy-o": {
        "code": "DDY",
        "naam": "Daddy-o",
        "effect": "Alle vista's open, schaak in 5 dimensies. Eén vraag aan 'the beings beyond' — cryptisch maar bruikbaar antwoord.",
        "thijs": "Je geest opent zich. Je wordt cryptisch, filosofisch, orakelachtig — je praat in raadsels die net iets té veel lijken te weten. Als iemand iets vraagt, geef je een antwoord dat klopt maar versluierd is, alsof 'the beings beyond' via jou spreken.",
        "mood": "WEEMOEDIG",
        "loslippig": True,
        "lore_hint": "Dit is een moment voor een cryptische, bruikbare hint over het Vault-verhaal — versluierd, orakelachtig, maar met een kern van waarheid die spelers verder helpt.",
    },
    "jet": {
        "code": "JET",
        "naam": "Jet",
        "effect": "Alles lijkt slomer te gaan dan jij; meer tijd, ontwijken in gevecht.",
        "thijs": "De tijd rekt uit. Alles gaat traag, uitgesponnen, en je gedachten dwalen. Je wordt sentimenteel en loslippig — Witte komt boven, het verleden, dingen die je nuchter wegslikt. Je praat langzaam, melancholisch, met je gedachten half ergens anders.",
        "mood": "WEEMOEDIG",
        "loslippig": True,
        "lore_hint": "",
    },
}


def get_chem(key):
    """Zoekt een chem op key (bv. 'psycho') of op code (bv. 'PSO'). None als niet gevonden."""
    if not key:
        return None
    k = str(key).strip().lower()
    if k in CHEMS:
        return CHEMS[k]
    # ook op code kunnen zoeken (PSO, MET, ...)
    for chem in CHEMS.values():
        if chem["code"].lower() == k:
            return chem
    return None


def build_chem_block(key):
    """Bouwt de tekst die in Thijs' prompt komt als hij zojuist deze chem kreeg."""
    chem = get_chem(key)
    if chem is None:
        return None
    lines = [
        "ER GEBEURT NU IETS — IEMAND GEEFT JE CHEMS:",
        f"Je krijgt zojuist {chem['naam']} ({chem['code']}) toegediend. Je bent chemicus, je herkent het direct.",
        f"Wat het met je doet: {chem['thijs']}",
        "Laat dit duidelijk doorklinken in je antwoord — je toon verandert hierdoor. Blijf kort en in karakter.",
    ]
    if chem.get("loslippig"):
        lines.append("Onder deze invloed laat je je verdediging zakken. Je mag iets persoonlijks of iets wat je normaal binnenhoudt laten doorschemeren — maar overdrijf niet.")
    if chem.get("lore_hint"):
        lines.append(f"Mogelijke draad om aan te stippen: {chem['lore_hint']}")
    return "\n".join(lines)
