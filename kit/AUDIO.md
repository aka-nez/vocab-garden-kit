# Pronunciation audio (Vocab Garden)

Every word has six clips voiced by "{{VOICE}}" (American English): `phrase`, `example`, `example2` … `example5`
(the five example sentences). Cards show IPA and a sound tip; the quiz has a "What did you hear?" exercise (its own
mode, and part of Smart mix for words at Leafy stage or higher) and an Audio speed setting.
New words get their clips in the same run that adds them (RUNBOOK step 5).

- Provider: ElevenLabs voices through OpenRouter TTS: `POST https://openrouter.ai/api/v1/audio/speech`
  body `{model, input, voice, response_format:"mp3"}`. Model `{{TTS_MODEL}}`. `tts_cache.py plan` prints the
  live price before anything is paid: about $0.08 / 1k chars in Oct 2026, ≈ $0.035 per word with six clips
  (≈ 420 characters), so a 500-word first import costs roughly $15–20.
- Network: `openrouter.ai` must be in the learner's claude.ai Settings → Capabilities → Code execution →
  Additional allowed domains.
- Key: file `{{KEY_FILE}}` on the learner's computer. Connect that folder, stage the file, run
  `tts_cache.py run --key-file <staged path>`, then delete the staged copy. Never print it, never put it in the
  project, the page or a command line. Needs the computer awake with the Claude desktop app open; listening to
  the clips works anywhere.

## Cache (pay once)
- `vocab/tts_cache.py` — `jobs` → `plan` → `run` → `pack` → upload `upload/*.mp4` as artifact assets
  (Artifact publish, `asset: true`, ≤25 per call) → `attach --uploads uploads.json` → `docs` → db batch.
- The asset store rejects mp3, so `pack` converts each clip to audio-only MP4/AAC (plays on iPhone too).
- Clip key = sha1(model \n voice \n text)[:16]. `vocab/audio_cache.json` (v2) maps
  key → {model, voice, text, chars, file, assets: {<artifact url>: {id, url}}}. `run` skips every key already in
  the manifest, so the same text+voice is never sent twice.
- Moving clips to another artifact later: copy assets server-side (Artifact publish with `from_url` + `asset_ids`),
  no regeneration.
- Speakable text: `say` (phrase as read aloud: sb → someone, slashes split, grammar formulas → natural chunk),
  `say_example` only when the first example needs it (e.g. "20/20" → "twenty-twenty"). Prepared by Claude during
  enrichment (`vocab/pron_prep_rules.md`); `auto_say()` is the fallback.

## In the quiz database
- `audio/u<N>` = {unit, model, words: {id: {say, say_example, ipa, tip, clips: {{{VOICE}}: {phrase, example, example2…example5}}}}}, `meta/audio`.
- `vocab/pron_prep.json` = say/ipa/tip for every word.
- If the computer isn't reachable when words are added, they get IPA/tips now and their clips later, when the
  learner says "make audio for the new words" with the computer awake — the cache knows what's missing.

## Choosing a voice
Good American ElevenLabs voices on OpenRouter: eric (default), sarah, jessica. To audition, generate the same
3–4 phrases with each candidate (`--voices eric,sarah,jessica` on `jobs`), upload, and let the learner pick.
Changing the voice later means regenerating every clip (new cache keys) — pick once.
