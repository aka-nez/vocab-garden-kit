#!/usr/bin/env python3
"""Check extra example sentences for Vocab Garden (rules: examples_rules.md).

python3 examples_check.py in.json out.json [--new N]

in.json : [{id, phrase, definition, type, examples:[{example, answer}, ...]}]
out.json: [{id, inflects, tags:[{form, context}] (one per existing example), new:[{example, answer, form, context}] }]
Prints every problem, or OK. Exit 1 on problems.
"""
import argparse, collections, difflib, json, re, sys

CONTEXTS = {"work", "tech", "money", "shopping", "travel", "home", "family", "friends", "relationships", "food",
            "health", "sport", "city", "nature", "animals", "study", "entertainment", "weather", "celebrations", "news"}
STOP = set("""a an the and or but if so to of in on at for with by from as is are was were be been being it its this
that these those i you he she we they me him her us them my your his our their not no do does did have has had will
would can could should just very really too also than then there here what when who how all some any up out about
into over after before more most much many one get got i'm it's don't didn't can't won't""".split())
ABBR = re.compile(r"[/\\()\[\]{}<>\"“”]|\b(sb|sth|e\.g|etc|i\.e|approx)\b", re.I)


def words(s):
    return re.findall(r"[a-z']+", s.lower())


def content(s, drop):
    return {w for w in words(s) if w not in STOP and w not in drop and len(w) > 2}


def base_form(f):
    return re.sub(r"\s+(question|negative)$", "", (f or "").strip().lower())


def opening(s):
    return " ".join(words(s)[:3])


def check_word(w, o, n_new):
    probs = []
    p = f"{w['id']} ({w['phrase']}):"
    old = w["examples"]
    tags, new = o.get("tags") or [], o.get("new") or []
    if len(tags) != len(old):
        probs.append(f"{p} tags must label the {len(old)} existing sentences (got {len(tags)})")
    if len(new) != n_new:
        probs.append(f"{p} need {n_new} new sentences (got {len(new)})")
    for t in tags + new:
        if t.get("context") not in CONTEXTS:
            probs.append(f"{p} context {t.get('context')!r} not in the list")
        f = (t.get("form") or "").strip()
        if not f or len(f.split()) > 5 or f != f.lower():
            probs.append(f"{p} form {f!r} must be a short lowercase label")
    old_ctx = {t.get("context") for t in tags}
    old_forms = {base_form(t.get("form")) for t in tags}
    new_ctx = [t.get("context") for t in new]
    new_forms = [base_form(t.get("form")) for t in new]
    if len(set(new_ctx)) != len(new_ctx) or set(new_ctx) & old_ctx:
        probs.append(f"{p} new contexts must differ from each other and from existing {sorted(old_ctx)}: {new_ctx}")
    full_new = [(t.get("form") or "").strip().lower() for t in new]
    if o.get("inflects"):
        if len(set(new_forms)) != len(new_forms) or set(new_forms) & old_forms:
            probs.append(f"{p} new base forms must differ from each other and from existing {sorted(old_forms)}: {new_forms}")
    elif len(set(full_new)) != len(full_new) or set(full_new) & {(t.get('form') or '').strip().lower() for t in tags}:
        probs.append(f"{p} new forms must differ from each other and from existing: {full_new}")
    drop = set(words(w["phrase"]))
    allx = [{"example": e["example"], "answer": e["answer"], "old": True} for e in old] + \
           [{"example": t.get("example", ""), "answer": t.get("answer", ""), "old": False} for t in new]
    for t in new:
        ex, a = t.get("example", ""), t.get("answer", "")
        q = f"{p} new “{ex[:50]}…”"
        if not ex or not a:
            probs.append(f"{q} empty example/answer"); continue
        if ex.count(a) != 1:
            probs.append(f"{q} answer {a!r} must occur exactly once (found {ex.count(a)})")
        if a != a.strip() or a[-1:] in ".!?,;:":
            probs.append(f"{q} answer has edge spaces/punctuation")
        n = len(ex.split())
        if n < 7 or n > 22:
            probs.append(f"{q} {n} words (want 8-20)")
        if re.search(r"\d", ex):
            probs.append(f"{q} digits — write numbers as words")
        if ABBR.search(ex):
            probs.append(f"{q} slash/bracket/quote/abbreviation")
        if ex[-1:] not in ".!?":
            probs.append(f"{q} must end with . ! or ?")
        i = ex.find(a)
        if i > 0 and re.search(r"'(s|ve|d|ll|re|m)\s*$", ex[:i]):
            probs.append(f"{q} contracted auxiliary right before the answer")
        if re.search(r"\b(should|could|would|might|must|can|may)\b", a.lower()) and not re.search(r"\b(should|could|would|might|must|can|may)\b", w["phrase"].lower()):
            probs.append(f"{q} answer must not include the modal verb")
    # pairwise near-duplicate checks (each new sentence vs every other sentence)
    for i, x in enumerate(allx):
        for j, y in enumerate(allx):
            if j <= i or (x["old"] and y["old"]) or not x["example"] or not y["example"]:
                continue
            c1, c2 = content(x["example"], drop), content(y["example"], drop)
            if c1 and c2:
                ov = len(c1 & c2) / min(len(c1), len(c2))
                if ov > 0.4:
                    probs.append(f"{p} sentences {i + 1} and {j + 1} share too many words {sorted(c1 & c2)}")
            strip = lambda s, a: s.replace(a, " ").lower() if a else s.lower()
            r = difflib.SequenceMatcher(None, strip(x["example"], x["answer"]), strip(y["example"], y["answer"])).ratio()
            if r > 0.55:
                probs.append(f"{p} sentences {i + 1} and {j + 1} are worded too similarly ({r:.2f})")
            if opening(x["example"]) == opening(y["example"]):
                probs.append(f"{p} sentences {i + 1} and {j + 1} start the same way ({opening(x['example'])!r})")
    if o.get("inflects"):
        answers = {e["answer"].lower() for e in allx if e["answer"]}
        if len(answers) < 3:
            probs.append(f"{p} inflecting phrase: the 5 answers should show at least 3 different forms (got {sorted(answers)})")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--new", type=int, default=3)
    a = ap.parse_args()
    src = json.load(open(a.inp))
    try:
        out = json.load(open(a.out))
    except Exception as e:
        print("cannot read output:", e); return 1
    by = {o.get("id"): o for o in out if isinstance(o, dict)}
    probs = []
    if len(out) != len(src):
        probs.append(f"count: {len(out)} outputs for {len(src)} inputs")
    ids = {w["id"] for w in src}
    probs += [f"unknown id {o.get('id')}" for o in out if isinstance(o, dict) and o.get("id") not in ids]
    ctx = collections.Counter()
    for w in src:
        o = by.get(w["id"])
        if not o:
            probs.append(f"{w['id']} missing"); continue
        probs += check_word(w, o, a.new)
        ctx.update(t.get("context") for t in o.get("new") or [])
    total = sum(ctx.values())
    for c, k in ctx.items():
        if total >= 60 and k / total > 0.15:
            probs.append(f"batch: context {c!r} used for {k} of {total} new sentences — spread contexts more evenly")
    if probs:
        print("\n".join(probs)); print(f"{len(probs)} problem(s)"); return 1
    print("OK"); return 0


if __name__ == "__main__":
    sys.exit(main())
