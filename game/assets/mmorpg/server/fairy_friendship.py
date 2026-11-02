"""Moonpetal Inn fairy friendship (0–100) and the house secret tease.

Talking about topics and offering unique compliments raises friendship. When
every inn fairy is at 100, the house trusts you and reveals a sealed secret
beneath the fairy village (dungeon content lands later — corrupted fairies).
"""
from __future__ import annotations

import json

MAX = 100
TOPIC_GAIN = 10
COMPLIMENT_GAIN = 12
GREET_GAIN = 4

FAIRY_IDS = (
    "selune", "ivria", "maelis", "aerin", "rhosyn",
    "tamsin_moon", "kaede", "bryony", "nyx",
)
FAIRY_NAMES = {
    "selune": "Selune", "ivria": "Ivria", "maelis": "Maelis", "aerin": "Aerin",
    "rhosyn": "Rhosyn", "tamsin_moon": "Tamsin", "kaede": "Kaede",
    "bryony": "Bryony", "nyx": "Nyx",
}
NAME_TO_ID = {v: k for k, v in FAIRY_NAMES.items()}

TOPICS = ("moon", "fae", "throne", "rumours")

# Five unique compliments per fairy — each awards COMPLIMENT_GAIN once.
# 4 topics × 10 + 5 compliments × 12 = 100.
COMPLIMENTS = {
    "selune": [
        ("grace", "You carry this house like moonlight carries water — quiet, certain, and impossible to refuse."),
        ("welcome", "No one else makes a stranger feel as if the door was waiting only for them."),
        ("wisdom", "Crowns come and go. Your patience with them is what keeps this place standing."),
        ("table", "The way you set a table says more about a realm than any speech from a throne."),
        ("trust", "If the Moon Petal has a heart, it beats wherever you are standing."),
    ],
    "ivria": [
        ("pages", "You treat pages like living things. Most people treat them like kindling."),
        ("memory", "Without you, half the realm's truth would be rumour and the other half would be ash."),
        ("candle", "Even your candles seem to burn more carefully than anyone else's."),
        ("ink", "Your ink remembers what kings prefer to forget. That is a kind of courage."),
        ("shelf", "I would trust your shelves with a secret before I trusted a vault."),
    ],
    "maelis": [
        ("bloom", "The blooms lean toward you as if they know their keeper by the sound of her step."),
        ("dew", "You speak of dew like most people speak of gold — and you are right to."),
        ("green", "Crownfall would be greyer without your stubborn green."),
        ("bite", "Even the blue ones listen when you scold them. I would too."),
        ("root", "You keep what grows alive. That is rarer than any jewel in this inn."),
    ],
    "aerin": [
        ("watch", "Nothing reaches this street without you seeing it first. That is a gift, not a habit."),
        ("sky", "You read the sky the way others read maps — and you never get lost."),
        ("warning", "Your warnings arrive before danger does. I sleep better knowing that."),
        ("balcony", "From your balcony the whole realm looks honest, even when it isn't."),
        ("edge", "You keep the edge of this house sharp. Soft houses don't last."),
    ],
    "rhosyn": [
        ("song", "Your music finds the places words can't reach and sits there until they heal."),
        ("string", "One note from you and the stairs remember why they were built."),
        ("history", "You keep wars alive as songs so no one has to fight them twice."),
        ("true", "You gave a king the truest song instead of the happiest. That took steel."),
        ("hum", "Even the dark behaves when your music is in the air."),
    ],
    "tamsin_moon": [
        ("pour", "You pour a drink like it matters who receives it. That is rarer than moonwine."),
        ("ledger", "Merchants fear your ledgers for good reason — and travellers love you for the same one."),
        ("honest", "You suggested honest on my first night. I've trusted your judgment since."),
        ("debt", "You hold an old royal debt and never lean on it. That is power used gently."),
        ("bar", "The Moon Bar feels safer than most castles. That is your doing."),
    ],
    "nyx": [
        ("hearth", "Your fire warms more than hands. It reminds people they are allowed to rest."),
        ("dark", "You walk the dark of the moon without becoming it. That is a hard road."),
        ("sister", "You warn travellers about the deep sisters. Kindness dressed as caution."),
        ("light", "Keep a light lit, you said. I have. It helps."),
        ("ash", "Even ash listens when you speak. The hearth chose well."),
    ],
    "kaede": [
        ("letter", "Your letters arrive where swords can't. That is a quieter kind of victory."),
        ("wax", "Moon-wax and a careful hand — half the court survives because of you."),
        ("price", "You quote lords different prices and somehow everyone pays the right one."),
        ("secret", "You keep secrets the way gardens keep seeds: buried, watered, waiting."),
        ("shoulder", "Anyone who reads over your shoulder deserves what they get. Anyone who helps you deserves better."),
    ],
    "bryony": [
        ("crystal", "Your crystals tell the truth even when no one wants it. That is bravery in glass."),
        ("moonlight", "You bottle moonlight like other people bottle wine — and share it more freely."),
        ("fortune", "You saw me coming. I believe you. The crystals rarely lie to you."),
        ("chair", "Empty chairs and walking crowds — you named the realm's fear without flinching."),
        ("fun", "You keep a joke in your pocket even when the reading is grim. Thank you for that."),
    ],
}

