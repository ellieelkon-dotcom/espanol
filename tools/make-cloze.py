#!/usr/bin/env python3
"""Fill in the `cl` field used by the sentence-completion mode.

For every card it looks for the word inside its own example sentence and
records where to open the blank. Verbs appear conjugated (the card says
pensar, the sentence says Pienso), so the forms below are generated and
matched against the sentence; the sentence decides which candidate is real.

`cl` is [answer, start, infinitive]: the text to type, where it sits in `ex`,
and the infinitive to show as a hint for verbs (empty for everything else).
It is Spanish only, so both versions get the same value.

Run from the project root after adding words:  python3 tools/make-cloze.py
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECKS = [ROOT / "data" / "deck.json", ROOT / "en" / "data" / "deck.json"]

WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
ART = re.compile(r"^(el|la|los|las|un|una|unos|unas)\s+", re.I)
# one-letter and two-letter words that would otherwise swallow a pronoun or article
STOP = {"se", "me", "te", "le", "lo", "la", "las", "los", "el", "un", "una",
        "de", "a", "y", "en", "que", "no", "su", "mi", "es", "ha", "he"}

ENDINGS = {
    "ar": ["o","as","a","amos","ais","an","e","es","emos","eis","en","aste","amos","asteis","aron",
           "aba","abas","abamos","abais","aban","are","aras","aremos","areis","aran",
           "aria","arias","ariamos","ariais","arian","ando","ado","ada","ados","adas",
           "ase","ases","asemos","asen","ara","aras","aran","aramos"],
    "er": ["o","es","e","emos","eis","en","a","as","amos","ais","an","i","iste","io","imos","isteis","ieron",
           "ia","ias","iamos","iais","ian","ere","eras","era","eremos","ereis","eran",
           "eria","erias","eriamos","eriais","erian","iendo","ido","ida","idos","idas",
           "iese","ieses","iesemos","iesen","iera","ieras","ieran","ieramos"],
    "ir": ["o","es","e","imos","is","en","a","as","amos","ais","an","i","iste","io","imos","isteis","ieron",
           "ia","ias","iamos","iais","ian","ire","iras","ira","iremos","ireis","iran",
           "iria","irias","iriamos","iriais","irian","iendo","ido","ida","idos","idas",
           "iese","ieses","iesemos","iesen","iera","ieras","ieran","ieramos"],
}

# verbs whose real forms the patterns above cannot reach
IRREGULAR = {
    "ser": "soy eres es somos sois son era eras eramos eran fui fuiste fue fuimos fueron sere seria siendo sido sea seas sean fuera fuese",
    "ir": "voy vas va vamos vais van iba ibas ibamos iban fui fuiste fue fuimos fueron ire iria yendo ido vaya vayas vayan fuera fuese",
    "haber": "he has ha hemos habeis han habia habias habiamos habian hubo hubiste hubieron habra habria habiendo habido haya hayas hayan hubiera hubiese hay",
    "estar": "estoy estas esta estamos estais estan estuve estuviste estuvo estuvimos estuvieron estare estaria estuviera este esten",
    "tener": "tengo tienes tiene tenemos teneis tienen tuve tuviste tuvo tuvimos tuvieron tendre tendria tenga tengas tengan tuviera ten",
    "hacer": "hago haces hace hacemos haceis hacen hice hiciste hizo hicimos hicieron hare haria haga hagas hagan hiciera hecho haz",
    "decir": "digo dices dice decimos decis dicen dije dijiste dijo dijimos dijeron dire diria diga digas digan dijera dicho diciendo",
    "poder": "puedo puedes puede podemos podeis pueden pude pudiste pudo pudimos pudieron podre podria pueda puedan pudiera pudiendo",
    "poner": "pongo pones pone ponemos poneis ponen puse pusiste puso pusimos pusieron pondre pondria ponga pongan pusiera puesto",
    "saber": "sabes sabe sabemos sabeis saben supe supiste supo supimos supieron sabre sabria sepa sepas sepan supiera sabiendo",
    "querer": "quiero quieres quiere queremos quereis quieren quise quisiste quiso quisimos quisieron querre querria quiera quieran quisiera",
    "venir": "vengo vienes viene venimos venis vienen vine viniste vino vinimos vinieron vendre vendria venga vengan viniera viniendo",
    "dar": "doy das damos dais dan diste dio dimos dieron dare daria den diera dando dado",
    "ver": "veo ves vemos veis vi viste vio vimos vieron vere veria vea vean viera viendo visto veia veias veian",
    "salir": "salgo sales sale salimos salis salen sali saliste salio salieron saldre saldria salga salgan saliera saliendo",
    "traer": "traigo traes trae traemos traen traje trajiste trajo trajimos trajeron traiga traigan trajera trayendo traido",
    "caer": "caigo caes cae caemos caen cai caiste cayo caimos cayeron caiga caigan cayera cayendo caido",
    "oir": "oigo oyes oye oimos ois oyen oi oiste oyo oyeron oiga oigan oyera oyendo oido",
    "leer": "leo lees lee leemos leen lei leiste leyo leimos leyeron leyera leyendo leido",
    "jugar": "juego juegas juega jugamos jugais juegan jugue jugaste jugo jugaron juegue jueguen jugara jugando jugado",
}

CLITICS = ("lo", "la", "le", "me", "te", "se", "nos", "los", "las", "les", "melo", "selo")


def flat(s):
    """Lowercase without accents, so ó and o compare equal."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def stems(stem):
    """Stem changes a conjugated form may show: e>ie, e>i, o>ue, and spelling shifts."""
    out = {stem}
    vowels = list(re.finditer(r"[eo]", stem))
    if vowels:
        at = vowels[-1].start()
        for src, dst in (("e", "ie"), ("e", "i"), ("o", "ue"), ("o", "u")):
            if stem[at] == src:
                out.add(stem[:at] + dst + stem[at + 1:])
    if stem.endswith("u"):
        out.add(stem[:-1] + "ue")
    for s in list(out):
        if s.endswith("c"):
            out.add(s[:-1] + "zc")   # conocer > conozco, traducir > traduzco
        if s.endswith("gu"):
            out.add(s[:-1])          # seguir > sigo
        if s.endswith("u"):
            out.add(s + "y")         # destruir > destruyo
        if s.endswith("g"):
            out.add(s[:-1] + "j")    # coger > cojo
    out |= {s + "g" for s in list(out)}    # tener > tengo
    out |= {s + "ig" for s in list(out)}   # traer > traigo
    return out


