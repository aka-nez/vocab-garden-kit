#!/usr/bin/env python3
"""Pronunciation audio for Vocab Garden — generate once, never pay twice.

Audio comes from ElevenLabs voices served through OpenRouter's TTS endpoint
(POST https://openrouter.ai/api/v1/audio/speech). The OpenRouter key is NOT read
from anywhere in chat: pass --key-file <file> (e.g. a file on the learner's computer),
or set OPENROUTER_API_KEY, or rely on an API credential the agent proxy attaches.

Cache: every clip is content-addressed.
    key = sha1(model \\n voice \\n text)[:16]
The manifest (audio_cache.json) maps key -> {model, voice, text, chars, file,
assets: {<artifact url>: {id, url}}}. A job whose key is already in the manifest is never sent to
the API again — not for another word with the same text, not on the next
run. The mp3 bytes live in the artifact's asset store (asset_id/url); the local
mp3 file is only a staging copy for upload.

Commands
  jobs    build jobs.json from prepared words (say/ipa/tip) + the unit store
          (clips: phrase, example, and example2… from each word's more_examples)
  plan    show which jobs are cached / new, characters and estimated cost
  run     generate only the new clips (respects --max-chars budget)
  pack    convert mp3 -> audio-only .mp4 (AAC): the artifact asset store takes mp4, not mp3
  attach  record uploaded asset urls/ids in the manifest (per artifact)
  docs    write audio docs for an artifact's db collection `audio` (per word, or --per-unit)
"""
import argparse, concurrent.futures as cf, datetime as dt, glob, hashlib, json, os, re, sys, time

API = "https://openrouter.ai/api/v1/audio/speech"
MODELS_API = "https://openrouter.ai/api/v1/models?output_modalities=speech"
# USD per input character (OpenRouter pricing.prompt, checked 2026-10-08); used when the live price list is unreachable
FALLBACK_PRICE = {
    "elevenlabs/eleven-v4": 0.00004, "elevenlabs/eleven-v4-turbo": 0.00002,
    "elevenlabs/eleven-v3": 0.00004, "elevenlabs/eleven-multilingual-v2": 0.00004,
    "elevenlabs/eleven-flash-v2.5": 0.00002, "elevenlabs/eleven-turbo-v2.5": 0.00002,
}


