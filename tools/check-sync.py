#!/usr/bin/env python3
"""Check that en/data/ stays in sync with data/.

Language-neutral content (Spanish text, ids, ordering, structure) must be
identical in both versions. Translated content must be present on both sides,
Hebrew on one and free of Hebrew on the other.

Run from the project root:  python3 tools/check-sync.py
Exits 1 and lists every problem it found.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HE_DIR = ROOT / "data"
EN_DIR = ROOT / "en" / "data"
HEBREW = re.compile(r"[֐-׿]")

errors = []
reported_hebrew = set()  # strings already flagged, so the sweep below does not repeat them


def err(msg):
    errors.append(msg)


def load(name):
    he = json.loads((HE_DIR / name).read_text(encoding="utf-8"))
    en = json.loads((EN_DIR / name).read_text(encoding="utf-8"))
    return he, en


def same(name, label, a, b):
    """Language-neutral value: must match between the two versions."""
    if a != b:
        err(f"{name}: {label} differs: he={a!r} en={b!r}")


def check_translated(name, label, he_val, en_val, want_hebrew=True):
    """Translated value: both sides filled or both empty, each in its language."""
    he_val, en_val = str(he_val), str(en_val)
    if bool(he_val.strip()) != bool(en_val.strip()):
        err(f"{name}: {label} filled on one side only: he={he_val!r} en={en_val!r}")
        return
    if not he_val.strip():
        return
    if HEBREW.search(en_val):
        err(f"{name}: {label} still Hebrew in the English version: {en_val!r}")
        reported_hebrew.add(en_val)
    if want_hebrew and not HEBREW.search(he_val):
        err(f"{name}: {label} has no Hebrew in the Hebrew version: {he_val!r}")


def check_no_hebrew(name, data):
    """Nothing anywhere in the English files may contain Hebrew."""
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and HEBREW.search(node) and node not in reported_hebrew:
            err(f"{name}: Hebrew left in the English version at {path}: {node!r}")

    walk(data, "")


def check_deck():
    name = "deck.json"
    he, en = load(name)
    same(name, "updated", he.get("updated"), en.get("updated"))

    hc, ec = he["cards"], en["cards"]
    if len(hc) != len(ec):
        err(f"{name}: card count differs: he={len(hc)} en={len(ec)}")

    he_ids = [c.get("id") for c in hc]
    en_ids = [c.get("id") for c in ec]
    for label, ids in (("he", he_ids), ("en", en_ids)):
        dups = {i for i in ids if ids.count(i) > 1}
        if dups:
            err(f"{name}: duplicate ids in the {label} version: {sorted(dups)}")
    missing_en = [i for i in he_ids if i not in set(en_ids)]
    missing_he = [i for i in en_ids if i not in set(he_ids)]
    if missing_en:
        err(f"{name}: {len(missing_en)} cards missing from the English version: {missing_en[:10]}")
    if missing_he:
        err(f"{name}: {len(missing_he)} cards missing from the Hebrew version: {missing_he[:10]}")
    if not missing_en and not missing_he and he_ids != en_ids:
        err(f"{name}: cards are in a different order in the two versions")

    en_by_id = {c.get("id"): c for c in ec}
    for card in hc:
        cid = card.get("id")
        other = en_by_id.get(cid)
        if other is None:
            continue
        where = f"{name} card {cid}"
        for field in ("es", "ex", "kind"):
            same(where, field, card.get(field), other.get(field))
        for field in ("he", "exHe", "topic"):
            check_translated(where, field, card.get(field, ""), other.get(field, ""))
        # note and src are usually plain Spanish or a source name, so no Hebrew is required
        for field in ("note", "src"):
            check_translated(where, field, card.get(field, ""), other.get(field, ""), want_hebrew=False)

    check_no_hebrew(name, en)


def check_grammar():
    name = "grammar.json"
    he, en = load(name)
    same(name, "focus", he.get("focus"), en.get("focus"))
    same(name, "active", he.get("active"), en.get("active"))

    ht, et = he.get("topics", {}), en.get("topics", {})
    same(name, "topic keys", sorted(ht), sorted(et))
    for key in sorted(set(ht) & set(et)):
        where = f"{name} topic {key}"
        same(where, "subkeys", sorted(ht[key]), sorted(et[key]))
        same(where, "week", ht[key].get("week"), et[key].get("week"))
        check_translated(where, "name", ht[key].get("name", ""), et[key].get("name", ""))
        # short labels and some rules are pure Spanish, so no Hebrew is required
        for field in ("short", "rule"):
            if field in ht[key] or field in et[key]:
                check_translated(where, field, ht[key].get(field, ""), et[key].get(field, ""), want_hebrew=False)

    hi, ei = he.get("items", []), en.get("items", [])
    if len(hi) != len(ei):
        err(f"{name}: question count differs: he={len(hi)} en={len(ei)}")
    for idx, (a, b) in enumerate(zip(hi, ei)):
        where = f"{name} question {idx}"
        if len(a) != 6 or len(b) != 6:
            err(f"{where}: expected 6 fields, got he={len(a)} en={len(b)}")
            continue
        # 0 topic key, 1 prompt, 2 hint, 3 options: all language-neutral
        for pos, label in ((0, "topic"), (1, "prompt"), (2, "hint"), (3, "options")):
            same(where, label, a[pos], b[pos])
        # 4 explanation keeps Spanish terms inline, so no Hebrew is required there
        check_translated(where, "explanation", a[4], b[4], want_hebrew=False)
        check_translated(where, "translation", a[5], b[5])
        if a[0] not in ht:
            err(f"{where}: topic {a[0]!r} is not in topics")

    for key in he.get("active", []):
        if key not in ht:
            err(f"{name}: active topic {key!r} is not in topics")

    check_no_hebrew(name, en)


def check_clips():
    name = "clips.json"
    he, en = load(name)
    hi, ei = he.get("items", []), en.get("items", [])
    if len(hi) != len(ei):
        err(f"{name}: clip count differs: he={len(hi)} en={len(ei)}")

    en_by_id = {c.get("id"): c for c in ei}
    if [c.get("id") for c in hi] != [c.get("id") for c in ei]:
        err(f"{name}: clip ids or order differ: he={[c.get('id') for c in hi]} en={[c.get('id') for c in ei]}")

    for clip in hi:
        cid = clip.get("id")
        other = en_by_id.get(cid)
        if other is None:
            err(f"{name}: clip {cid} missing from the English version")
            continue
        where = f"{name} clip {cid}"
        for field in ("es", "title"):
            same(where, field, clip.get(field), other.get(field))
        for field in ("he", "topic"):
            check_translated(where, field, clip.get(field, ""), other.get(field, ""))

        hq, eq = clip.get("qs", []), other.get("qs", [])
        if len(hq) != len(eq):
            err(f"{where}: question count differs: he={len(hq)} en={len(eq)}")
            continue
        for qi, (a, b) in enumerate(zip(hq, eq)):
            qwhere = f"{where} question {qi}"
            check_translated(qwhere, "text", a[0], b[0])
            if len(a[1]) != len(b[1]):
                err(f"{qwhere}: answer count differs: he={len(a[1])} en={len(b[1])}")
                continue
            for oi, (ao, bo) in enumerate(zip(a[1], b[1])):
                check_translated(qwhere, f"answer {oi}", ao, bo)

    check_no_hebrew(name, en)


def main():
    for directory in (HE_DIR, EN_DIR):
        if not directory.is_dir():
            print(f"missing directory: {directory}", file=sys.stderr)
            return 1

    check_deck()
    check_grammar()
    check_clips()

    if errors:
        print(f"{len(errors)} problem(s) between data/ and en/data/:\n", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        print("\nUpdate the English version to match, then run this again.", file=sys.stderr)
        return 1

    print("data/ and en/data/ are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