# Longer topic replies (server-authoritative when friendship is tracked).
TOPIC_LINES = {
    "selune": {
        "moon": "The moon was not always alone. There were two, once — sisters in the same sky. The second fell the night the first king was crowned, and wherever its light struck, moon-petals still open. We built this inn on one of those scars. That is why the door finds you again.",
        "fae": "We are not your fairy tales, traveller. We were here before the roads were cut, and we will be here when the last crown rusts. We prefer to be guests in your stories because guests can leave — and return — on their own terms.",
        "throne": "Every ruler of Crownfall has drunk here once. Most never knew who poured. A few did, and those few either kept their promise to us… or found the petals would not open for them again.",
        "rumours": "Ask the others. Each of my girls hears a different thread. Together we hear the whole cloth. If you earn their trust — all of them — the house may tell you what we do not tell crowns.",
    },
    "ivria": {
        "moon": "Moon-phases decide which of our doors are open, and which histories are safe to read aloud. Learn the calendar and the world gets larger — or sharper. Some pages only turn under a waning light.",
        "fae": "Our names are contracts. Never give us yours lightly, and never take ours without a gift. Ink remembers debts longer than blood does.",
        "throne": "The chronicles say the Founder King won his crown by the sword. My quieter copy says he bought it — with a promise to the fae. Promises make better bindings than iron, until someone files them down.",
        "rumours": "A page walked out of this room once. The last person who read it wears a crown now. Pages that leave without leave tend to come back… changed.",
    },
    "maelis": {
        "moon": "Moonblooms only open under a full moon. Pick one at the wrong hour and it turns to ash in your hand — and something under the soil remembers you were greedy.",
        "fae": "Every one of us is bound to something that grows. Burn a forest and somewhere a fae forgets her own name. That is not poetry. That is bookkeeping.",
        "throne": "The king's men cut the Elderwood for warships last spring. Wood remembers axes. You will be hearing about that longer than the ships float.",
        "rumours": "Something digs under the old orchard at night. Not moles. Moles don't sing — and they don't leave petal-shaped holes that frost over by dawn.",
    },
    "aerin": {
        "moon": "From up here you can see the moon's reflection in every window in the glade. Count the dark ones. Those are the rooms that have stopped listening.",
        "fae": "We fly less than we used to. The sky over Crownfall has too many arrows in it, and too many watchers who think wings are invitations.",
        "throne": "Guards changed shifts at the castle twice tonight. Once is routine. Twice means someone is expecting a visitor who should not be named in a bright room.",
        "rumours": "A cloaked rider has visited the north gate each night this week. She never comes in. She leaves a single black petal on the stones and rides on.",
    },
    "rhosyn": {
        "moon": "There is a song that only works when the moon is full. Play it in the right place and the ground remembers what stood there — temple, tree, or grave. Play it wrong and the ground remembers you instead.",
        "fae": "Our music is how we keep our history. Lose a song and you lose a war that already happened, which is somehow worse than losing one that hasn't.",
        "throne": "I played at the last coronation. The new king asked for a happy song. I gave him the truest one I had. He smiled anyway. That worried me more than if he had wept.",
        "rumours": "A bard in the Resting Ox has been singing one of our songs. Badly. And it is working. That should not be possible for mortal throats without a teacher — or a theft.",
    },
    "tamsin_moon": {
        "moon": "Moonwine is pressed only on the full moon. One glass and you dream of where you'll be in a year. Two and you dream of where you'll be in ten. Three and you stop dreaming of yourself at all — so I cut most folk off at one.",
        "fae": "Selune runs the house. I run the house's money. Guess which of us the merchants fear when the ledger comes out. Hint: it is not the hostess with the soft voice.",
        "throne": "The crown owes this inn a debt older than the treasury. We have never asked for it. Yet. Debts that old gather interest in strange coin.",
        "rumours": "Someone paid for a room upstairs in old royal coin — coin that was melted down a hundred years ago. The stamp was perfect. The metal sang when I bit it.",
    },
    "nyx": {
        "moon": "The dark of the moon is mine. When it vanishes, the old things under Crownfall stretch — under roads, under castles, under pretty inns with candlelight. Stretching is not the same as waking. Not yet.",
        "fae": "Not all fae drink in pretty inns. Some of my sisters chose the deep places when the second moon fell. Do not take their bargains. Do not follow their songs underground without a light you trust.",
        "throne": "The throne is carved from a tree that was alive when it was cut. It still dreams. Ask the king why he doesn't sleep. If he answers honestly, buy him a drink on me.",
        "rumours": "The miners have stopped going below the third floor after dark. They say they hear a heartbeat in the stone. Heartbeats underground are rarely good news for anyone standing above them.",
    },
    "kaede": {
        "moon": "Letters sealed with moon-wax can only be opened by the one they're meant for. Useful in a city of spies. Dangerous in a city of curious friends. I write both kinds.",
        "fae": "I write for half the court of Crownfall. They think I'm a scribe with neat handwriting. I let them. Handwriting is a wonderful place to hide a second meaning.",
        "throne": "Three lords wrote to me this month asking how much a crown costs. I quoted them all different prices. One paid. One fled. One is still counting coins and calling it strategy.",
        "rumours": "A duke has been writing love letters to someone dead twenty years. She writes back in a hand I taught her before she died. I have not decided whether that is comfort or a crime.",
    },
    "bryony": {
        "moon": "Each crystal holds a night of moonlight. Break one and you get a night back — memories, luck, or a warning, depending on how you break it. I've only ever broken two, and I still dream both nights.",
        "fae": "We age by moons, not years. I'm very young by that count. Selune is very, very not. The crystals like both of us for different reasons.",
        "throne": "Every crystal I read for the throne shows the same thing: an empty chair, and a lot of people walking toward it. I stopped telling them which people. They never thank me for accuracy.",
        "rumours": "Someone in this room is not a fae. I won't say who. It's funnier this way — and safer. The crystals twitch when I almost point.",
    },
}

