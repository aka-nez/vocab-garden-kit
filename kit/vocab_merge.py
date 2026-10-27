#!/usr/bin/env python3
"""Merge helper for Vocab Garden: turns a batch of new phrases into updated unit docs.

Subcommands
  dedupe  --units-dir DIR --candidates raw.json --out fresh.json [--report r.json]
          Drops candidates already in the store (normalised match); for known
          phrases it records the extra lesson date in the report so `apply` can
          add it. fresh.json = only NEW items (to enrich).
  apply   --units-dir DIR --fresh enriched.json --report r.json --out-dir OUT --today YYYY-MM-DD
          Writes every changed unit doc to OUT/u<N>.json (full doc, ready for
          ArtifactData set with file_path) and OUT/summary.json.
  check   --fresh enriched.json
          Checks the 5 example sentences of every enriched item (same rules as apply); prints OK or problems.
  csv     --units-dir DIR --out vocab_master.csv

Candidate item fields (from extraction):
  phrase, definition, type, kind (target|feedback), source (chat|import|...),
  lesson_date ("25.09" or label, optional), unit_no (int), unit_title, evidence (optional)
Enriched items additionally carry (rules: examples_rules.md):
  ru, inflects (true|false), example, answer, example_form, example_context,
  more_examples: [{example, answer, form, context} x 4]
Every word has 5 sentences, each in a different context and grammar form; the quiz shows them in a
shuffle-bag order with a "form · context" label, and the audio step voices each one (clips example,
example2..example5). The sentence checks live in examples_check.py (keep it next to this file).

DIR holds the unit docs as saved by ArtifactData list --out_dir (files u1.json, u2.json ...
each the raw document {no,title,updated,words:[...]}).
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import examples_check  # same folder; rules in examples_rules.md
except ImportError:
    examples_check = None

N_MORE = 4  # more_examples per word (5 sentences in total)

STOP = {"sb", "sth", "someone", "something", "one's", "ones", "your", "yours", "my", "sb's", "sbs",
        "smb", "smth", "a", "an", "the", "be", "to", "get", "oneself", "yourself", "it", "his", "her"}


def norm(p):
    p = (p or "").lower()
    p = re.sub(r"\(.*?\)", " ", p)
    p = p.replace("’", "'")
    p = re.sub(r"[^a-z' ]+", " ", p)
    return " ".join(t for t in p.split() if t not in STOP)


def parts(p):
    return {norm(x) for x in re.split(r"\s*/\s*", p or "")} - {""}


def mkid(phrase):
    return hashlib.sha1(norm(phrase).encode()).hexdigest()[:10]


def iso(label, today):
    m = re.match(r"^(\d\d)\.(\d\d)", label or "")
    if not m:
        return None
    y = today.year
    d = f"{y}-{m.group(2)}-{m.group(1)}"
    if d > today.isoformat():  # a December lesson read in January
        d = f"{y - 1}-{m.group(2)}-{m.group(1)}"
    return d


def load_units(d):
    units = {}
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        doc = json.load(open(f, encoding="utf-8"))
        if "words" not in doc and isinstance(doc.get("data"), dict):
            doc = doc["data"]
        if "words" in doc:
            units[int(doc["no"])] = doc
    return units


def index(units):
    idx = {}
    for u in units.values():
        for w in u["words"]:
            idx.setdefault(norm(w["phrase"]), (u["no"], w["id"]))
    return idx


def find(idx, units, phrase):
    k = norm(phrase)
    if k in idx:
        return idx[k]
    cp = {c for c in parts(phrase) if len(c.split()) >= 2 or len(c) >= 7}
    if not cp:
        return None
    for u in units.values():
        for w in u["words"]:
            if cp & parts(w["phrase"]):
                return (u["no"], w["id"])
    return None


def cmd_dedupe(a):
    units = load_units(a.units_dir)
    idx = index(units)
    cands = json.load(open(a.candidates, encoding="utf-8"))
    fresh, known, seen = [], [], set()
    for c in cands:
        hit = find(idx, units, c["phrase"])
        if hit:
            known.append({"unit_no": hit[0], "id": hit[1], "lesson_date": c.get("lesson_date"),
                          "phrase": c["phrase"]})
            continue
        k = norm(c["phrase"])
        if k in seen:
            continue
        seen.add(k)
        fresh.append(c)
    json.dump(fresh, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"known": known}, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"candidates={len(cands)} new={len(fresh)} already_known={len(known)}")


def enrich_problems(c):
    """Why an enriched item can't be stored (empty list when it is fine)."""
    if examples_check is None:
        return ["examples_check.py not found next to vocab_merge.py (project doc vocab/examples_check.py)"]
    if not c.get("ru"):
        return ["missing ru"]
    if not c.get("example") or not c.get("answer"):
        return ["missing example/answer"]
    if c["example"].count(c["answer"]) != 1:
        return ["answer must occur exactly once in example"]
    more = c.get("more_examples")
    if not isinstance(more, list) or len(more) != N_MORE:
        return [f"need more_examples with {N_MORE} items {{example, answer, form, context}} (see examples_rules.md)"]
    if not isinstance(c.get("inflects"), bool):
        return ["missing inflects (true|false)"]
    w = {"id": c.get("phrase", "?"), "phrase": c.get("phrase", ""), "definition": c.get("definition", ""),
         "type": c.get("type", ""), "examples": [{"example": c["example"], "answer": c["answer"]}]}
    o = {"inflects": c["inflects"], "tags": [{"form": c.get("example_form", ""), "context": c.get("example_context", "")}],
         "new": more}
    return examples_check.check_word(w, o, N_MORE)


