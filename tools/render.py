#!/usr/bin/env python3
"""Render the Vocab Garden kit for one learner.

    python3 tools/render.py config.json build/            # everything (needs ARTIFACT_URL)
    python3 tools/render.py config.json build/ --only page  # just the quiz page (before the artifact exists)

Output:
    build/vocab-garden.html          -> publish as the quiz artifact (capabilities: db, assets)
    build/vocab/*.md, *.py, state.json -> upload to the learner's Claude project under vocab/
    build/project_instructions.md    -> the learner pastes it into the project's custom instructions

Every {{KEY}} in a template must have a non-empty value in config.json, otherwise nothing is written for that file
and the script exits 1 listing what is missing.
"""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PH = re.compile(r"\{\{([A-Z_]+)\}\}")
SAFE = re.compile(r'^[^<>"\\`\n]*$')
CHECKS = {
    "ARTIFACT_URL": re.compile(r"^https://claude\.ai/(code/)?artifact/[A-Za-z0-9_-]+$"),
    "VOICE": re.compile(r"^[a-z][a-z0-9_-]*$"),
}

PAGE = [("page/vocab-garden.template.html", "vocab-garden.html")]
KIT = [(f"kit/{n}", f"vocab/{n}") for n in ("RUNBOOK.md", "examples_rules.md", "pron_prep_rules.md", "AUDIO.md")] + \
      [("kit/state.template.json", "vocab/state.json"), ("kit/project_instructions.md", "project_instructions.md")]
COPY = [(f"kit/{n}", f"vocab/{n}") for n in ("vocab_merge.py", "examples_check.py", "tts_cache.py")]


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__); return 2
    cfg_path, out = args[0], args[1]
    only_page = "--only" in args and args[args.index("--only") + 1] == "page"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    bad = []
    for k, v in cfg.items():
        if not isinstance(v, str) or not SAFE.match(v):
            bad.append(f"{k}: must be a plain string without < > \" \\ ` or newlines")
        elif v and k in CHECKS and not CHECKS[k].match(v):
            bad.append(f"{k}: {v!r} does not look right")
    if bad:
        print("config problems:\n  " + "\n  ".join(bad)); return 1
    jobs = PAGE + ([] if only_page else KIT)
    missing_all = set()
    for src, dst in jobs:
        text = open(os.path.join(ROOT, src), encoding="utf-8").read()
        keys = set(PH.findall(text))
        missing = sorted(k for k in keys if not cfg.get(k))
        if missing:
            missing_all.update(missing); print(f"skip {dst}: missing {', '.join(missing)}"); continue
        is_json = dst.endswith(".json")
        text = PH.sub(lambda m: json.dumps(cfg[m.group(1)])[1:-1] if is_json else cfg[m.group(1)], text)
        path = os.path.join(out, dst); os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)
        print(f"wrote {path}")
    if not only_page:
        for src, dst in COPY:
            path = os.path.join(out, dst); os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, src), path); print(f"copied {path}")
        for name, empty in (("pron_prep.json", []), ("audio_cache.json", {"version": 2, "entries": {}})):
            path = os.path.join(out, "vocab", name)
            if not os.path.exists(path):
                json.dump(empty, open(path, "w"), indent=1); print(f"wrote {path}")
    if missing_all:
        print("fill these in config.json and run again: " + ", ".join(sorted(missing_all))); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