def norm_text(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def clip_key(model, voice, text):
    return hashlib.sha1(f"{model}\n{voice}\n{norm_text(text)}".encode()).hexdigest()[:16]


def load_json(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def load_manifest(p):
    m = load_json(p, None) or {"version": 2, "entries": {}}
    m.setdefault("entries", {})
    for e in m["entries"].values():  # v1 -> v2: one upload per artifact under e["assets"]
        if e.get("url") and e.get("artifact"):
            e.setdefault("assets", {})[e["artifact"]] = {"id": e.get("asset_id"), "url": e["url"]}
        for k in ("url", "asset_id", "artifact", "upload_file"):
            e.pop(k, None)
    m["version"] = 2
    return m


def asset_of(e, artifact):
    return (e.get("assets") or {}).get(artifact)


def auto_say(phrase):
    """Fallback speakable text when no `say` was prepared (grammar patterns should always get one)."""
    s = phrase
    s = re.sub(r"\bsb's\b", "someone's", s)
    s = re.sub(r"\bsb\b", "someone", s)
    s = re.sub(r"\bsth\b", "something", s)
    s = re.sub(r"\bone's\b", "your", s)
    s = s.replace("(", "").replace(")", "")
    s = re.sub(r"\s*/\s*", ". ", s)
    s = re.sub(r"\s*\.\.\.\s*|\s*…\s*", " ", s)
    return norm_text(s)


# ---------------------------------------------------------------- commands
def cmd_jobs(a):
    words = {}
    for f in sorted(glob.glob(os.path.join(a.units_dir, "*.json"))):
        d = load_json(f, {})
        d = d.get("data", d)
        for w in d.get("words", []):
            words[w["id"]] = dict(w, unitNo=d.get("no"), unitTitle=d.get("title"))
    prep = load_json(a.prep, [])
    voices = [v.strip() for v in a.voices.split(",") if v.strip()]
    out = {"model": a.model, "voices": voices, "default_voice": voices[0], "words": [], "jobs": []}
    for p in prep:
        w = words.get(p["id"])
        if not w:
            print(f"! unknown word id {p['id']}", file=sys.stderr)
            continue
        say = norm_text(p.get("say") or auto_say(w["phrase"]))
        say_ex = norm_text(p.get("say_example") or w.get("example") or "")
        # extra example sentences live on the unit word as more_examples: [{example, answer, say?}]
        # → clips "example2", "example3", … (text = its optional `say`, else the sentence itself)
        more = [norm_text(m.get("say") or m.get("example") or "") for m in (w.get("more_examples") or [])]
        out["words"].append({**{k: w.get(k) for k in ("id", "phrase", "definition", "ru", "example", "answer", "type", "kind", "source", "unitNo", "unitTitle", "lessons", "more_examples")},
                             "say": say, "say_example": say_ex, "ipa": p.get("ipa", ""), "tip": p.get("tip", "")})
        for v in voices:
            out["jobs"].append({"word": w["id"], "clip": "phrase", "voice": v, "text": say})
            if say_ex:
                out["jobs"].append({"word": w["id"], "clip": "example", "voice": v, "text": say_ex})
            for i, t in enumerate(more):
                if t:
                    out["jobs"].append({"word": w["id"], "clip": f"example{i + 2}", "voice": v, "text": t})
    for j in out["jobs"]:
        j["model"] = a.model
        j["key"] = clip_key(a.model, j["voice"], j["text"])
    save_json(a.out, out)
    print(f"{len(out['words'])} words × {len(voices)} voices → {len(out['jobs'])} clips → {a.out}")


def price_per_char(model):
    try:
        import requests
        r = requests.get(MODELS_API, timeout=15)
        for m in r.json().get("data", []):
            if m.get("id") == model:
                return float(m["pricing"]["prompt"]), "live"
    except Exception:
        pass
    return FALLBACK_PRICE.get(model, 0.00004), "fallback"


def split_jobs(jobs, man):
    seen, new, cached = set(), [], []
    for j in jobs:
        if j["key"] in seen:
            continue
        seen.add(j["key"])
        (cached if j["key"] in man["entries"] else new).append(j)
    return new, cached


def cmd_plan(a):
    J = load_json(a.jobs, {})
    man = load_manifest(a.manifest)
    new, cached = split_jobs(J["jobs"], man)
    chars = sum(len(j["text"]) for j in new)
    ppc, src = price_per_char(J["model"])
    print(f"clips: {len(new) + len(cached)} unique · cached {len(cached)} · new {len(new)}")
    print(f"new characters: {chars} · est. cost ${chars * ppc:.3f} ({J['model']} @ ${ppc * 1000:.3f}/1k chars, {src} price)")
    return new


def tts(job, api_key, retries=4):
    import requests
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": job["model"], "input": job["text"], "voice": job["voice"], "response_format": "mp3"}
    delay = 2
    for attempt in range(retries + 1):
        r = requests.post(API, headers=headers, json=body, timeout=120)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("audio") and len(r.content) > 1500:
            return r.content, r.headers.get("x-generation-id")
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(delay); delay *= 2; continue
        raise RuntimeError(f"HTTP {r.status_code} {ctype}: {r.text[:300]}")


def cmd_run(a):
    J = load_json(a.jobs, {})
    man = load_manifest(a.manifest)
    new, _ = split_jobs(J["jobs"], man)
    budget = a.max_chars
    todo, spent = [], 0
    for j in new:
        if spent + len(j["text"]) > budget:
            print(f"! budget of {budget} chars reached; {len(new) - len(todo)} clips left for next run")
            break
        todo.append(j); spent += len(j["text"])
    if not todo:
        print("nothing to generate — every clip is already cached ✔")
        return
    os.makedirs(a.out_dir, exist_ok=True)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if a.key_file:  # read by the script itself; never printed
        with open(os.path.expanduser(a.key_file)) as kf:
            api_key = kf.read().strip()
    ok = fail = 0

    def one(j):
        audio, gen = tts(j, api_key)
        path = os.path.join(a.out_dir, j["key"] + ".mp3")
        with open(path, "wb") as f:
            f.write(audio)
        return j, path, len(audio), gen

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, j) for j in todo]
        for fu in cf.as_completed(futs):
            try:
                j, path, n, gen = fu.result()
            except Exception as e:
                fail += 1
                print(f"✗ {e}", file=sys.stderr)
                continue
            man["entries"][j["key"]] = {"model": j["model"], "voice": j["voice"], "text": j["text"], "chars": len(j["text"]),
                                        "file": os.path.basename(path), "bytes": n, "gen_id": gen,
                                        "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
            save_json(a.manifest, man)  # persist after every clip: a crash never loses paid audio
            ok += 1
    print(f"generated {ok} clips ({spent} chars), failed {fail} → {a.out_dir}")
    if fail:
        sys.exit(2)


def cmd_pack(a):
    import subprocess
    man = load_manifest(a.manifest)
    os.makedirs(a.out_dir, exist_ok=True)
    wanted = {j["key"] for j in load_json(a.jobs, {}).get("jobs", [])} if a.jobs else None
    n = missing = 0
    for k, e in man["entries"].items():
        if (wanted is not None and k not in wanted) or asset_of(e, a.artifact):
            continue  # not needed here, or already uploaded to this artifact
        src, dst = os.path.join(a.mp3_dir, e["file"]), os.path.join(a.out_dir, k + ".mp4")
        if not os.path.exists(src):
            missing += 1; continue
        if not os.path.exists(dst):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-c:a", "aac", "-b:a", "96k",
                            "-movflags", "+faststart", dst], check=True)
        n += 1
    save_json(a.manifest, man)
    print(f"{n} clips ready to upload to {a.artifact} in {a.out_dir}" + (f"; {missing} mp3 missing locally" if missing else ""))