def verb_forms(infinitive):
    inf = flat(infinitive)
    base = inf[:-2] if inf.endswith("se") else inf
    out = {inf, base}
    if base in IRREGULAR:
        out |= set(IRREGULAR[base].split())
    if len(base) > 2 and base[-2:] in ENDINGS:
        for stem in stems(base[:-2]):
            out |= {stem + e for e in ENDINGS[base[-2:]]}
    out |= {f + c for f in list(out) if len(f) > 3 for c in CLITICS}
    return out


def noun_forms(es):
    """The headword plus its gender and number variants."""
    out = set()
    for part in re.split(r"[/,]", re.sub(r"\(.*?\)", "", es)):
        p = part.strip().strip("¡!¿?.,")
        if p:
            out.add(p)
            out.add(ART.sub("", p).strip())
    out = {flat(v) for v in out if v}
    for v in list(out):
        head, rest = (v.split(" ", 1) + [""])[:2]
        rest = (" " + rest) if rest else ""
        group = {head}
        if head.endswith(("o", "a", "e")):
            group |= {head[:-1] + x for x in "oae"}
        for g in list(group):
            group.add(g + "s")
            if g[-1:] not in "aeiou":
                group.add(g + "es")
        out |= {g + rest for g in group}
    return out


def locate(sentence, forms, allow_short):
    """Longest candidate that appears in the sentence, as a (start, end) span."""
    toks = [(m.start(), m.end()) for m in WORD.finditer(sentence)]
    for n in range(4, 0, -1):
        best = None
        for i in range(len(toks) - n + 1):
            s, e = toks[i][0], toks[i + n - 1][1]
            surf = flat(sentence[s:e])
            if surf not in forms:
                continue
            if n == 1 and not allow_short and (len(surf) <= 2 or surf in STOP):
                continue
            if best is None or e - s > best[1] - best[0]:
                best = (s, e)
        if best:
            return best
    return None


def cloze_for(card):
    ex = card.get("ex") or ""
    if not ex:
        return None
    if card.get("kind") == "verb":
        infs = [p.strip() for p in re.split(r"[/,]", re.sub(r"\(.*?\)", "", card["es"])) if p.strip()]
        forms = set()
        for inf in infs:
            forms |= verb_forms(inf)
        span = locate(ex, forms, False) or locate(ex, forms, True)
        hint = " / ".join(infs)
    else:
        forms = noun_forms(card["es"])
        span = locate(ex, forms, False)
        hint = ""
    if not span:
        return None
    # a synonym or another form of the same verb left in the sentence gives the answer
    # away, so those cards sit the mode out rather than ask a broken question
    rest = ex[:span[0]] + " " + ex[span[1]:]
    if locate(rest, forms if card.get("kind") == "verb" else noun_forms(card["es"]), False):
        return None
    return [ex[span[0]:span[1]], span[0], hint]


def main():
    made = skipped = 0
    missing = []
    results = {}
    for path in DECKS:
        deck = json.loads(path.read_text(encoding="utf-8"))
        for card in deck["cards"]:
            cl = results.get(card["id"], "unset")
            if cl == "unset":
                cl = cloze_for(card)
                results[card["id"]] = cl
                if cl:
                    made += 1
                else:
                    skipped += 1
                    missing.append(f"[{card.get('kind')}] {card['es']}")
            if cl:
                card["cl"] = cl
            else:
                card.pop("cl", None)
        path.write_text(
            json.dumps(deck, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8")

    total = made + skipped
    print(f"sentence completion ready for {made}/{total} cards ({made / total * 100:.0f}%)")
    if missing:
        print(f"\n{len(missing)} cards have no usable blank and are left out of that mode:")
        for m in missing:
            print(f"  - {m}")
        print("\nUsually the card is a phrase the sentence splits up, a number written as a word,")
        print("or a card whose sentence also uses one of its synonyms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
