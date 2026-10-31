#!/usr/bin/env python3
"""Irregular verbs for the Vocab Garden "Verbs" tab.

Source: verbs_src.txt, one verb per line, pipe-separated (no header):
    v1|v2|v3|translation|past simple sentence|its translation|modal sentence|its translation
v2/v3 may list variants with "/" (first = the American main form; all are accepted as answers).
The modal sentence must contain "<should|shouldn't|could|couldn't|must|might|can't> have <v3>".
The translation columns are in the learner's language (the db field is called `ru` whatever the language).

    python3 verbs_tool.py build --src verbs_src.txt --notes notes.ru.json --out verbs_list.json [--table]
        -> the db doc verbs/list  {version, updated, count, notes, verbs:[...]}
    python3 verbs_tool.py jobs --src verbs_src.txt --voice eric --model elevenlabs/eleven-v4 --out jobs.json
        -> a jobs file for tts_cache.py plan / run / pack (3 clips per verb: forms, ex2, ex3)
    python3 verbs_tool.py audio-doc --jobs jobs.json --manifest audio_cache.json --artifact <url> --out verbs_audio.json
        -> the db doc verbs/audio  {voice, model, updated, clips:{<id>:{forms, ex2, ex3}}}; exits 2 if clips are missing

Only the English columns are voiced, so a translated verbs_src.txt produces the same clip keys (the cache
prevents paying twice inside one manifest).
"""
import argparse, datetime as dt, hashlib, json, re, sys, collections

V="aeiou"
def ed(v):
    if v.endswith('e'): return v+'d'
    if v.endswith('y') and v[-2] not in V: return v[:-1]+'ied'
    if re.fullmatch(r'[^aeiou]*[aeiou][^aeiouwxy]', v) and len(v)<=4: return v+v[-1]+'ed'
    return v+'ed'
def en(v):
    if v.endswith('ee'): return v+'n'
    if v.endswith('e'): return v+'n'
    if re.fullmatch(r'[^aeiou]*[aeiou][^aeiouwxy]', v): return v+v[-1]+'en'
    return v+'en'
def ing(v):
    if v.endswith('ee'): return v+'ing'
    if v.endswith('ie'): return v[:-2]+'ying'
    if v.endswith('e'): return v[:-1]+'ing'
    if re.fullmatch(r'[^aeiou]*[aeiou][^aeiouwxy]', v) or v in ('upset','forget','begin'): return v+v[-1]+'ing'
    return v+'ing'
def shifts(v):
    out=[]
    m=re.search(r'i(ng|nk|m|n|g|t|ck)$',v)
    if m and re.fullmatch(r'[^aeiou]*i[^aeiou]+',v):
        out += [v[:m.start()]+'a'+v[m.start()+1:], v[:m.start()]+'u'+v[m.start()+1:]]
    if re.fullmatch(r'[^aeiou]*ee[^aeiou]+',v): out.append(v.replace('ee','e'))
    if v.endswith('ow') and len(v)<=5: out.append(v[:-2]+'ew')
    return out
SAY={'read':{'forms':'read, red, red','ex2':'I red the whole book on the plane.','ex3':'You could have red the instructions first.'},
     'tear':{'forms':'tear, tore, torn. As in, to tear paper.'}}
OVR={ # hand-picked traps where the generator is weak
 'be':{'t2':['been','be','is'],'t3':['was','were','be']},
 'have':{'t2':['haved','has','have'],'t3':['haved','has','hadden']},
 'do':{'t2':['done','doed','does'],'t3':['did','doed','doen']},
 'go':{'t2':['gone','goed','wented'],'t3':['went','goed','wented']},
 'get':{'t2':['gotten','getted','gat'],'t3':['getted','gat','gotted']},
 'lie':{'t2':['lain','laid','lied'],'t3':['lay','laid','lied']},
 'lay':{'t2':['layed','lain','lay'],'t3':['layed','lain','lay']},
 **{v:{'t2':[v,v+'ing',v+'en'],'t3':[v,v+'ing',v+'en']} for v in ['burn','dream','lean','leap','learn','smell','spell','spill','spoil','kneel']},
 'light':{'t2':['light','lited','lighten'],'t3':['light','lited','lighten']},
 'show':{'t2':['shown','show','shew'],'t3':['show','showen','shew']},
 'prove':{'t2':['proven','prove','proof'],'t3':['prove','proof','proving']},
 'sew':{'t2':['sewn','sew','sown'],'t3':['sew','sown','sewing']},
 'swell':{'t2':['swollen','swell','swole'],'t3':['swell','swole','swelling']},
 'fit':{'t2':['fat','fitten','fitting'],'t3':['fat','fitten','fitting']},
 'shine':{'t2':['shine','shinned','shane'],'t3':['shine','shinned','shoned']},
 'dive':{'t2':['dive','diven','dave'],'t3':['dive','diven','doven']},
 'hang':{'t2':['hanged','hanging','hang'],'t3':['hanged','hang','hungen']},
}