def cmd_check(a):
    fresh = json.load(open(a.fresh, encoding="utf-8"))
    probs = [p for c in fresh for p in enrich_problems(c)]
    if probs:
        print("\n".join(probs)); print(f"{len(probs)} problem(s)"); sys.exit(1)
    print(f"OK ({len(fresh)} items)")


def cmd_apply(a):
    today = date.fromisoformat(a.today)
    units = load_units(a.units_dir)
    rep = json.load(open(a.report, encoding="utf-8"))
    fresh = json.load(open(a.fresh, encoding="utf-8")) if a.fresh else []
    changed, added, updated, errors = set(), [], [], []
    byid = {w["id"]: (u, w) for u in units.values() for w in u["words"]}

    for k in rep.get("known", []):
        u, w = byid.get(k["id"], (None, None))
        if not w:
            continue
        touched = False
        lab = k.get("lesson_date")
        if lab and lab not in w.get("lessons", []):
            w.setdefault("lessons", []).append(lab)
            touched = True
        if touched:
            changed.add(u["no"])
            updated.append(w["id"])

    for c in fresh:
        why = enrich_problems(c)
        if why:
            errors += [f"not enriched properly: {p}" for p in why]
            continue
        no = int(c["unit_no"])
        if no not in units:
            units[no] = {"no": no, "title": c.get("unit_title") or f"Unit {no}", "words": []}
        wid = mkid(c["phrase"])
        if wid in byid:
            continue
        lab = c.get("lesson_date")
        w = {"id": wid, "phrase": c["phrase"].strip(), "definition": c["definition"].strip(), "ru": c["ru"],
             "example": c["example"], "answer": c["answer"],
             "example_form": c["example_form"].strip(), "example_context": c["example_context"],
             "more_examples": [{"example": m["example"], "answer": m["answer"], "form": m["form"].strip(),
                                "context": m["context"]} for m in c["more_examples"]],
             "type": c.get("type", ""),
             "source": c.get("source", "chat"), "kind": c.get("kind", "target"),
             "lessons": [lab] if lab else [], "first_seen": iso(lab, today) or today.isoformat(),
             "added": today.isoformat()}
        units[no]["words"].append(w)
        byid[wid] = (units[no], w)
        changed.add(no)
        added.append(wid)

    os.makedirs(a.out_dir, exist_ok=True)
    for no in sorted(changed):
        units[no]["updated"] = today.isoformat()
        json.dump(units[no], open(os.path.join(a.out_dir, f"u{no}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    total = sum(len(u["words"]) for u in units.values())
    summary = {"changed_units": sorted(changed), "added_ids": added, "updated_ids": updated,
               "added_count": len(added), "total": total, "errors": errors,
               "added_phrases": [byid[i][1]["phrase"] for i in added]}
    json.dump(summary, open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "added_ids"}, ensure_ascii=False, indent=1))
    if errors:
        sys.exit(2)


def cmd_csv(a):
    units = load_units(a.units_dir)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["phrase", "definition", "translation", "example", "example2", "example3", "example4", "example5",
                     "unit", "lessons", "source", "kind", "type", "first_seen", "id"])
        for no in sorted(units):
            u = units[no]
            for w in u["words"]:
                more = [(m or {}).get("example", "") for m in (w.get("more_examples") or [])][:N_MORE]
                more += [""] * (N_MORE - len(more))
                wr.writerow([w["phrase"], w["definition"], w.get("ru", ""), w.get("example", ""), *more,
                             f"Unit {no}: {u['title']}",
                             ", ".join(w.get("lessons", [])), w.get("source", ""), w.get("kind", ""), w.get("type", ""),
                             w.get("first_seen", ""), w["id"]])
    print("rows:", sum(len(u["words"]) for u in units.values()))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("dedupe"); d.add_argument("--units-dir", required=True); d.add_argument("--candidates", required=True)
    d.add_argument("--out", required=True); d.add_argument("--report", required=True)
    p = sp.add_parser("apply"); p.add_argument("--units-dir", required=True); p.add_argument("--fresh")
    p.add_argument("--report", required=True); p.add_argument("--out-dir", required=True); p.add_argument("--today", required=True)
    k = sp.add_parser("check"); k.add_argument("--fresh", required=True)
    c = sp.add_parser("csv"); c.add_argument("--units-dir", required=True); c.add_argument("--out", required=True)
    a = ap.parse_args()
    {"dedupe": cmd_dedupe, "apply": cmd_apply, "check": cmd_check, "csv": cmd_csv}[a.cmd](a)


if __name__ == "__main__":
    main()
