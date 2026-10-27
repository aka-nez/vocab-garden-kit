# Example sentences — rules (Vocab Garden)

{{LEARNER_NAME}} ({{LEARNER_PROFILE}}) learns English phrases with a spaced-repetition quiz. Every word has
**5 example sentences**: `example` + 4 in `more_examples`. The quiz shows one at a time (shuffle-bag: all 5 before
any repeats, never the same twice in a row), blanks out its `answer` for fill-the-gap, shows a small
"form · context" label (hidden on gap-fill questions), and the TTS voice "{{VOICE}}" (American English) reads it
aloud. The point is to meet the phrase in **different situations and different grammar forms** — never five
near-copies of one sentence.

## New words (enriched.json)
For each new word write all 5 sentences, planned together:
```
{ ...candidate fields, "ru": "<{{NATIVE_LANG}} translation>", "inflects": true|false,
  "example": "...", "answer": "...", "example_form": "...", "example_context": "...",
  "more_examples": [ {"example": "...", "answer": "...", "form": "...", "context": "..."} × 4 ] }
```
(The field is called `ru` for historical reasons; it always holds the {{NATIVE_LANG}} translation.)
Plan first: pick 5 different contexts and 5 different forms (base forms for inflecting phrases), then write.
Check with `python3 vocab_merge.py check --fresh enriched.json` until it prints OK (`apply` runs the same check).

## Translation (`ru`)
A natural {{NATIVE_LANG}} equivalent, short. For an idiom: the closest {{NATIVE_LANG}} idiom, or the plain meaning
if there is none. Not a dictionary entry, not a word-by-word gloss.

## Labels
**context** — exactly one of: work, tech, money, shopping, travel, home, family, friends, relationships, food,
health, sport, city, nature, animals, study, entertainment, weather, celebrations, news.
All 5 sentences of a word use different contexts.

**form** — short lowercase label (≤ 4 words) of how the PHRASE itself is used:
- If the phrase contains a verb that can change (`inflects: true`): its tense/form —
  present simple, present continuous, past simple, past continuous, present perfect, present perfect continuous,
  past perfect, will future, going to, modal (can/could/should/must/might/would + verb), conditional (inside an
  if-clause or a would-clause), imperative, infinitive (to + verb after another verb), -ing form (gerund),
  passive, used to. You may add " question" or " negative" (e.g. "present perfect question").
  The 5 BASE forms (without question/negative) must all differ, and the 5 answers must show at least 3 different
  word forms. Prefer common, useful forms (past simple, present perfect, will/going to, continuous, modal,
  conditional, imperative) before rare ones.
- If it does not (`inflects: false`: nouns, adjectives, adverbs, fixed expressions like "once in a blue moon"):
  vary its role instead — e.g. singular, plural, as subject, as object, after a preposition, before a noun,
  after be, comparative, in a question, in a negative, sentence start, sentence end, in reported speech.
  All 5 labels differ.
- `type: grammar` items: keep the taught pattern in every sentence; vary the situation and the sentence around it
  (statement / question / negative / past context / future context).

## Sentences
- Natural, everyday American English, 8–20 words, one sentence (two short ones only if really needed), ending
  with `.`, `!` or `?`. Clear enough that the meaning of the phrase can be guessed from context.
- Use the phrase with the meaning in `definition` / `ru`. Alternatives ("pig out on sth / gorge yourself on sth"):
  one sentence may use a different variant.
- Each sentence is a genuinely different scene: different people, place, objects and nouns, different opening
  words. Not a paraphrase. Don't reuse the same subject ("My sister…") or the same first three words.
- Speakable as written: numbers as words, no digits, no abbreviations (e.g., etc., sb, sth), no slashes, brackets,
  quotation marks or emoji. No contracted auxiliary inside or right before the answer (write "has taken", not
  "'s taken"). Other contractions are fine.
- Nothing offensive, no real public figures, no brand-heavy text. Vary names and people (not always boss/colleague).
- Situations may lean towards the learner's life ({{LEARNER_PROFILE}}) but must stay varied.

## Answer (what the learner types into the gap)
- An exact, case-sensitive substring of the sentence, occurring once, without final punctuation.
- The phrase as used, inflected. Include a tense auxiliary (have/has/had, will, am/is/are/was/were, been,
  going to) when it stands DIRECTLY before the phrase — that is how the gap teaches the tense. Never include
  modals (should/could…), subjects or adverbs; if an adverb would split auxiliary and verb, move the adverb.
- Slot words (sb/sth) get real words; include a filler only when it sits between fixed words.

## Self-review before saving
Read each word's 5 sentences together, as a teacher would: no two with the same kind of scene or idea, labels
match the sentences (a "present perfect" label really is present perfect), the meaning matches `definition`.

## Checks (automatic)
`examples_check.py` (used by `vocab_merge.py check/apply`) flags: labels outside the lists, repeated contexts or
forms, answers that don't occur exactly once, length, digits/abbreviations/brackets, contracted auxiliary before
the answer, modal inside the answer, too few answer forms for inflecting phrases, and near-duplicates between any
two sentences of a word (shared content words > 40%, similar wording > 0.55, same first three words).

## Backfilling extra sentences for words that already exist (optional tool)
`examples_check.py in.json out.json [--new N]` — in: `[{id, phrase, definition, type, examples:[{example, answer}]}]`,
out: `[{id, inflects, tags:[{form, context}] (one per existing sentence), new:[{example, answer, form, context} × N]}]`.
Existing sentences are kept unchanged; only labels are added to them. Useful if words were ever imported with
fewer than 5 sentences.