def cmd_attach(a):
    """uploads.json: [{"file": "<key>.mp4", "id": "...", "url": "...", "bytes": n?}] from the Artifact upload results."""
    man = load_manifest(a.manifest)
    n = bad = 0
    for u in load_json(a.uploads, []):
        key = os.path.splitext(os.path.basename(u["file"]))[0]
        e = man["entries"].get(key)
        if not e:
            print(f"! {key} not in manifest", file=sys.stderr); bad += 1; continue
        local = os.path.join(a.upload_dir, key + ".mp4")
        if u.get("bytes") and os.path.exists(local) and os.path.getsize(local) != int(u["bytes"]):
            print(f"! {key}: uploaded {u['bytes']} bytes but local file has {os.path.getsize(local)}", file=sys.stderr); bad += 1; continue
        e.setdefault("assets", {})[a.artifact] = {"id": u["id"], "url": u["url"]}
        n += 1
    save_json(a.manifest, man)
    print(f"attached {n} to {a.artifact}; problems: {bad}")
    if bad:
        sys.exit(2)


def cmd_docs(a):
    J = load_json(a.jobs, {})
    man = load_manifest(a.manifest)
    os.makedirs(a.out_dir, exist_ok=True)
    byword = {}
    for j in J["jobs"]:
        e = man["entries"].get(j["key"])
        up = e and asset_of(e, a.artifact)
        if not up:
            continue
        byword.setdefault(j["word"], {}).setdefault(j["voice"], {})[j["clip"]] = {"url": up["url"], "key": j["key"]}
    meta = {w["id"]: w for w in J["words"]}
    today = dt.date.today().isoformat()
    n = 0
    if a.per_unit:  # one doc per unit: audio/u<N> = {unit, model, words: {id: {...}}}
        units = {}
        for w in J["words"]:  # every prepared word: IPA/tips show even while its clips are still pending
            clips = byword.get(w["id"], {})
            units.setdefault(w["unitNo"], {})[w["id"]] = {"say": w["say"], "say_example": w["say_example"], "ipa": w["ipa"], "tip": w["tip"], "clips": clips}
        for no, ws in sorted(units.items()):
            save_json(os.path.join(a.out_dir, f"u{no}.json"), {"unit": no, "model": J["model"], "words": ws, "updated": today}); n += 1
        pending = len(J["words"]) - len(byword)
        print(f"{n} unit audio docs ({len(byword)} words with clips, {pending} pending) → {a.out_dir}")
        return
    for wid, clips in byword.items():
        w = meta[wid]
        doc = {"word": wid, "say": w["say"], "say_example": w["say_example"], "ipa": w["ipa"], "tip": w["tip"],
               "model": J["model"], "clips": clips, "updated": today}
        save_json(os.path.join(a.out_dir, wid + ".json"), doc); n += 1
    print(f"{n} audio docs → {a.out_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("jobs"); p.add_argument("--prep", required=True); p.add_argument("--units-dir", required=True)
    p.add_argument("--voices", default="eric"); p.add_argument("--model", default="elevenlabs/eleven-v4"); p.add_argument("--out", default="jobs.json")
    p = sp.add_parser("plan"); p.add_argument("--jobs", default="jobs.json"); p.add_argument("--manifest", default="audio_cache.json")
    p = sp.add_parser("run"); p.add_argument("--jobs", default="jobs.json"); p.add_argument("--manifest", default="audio_cache.json")
    p.add_argument("--out-dir", default="mp3"); p.add_argument("--max-chars", type=int, default=20000); p.add_argument("--workers", type=int, default=4)
    p.add_argument("--key-file", default="", help="file containing the OpenRouter key (else OPENROUTER_API_KEY / proxy credential)")
    p = sp.add_parser("pack"); p.add_argument("--manifest", default="audio_cache.json"); p.add_argument("--mp3-dir", default="mp3"); p.add_argument("--out-dir", default="upload")
    p.add_argument("--artifact", required=True); p.add_argument("--jobs", default="", help="only clips used by this jobs file")
    p = sp.add_parser("attach"); p.add_argument("--manifest", default="audio_cache.json"); p.add_argument("--uploads", required=True)
    p.add_argument("--artifact", required=True); p.add_argument("--upload-dir", default="upload")
    p = sp.add_parser("docs"); p.add_argument("--jobs", default="jobs.json"); p.add_argument("--manifest", default="audio_cache.json"); p.add_argument("--out-dir", default="audio_docs")
    p.add_argument("--artifact", required=True); p.add_argument("--per-unit", action="store_true")
    a = ap.parse_args()
    {"jobs": cmd_jobs, "plan": cmd_plan, "run": cmd_run, "pack": cmd_pack, "attach": cmd_attach, "docs": cmd_docs}[a.cmd](a)


if __name__ == "__main__":
    main()