SECRET_TEASE = (
    "The house trusts you now — every voice in it. Listen carefully.\n\n"
    "Beneath the fairy village, under roots older than the roads, there is a sealed hollow. "
    "We called it the Petaldeep once. It was a garden of quiet light.\n\n"
    "Something in it twisted. Sisters who went down to tend it came back wrong — "
    "petals blackened, songs that bite, smiles with too many edges. Corrupted fae. "
    "We sealed the mouth and told the village the orchard was only orchard.\n\n"
    "When the way is ready, the door will show itself to you near the old roots. "
    "Not yet. Earn nothing more tonight — only remember: the Petaldeep waits, "
    "and it will not wait kindly."
)

SECRET_HINT_PARTIAL = (
    "You are close. The house does not open its oldest door for a favourite — "
    "only for a guest every sister trusts. Speak with the others. Compliment them honestly. "
    "When every friendship here is full, we will tell you what grows under the village."
)


def ensure_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS moonpetal_friendship ("
        "player_id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')"
    )
    conn.commit()


def _blank():
    return {
        "friendship": {fid: 0 for fid in FAIRY_IDS},
        "topics_done": {fid: [] for fid in FAIRY_IDS},
        "compliments_done": {fid: [] for fid in FAIRY_IDS},
        "greeted": [],
        "secret_unlocked": False,
        "secret_told": False,
    }