def norm_text(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def clip_key(model, voice, text):  # same as tts_cache.py
    return hashlib.sha1(f"{model}\n{voice}\n{norm_text(text)}".encode()).hexdigest()[:16]


def parse(src):
    rows = [l.rstrip("\n").split("|") for l in open(src, encoding="utf-8") if l.strip()]
    verbs, bad, modals = [], [], collections.Counter()
    for i, row in enumerate(rows):
        if len(row) != 8:
            bad.append((i + 1, f"{len(row)} columns")); continue
        v1, v2, v3, ru, ex2, ru2, ex3, ru3 = [c.strip() for c in row]
        f2, f3 = v2.split("/"), v3.split("/")
        m2 = next((f for f in f2 if re.search(r"\b" + re.escape(f) + r"\b", ex2)), None)
        m3 = re.search(r"\b((?:should|shouldn't|could|couldn't|must|might|can't) have) (" + "|".join(map(re.escape, f3)) + r")\b", ex3)
        if not m2 or not m3:
            bad.append((i + 1, v1 + (": V2 not found in the past simple sentence" if not m2 else ": no modal + have + V3 in the modal sentence"))); continue
        modal = m3.group(1).replace("shouldn't", "should").replace("couldn't", "can't")
        modals[modal] += 1
        valid = {2: set(f2), 3: set(f3)}

        def traps(T):
            cand = [(f3 if T == 2 else f2)[0], ed(v1)]
            if T == 2: cand += [f2[0] + "ed" if not f2[0].endswith("e") else f2[0] + "d", v1]
            else: cand += [en(f2[0]) if f2[0] != f3[0] else None, v1]
            cand += shifts(v1) + [en(v1), ing(v1)]
            out = []
            for c in cand:
                if c and c not in valid[T] and c not in out: out.append(c)
            return out[:5]

        o, s = OVR.get(v1, {}), SAY.get(v1, {})
        verbs.append({"id": v1, "n": len(verbs) + 1, "v1": v1, "v2": f2, "v3": f3, "ru": ru,
                      "ex2": {"s": ex2, "a": m2, "ru": ru2},
                      "ex3": {"s": ex3, "a": m3.group(2), "hl": m3.group(0), "m": modal, "ru": ru3},
                      "t2": o.get("t2") or traps(2), "t3": o.get("t3") or traps(3),
                      "say": {"forms": s.get("forms", ", ".join([v1, "was, were" if v1 == "be" else f2[0], f3[0]]) + "."),
                              "ex2": s.get("ex2", ex2), "ex3": s.get("ex3", ex3)}})
    return verbs, bad, modals


def cmd_build(a):
    verbs, bad, modals = parse(a.src)
    if bad:
        print("problems:\n  " + "\n  ".join(f"line {n}: {m}" for n, m in bad)); return 2
    notes = json.load(open(a.notes, encoding="utf-8")) if a.notes else {}
    doc = {"version": 1, "updated": dt.date.today().isoformat(), "count": len(verbs), "notes": notes,
           "verbs": [{k: v for k, v in x.items() if k != "say"} for x in verbs]}
    json.dump(doc, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(verbs)} verbs -> {a.out}; modals: {dict(modals)}")
    if a.table:
        for v in verbs:
            print(f"{v['v1']:<14} V2 {'/'.join(v['v2']):<16} {v['t2']}  | V3 {'/'.join(v['v3']):<16} {v['t3']}")
    return 0


def cmd_jobs(a):
    verbs, bad, _ = parse(a.src)
    if bad:
        print("fix verbs_src.txt first (run build)"); return 2
    out = {"model": a.model, "voices": [a.voice], "default_voice": a.voice, "words": [], "jobs": []}
    for v in verbs:
        for clip in ("forms", "ex2", "ex3"):
            t = norm_text(v["say"][clip])
            out["jobs"].append({"word": v["id"], "clip": clip, "voice": a.voice, "text": t, "model": a.model, "key": clip_key(a.model, a.voice, t)})
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(verbs)} verbs -> {len(out['jobs'])} clips -> {a.out}")
    return 0


def cmd_audio_doc(a):
    J = json.load(open(a.jobs, encoding="utf-8"))
    man = json.load(open(a.manifest, encoding="utf-8"))
    clips, missing = {}, 0
    for j in J["jobs"]:
        e = man.get("entries", {}).get(j["key"]) or {}
        up = (e.get("assets") or {}).get(a.artifact)
        if not up:
            missing += 1; continue
        clips.setdefault(j["word"], {})[j["clip"]] = up["url"]
    doc = {"voice": J["default_voice"], "model": J["model"], "updated": dt.date.today().isoformat(), "clips": clips}
    json.dump(doc, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(clips)} verbs with clips -> {a.out}" + (f"; {missing} clips not uploaded to this artifact yet" if missing else ""))
    return 2 if missing else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("build"); p.add_argument("--src", default="verbs_src.txt"); p.add_argument("--notes", default="")
    p.add_argument("--out", default="verbs_list.json"); p.add_argument("--table", action="store_true")
    p = sp.add_parser("jobs"); p.add_argument("--src", default="verbs_src.txt"); p.add_argument("--voice", default="eric")
    p.add_argument("--model", default="elevenlabs/eleven-v4"); p.add_argument("--out", default="jobs.json")
    p = sp.add_parser("audio-doc"); p.add_argument("--jobs", default="jobs.json"); p.add_argument("--manifest", default="audio_cache.json")
    p.add_argument("--artifact", required=True); p.add_argument("--out", default="verbs_audio.json")
    a = ap.parse_args()
    return {"build": cmd_build, "jobs": cmd_jobs, "audio-doc": cmd_audio_doc}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
