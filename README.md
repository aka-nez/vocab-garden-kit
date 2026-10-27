# Vocab Garden kit

A spaced-repetition English vocabulary garden you grow by just messaging Claude — built entirely on claude.ai
(a project + an artifact with its own database), no server.

You send new words to Claude in a dedicated project chat — typed, pasted lesson notes, a photo of your notebook,
or a CSV/Anki export. For each new phrase Claude:
1. drops what you already have,
2. writes a translation into your language and **five example sentences** — each in a different situation and
   grammar form, with a gap-fill answer,
3. voices the phrase and all five sentences with an American ElevenLabs voice (via OpenRouter) — paid once per clip,
   cached forever,
4. adds everything to your **Vocab Garden**: a private quiz page with its own database.

![Vocab Garden in 28 seconds: send words, enrich, listen, practise, grow](docs/vocab-garden-features.gif)

<sub>Same animation as [MP4](docs/vocab-garden-features.mp4) · source in [`docs/motion`](docs/motion)</sub>

**The quiz page:** six growth stages (Seed → Rooted) on a 1/3/7/16/40-day schedule; Smart mix that moves from
recognition (pick the meaning) to recall (translation → English, fill the gap, by ear); "What did you hear?" audio
mode; flashcards; five rotating example sentences per word with "form · context" labels; IPA and sound tips for your
native language's traps; "I know this" to retire words; daily streak; filters by unit, corrections and grammar
patterns; progress synced across devices through the artifact database. Keyboard-friendly, phone-first, light/dark.

## Set it up for someone

This repo is a **handoff for an agent**. In the learner's claude.ai account:

1. Create a Claude project (e.g. "English (Alex)").
2. Start a task in that project, attach or link this repo, and say:
   > Read HANDOFF.md and set up a Vocab Garden for me.
3. Answer one round of questions (name, native language, voice, how to group words, any existing list to import).
   Claude publishes the page, installs the kit into the project, imports your words, makes the audio (after you OK
   the cost) and gives you a short text to paste into the project's instructions.

From then on, in that project: "add: cut corners, a blessing in disguise", "take the phrases from this photo",
"new unit: Travel", "make audio for the new words".

Details and prerequisites: [`HANDOFF.md`](HANDOFF.md). The procedure Claude follows for every batch of words:
[`kit/RUNBOOK.md`](kit/RUNBOOK.md).

## Costs

- Claude: whatever plan the learner already has.
- Audio: OpenRouter TTS, ~$0.035 per word (six clips) at October 2026 prices — roughly $15–20 for a 500-word
  import, cents for a lesson's worth of words. `tts_cache.py plan` shows the exact figure before anything is spent.

## Repo layout

```
HANDOFF.md                       instructions for the setup agent
config.example.json              per-learner settings
page/vocab-garden.template.html  the quiz page (one self-contained file)
kit/                             runbook, rules, scripts and project instructions for the learner's Claude project
tools/render.py                  fills {{PLACEHOLDERS}} from config.json into build/
examples/                        two fully enriched demo words (data shape + smoke test)
docs/                            feature animation (GIF/MP4) and its source
```

Local smoke test (Python 3.9+; `requests` and `ffmpeg` only needed for audio):

```bash
python3 kit/vocab_merge.py check --fresh examples/enriched.demo.json   # → OK (2 items)
python3 tools/render.py config.example.json build --only page          # → build/vocab-garden.html
```

## Privacy

No keys or learner data are in this repo. The OpenRouter key stays in a file on the learner's computer and is only
read by the TTS script at run time. The quiz page and its database are private to the learner unless they share
the link.

## License

MIT — see [LICENSE](LICENSE).