def load(conn, pid):
    ensure_schema(conn)
    row = conn.execute(
        "SELECT data FROM moonpetal_friendship WHERE player_id = ?", (int(pid),)
    ).fetchone()
    try:
        d = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        d = {}
    base = _blank()
    base.update(d or {})
    fr = dict(base.get("friendship") or {})
    for fid in FAIRY_IDS:
        fr[fid] = max(0, min(MAX, int(fr.get(fid) or 0)))
    base["friendship"] = fr
    for key in ("topics_done", "compliments_done"):
        bag = dict(base.get(key) or {})
        for fid in FAIRY_IDS:
            bag[fid] = list(bag.get(fid) or [])
        base[key] = bag
    base["greeted"] = list(base.get("greeted") or [])
    base["secret_unlocked"] = bool(base.get("secret_unlocked"))
    base["secret_told"] = bool(base.get("secret_told"))
    return base


def save(conn, pid, d):
    ensure_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO moonpetal_friendship (player_id, data) VALUES (?, ?)",
        (int(pid), json.dumps(d)),
    )
    conn.commit()


def resolve_id(name_or_id):
    raw = str(name_or_id or "")
    if raw in FAIRY_IDS:
        return raw
    if raw in NAME_TO_ID:
        return NAME_TO_ID[raw]
    low = raw.lower().replace(" ", "_")
    if low in FAIRY_IDS:
        return low
    if low == "tamsin":
        return "tamsin_moon"
    return None


def all_maxed(d):
    fr = d.get("friendship") or {}
    return all(int(fr.get(fid) or 0) >= MAX for fid in FAIRY_IDS)


def grant_full_trust(conn, pid):
    """Every Moonpetal fairy at 100, and the house secret unlocked."""
    d = load(conn, pid)
    d["friendship"] = {fid: MAX for fid in FAIRY_IDS}
    greeted = list(d.get("greeted") or [])
    for fid in FAIRY_IDS:
        if fid not in greeted:
            greeted.append(fid)
    d["greeted"] = greeted
    d["secret_unlocked"] = True
    save(conn, pid, d)
    return d


def _add(d, fid, amount):
    fr = d.setdefault("friendship", {})
    before = int(fr.get(fid) or 0)
    after = min(MAX, before + int(amount))
    fr[fid] = after
    gained = after - before
    if all_maxed(d) and not d.get("secret_unlocked"):
        d["secret_unlocked"] = True
    return gained, after


def greet(conn, pid, fairy_id):
    """First-ever greeting with this fairy. Small friendship bump."""
    d = load(conn, pid)
    gained = 0
    if fairy_id not in d.get("greeted", []):
        d.setdefault("greeted", []).append(fairy_id)
        gained, _ = _add(d, fairy_id, GREET_GAIN)
        save(conn, pid, d)
    return d, gained


def apply_topic(conn, pid, fairy_id, topic):
    d = load(conn, pid)
    topic = str(topic or "")
    if topic not in TOPICS:
        return d, 0, TOPIC_LINES.get(fairy_id, {}).get(topic) or "…"
    done = d.setdefault("topics_done", {}).setdefault(fairy_id, [])
    gained = 0
    if topic not in done:
        done.append(topic)
        gained, _ = _add(d, fairy_id, TOPIC_GAIN)
        save(conn, pid, d)
    else:
        # Re-hearing still returns the long line; no extra friendship.
        pass
    line = TOPIC_LINES.get(fairy_id, {}).get(topic) or "…"
    return d, gained, line


def apply_compliment(conn, pid, fairy_id, comp_id):
    d = load(conn, pid)
    comps = COMPLIMENTS.get(fairy_id) or []
    entry = next((c for c in comps if c[0] == comp_id), None)
    if not entry:
        return d, 0, "She tilts her head, unconvinced."
    done = d.setdefault("compliments_done", {}).setdefault(fairy_id, [])
    gained = 0
    if comp_id not in done:
        done.append(comp_id)
        gained, _ = _add(d, fairy_id, COMPLIMENT_GAIN)
        save(conn, pid, d)
        reply = (
            f"{FAIRY_NAMES.get(fairy_id, 'She')} looks at you a long moment.\n\n"
            f"\"…You mean that.\"\n\n"
            f"Colour rises at her cheeks — or whatever fae have instead of cheeks. "
            f"Friendship deepens (+{gained})."
        )
    else:
        reply = (
            f"{FAIRY_NAMES.get(fairy_id, 'She')} smiles, soft and already-knowing.\n\n"
            f"\"You've said that one before. Say it again if you like — "
            f"I keep the first time.\"\n\n"
            f"(Already counted toward friendship.)"
        )
    return d, gained, reply


def public_state(d, fairy_id=None):
    fr = d.get("friendship") or {}
    out = {
        "friendship": {fid: int(fr.get(fid) or 0) for fid in FAIRY_IDS},
        "secret_unlocked": bool(d.get("secret_unlocked")) or all_maxed(d),
        "secret_told": bool(d.get("secret_told")),
        "max": MAX,
    }
    if fairy_id:
        done_t = set(d.get("topics_done", {}).get(fairy_id) or [])
        done_c = set(d.get("compliments_done", {}).get(fairy_id) or [])
        out["fairy_id"] = fairy_id
        out["value"] = int(fr.get(fairy_id) or 0)
        out["topics_done"] = list(done_t)
        out["compliments_done"] = list(done_c)
        out["compliments"] = [
            {"id": cid, "label": _compliment_label(cid), "done": cid in done_c}
            for cid, _line in (COMPLIMENTS.get(fairy_id) or [])
        ]
        remaining = sum(1 for fid in FAIRY_IDS if int(fr.get(fid) or 0) < MAX)
        out["fairies_remaining"] = remaining
    return out


def _compliment_label(cid):
    LABELS = {
        "grace": "Compliment her grace",
        "welcome": "Praise her welcome",
        "wisdom": "Admire her wisdom",
        "table": "Notice how she keeps the house",
        "trust": "Say the inn's heart is hers",
        "pages": "Praise how she tends the pages",
        "memory": "Honour her memory of the realm",
        "candle": "Notice her careful candles",
        "ink": "Respect her ink and courage",
        "shelf": "Trust her shelves with a secret",
        "bloom": "Praise the blooms she keeps",
        "dew": "Speak well of her dew-lore",
        "green": "Thank her for Crownfall's green",
        "bite": "Joke gently about the blue ones",
        "root": "Honour what she keeps alive",
        "watch": "Thank her sharp watch",
        "sky": "Praise how she reads the sky",
        "warning": "Say her warnings keep you safe",
        "balcony": "Admire the view she guards",
        "edge": "Respect the edge she keeps",
        "song": "Praise her music's reach",
        "string": "Say her notes heal the stairs",
        "history": "Honour the wars she keeps as song",
        "true": "Respect the true song she gave a king",
        "hum": "Thank her for taming the dark",
        "pour": "Praise how she pours a drink",
        "ledger": "Respect her feared ledgers",
        "honest": "Thank her for honest advice",
        "debt": "Admire how she holds old debts",
        "bar": "Say the bar feels safer than castles",
        "hearth": "Praise the warmth of her fire",
        "dark": "Respect how she walks the dark moon",
        "sister": "Thank her warnings of deep sisters",
        "light": "Tell her you kept a light lit",
        "ash": "Say even ash listens to her",
        "letter": "Praise letters that outrun swords",
        "wax": "Respect her moon-wax seals",
        "price": "Admire her prices for lords",
        "secret": "Trust how she keeps secrets",
        "shoulder": "Offer help, not a peek",
        "crystal": "Praise her honest crystals",
        "moonlight": "Thank her bottled moonlight",
        "fortune": "Believe what she saw of you",
        "chair": "Respect the hard reading she gives",
        "fun": "Thank her for a joke in grim hours",
    }
    return LABELS.get(cid) or f"Compliment ({cid})"


def mark_secret_told(conn, pid):
    d = load(conn, pid)
    d["secret_unlocked"] = True
    d["secret_told"] = True
    save(conn, pid, d)
    return d


def secret_line(d):
    if d.get("secret_unlocked") or all_maxed(d):
        return SECRET_TEASE
    return SECRET_HINT_PARTIAL
