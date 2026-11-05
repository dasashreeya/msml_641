# Work split

Team: **Shreeya Dasa Lakshminath**, **Rachel Bubeck**, **Teammate 3 (name TBD)**.

The project builds on the existing pipeline, data and results: no new datasets, **no
retraining**, no GPU, and no re-downloading the training data. The models are already
trained. The remaining work goes deeper on what exists:

| Task | Owner | What | Estimated effort |
|---|---|---|---|
| Completed | Shreeya | Pipeline, baselines, fine-tuning, held-out evaluation, system combination | done |
| Task 0 | Rachel, Teammate 3 | Setup and smoke test (Teammate 3 also downloads the 16 MB dev set) | ~1–2 h |
| Task B | Rachel | Error analysis of the existing systems | ~10–15 h over 4 weeks |
| Task C | Teammate 3 | Better decoding settings for the existing models (no training) | ~8–10 h hands-on, plus ~3–4 h of unattended laptop CPU time |
| Report and slides | Everyone | Each writes their own sections | shared |

Effort figures are estimates. The CPU time is measured: one full decode of the dev set
took 15–26 min on a MacBook (`decode_seconds` in `reports/baselines/*.json`: zero-shot
turbo 928 s, turbo with prompt 1,539 s, `ft-g7` with prompt 1,462 s).

## Timeline

| Date | Milestone |
|---|---|
| Sun Nov 8 | Task 0 done by Rachel and Teammate 3; smoke-test WERs posted in the group chat |
| Sun Nov 15 | B1 metrics module merged; C1 tuning protocol written |
| Sun Nov 22 | B2 analysis numbers; C2 decoding comparison done |
| Sun Nov 29 | B3 taxonomy and figures; C3 combination; everyone's report sections drafted |
| Tue Dec 1 | Full report draft and slides; everyone reviews the whole document |
| Thu Dec 3 / Dec 10 | Presentation (whichever slot we get); final report and repository link on ELMS |

---

## Shreeya: completed

Everything in `docs/PRIOR_WORK.md`, with its results in `reports/`:

- **Data pipeline:** download and verification, data audit (`reports/data_audit.json`),
  Bangor CHAT conversion and segmentation into training clips (S2 and the dev-length G7
  variant).
- **Zero-shot baselines** (`reports/baselines/`):
  - Whisper large-v3-turbo and large-v3 with `--language` set to auto, en and es;
  - Qwen3-ASR 0.6B and 1.7B;
  - a CTC model;
  - Whisper with a code-switched prompt.
- **Fine-tuning** Whisper large-v3-turbo on Bangor (`ft-s2`, `ft-g7`, `ft-g7sd`) on Modal
  A100s (`reports/finetune/`).
- **Held-out evaluation:** 5-fold clip cross-validation plus speaker-held-out folds
  (`reports/baselines/kfold-d2-*`, `reports/finetune/kfold-d2.score.json`).
- **System combination:** MBR selection, ROVER, sentence-break and convention fixes
  (`reports/baselines/r3*`, `r4*`, `mbr-*`, `rover-*`).
- **Diagnostics:** per-speaker splits, error categories, transcription-convention rates,
  switch density.

Shreeya also does a one-time handover of the shared inputs below and answers questions
about the existing code.

## Shared inputs (one-time handover from Shreeya)

These contain Data-derived material, so they are shared **privately within the team**
(a shared Drive folder), never committed, uploaded elsewhere or posted in chat. Both
target paths are already gitignored.

| What | Size | Put it at | Needed by |
|---|---|---|---|
| Fine-tuned model `ft-g7` (CTranslate2: `model.bin`, `config.json`, tokenizer files) | ~1.6 GB | `artifacts/models/ft-g7/` | Task C |
| Existing predictions: `<run>.csv` and `<run>.reference.csv` for every run, **excluding the 4 `ger*` files** | ~4 MB | `data/interim/predictions/` | Tasks B and C |
| English/Spanish word lexicon `bangor_lexicon.json` (6,355 words from Bangor's CHAT language tags) | ~110 KB | `data/processed/bangor_lexicon.json` | Task B |

Each prediction pair has the columns `audio_filename,transcript`: the system's output in
`<run>.csv` and the matching reference transcripts in `<run>.reference.csv`.

**Nobody needs to download the Bangor Miami corpus.** The models were already trained on
it, and the lexicon above is the only part the remaining work uses. The corpus has also
been removed from Mozilla Data Collective (its API returns `410 Dataset no longer
available` as of Nov 2026; see `docs/DATA.md`).

---

## Task 0: setup (Rachel and Teammate 3, by Sun Nov 8)

1. Install [`uv`](https://docs.astral.sh/uv/) and `ffmpeg` (macOS:
   `brew install uv ffmpeg`).
2. Clone and install:
   ```sh
   git clone https://github.com/dasashreeya/msml_641.git && cd msml_641
   uv sync --extra audit --extra dev --extra prep --extra baseline
   uv run pytest -q          # expect: all passed, a few skipped
   ```
3. Copy the shared inputs into place (table above).
4. **Teammate 3 only:** create a free account at https://mozilladatacollective.com and
   download and ingest the **dev set** (~16 MB) as described in `docs/DATA.md`. Task C
   re-decodes the dev audio, so it needs the clips. Rachel needs no download: Task B
   works from the shared predictions, which already contain the references.
5. Smoke test:
   - **Rachel**, which reads the shared predictions only:
     ```sh
     uv run python scripts/compare_runs.py --output reports/baselines/smoke-rachel.json \
         large-v3-turbo-auto-int8-b5 large-v3-turbo-auto-int8-b5-prompt
     ```
   - **Teammate 3**, which decodes 10 dev clips on CPU in a few minutes:
     ```sh
     uv run python scripts/whisper_baseline.py --model large-v3-turbo --language auto \
         --limit 10 --run-name smoke-<yourname>
     ```
   Post that it ran (and Teammate 3's WER) in the group chat.
6. Read `docs/PRIOR_WORK.md` and skim `reports/baselines/comparison-*.json` to see what
   has been measured.

**Done when:** tests pass, the shared inputs are in place, Teammate 3 has the dev set
ingested, and both smoke tests run.

---

## Task B: error analysis of the existing systems (Rachel)

**Why.** The existing results report one number per system: WER. That doesn't say
*where* systems fail. In code-switched speech the interesting question is what happens
at a language switch, and which language suffers more. This task answers that, and it is
the core NLP analysis in the report.

**Systems to analyse.** These predictions already exist, so no decoding is needed:

| Label in the report | Run name in `data/interim/predictions/` |
|---|---|
| Zero-shot Whisper turbo | `large-v3-turbo-auto-int8-b5` |
| Whisper turbo + prompt | `large-v3-turbo-auto-int8-b5-prompt` |
| Zero-shot Qwen3-ASR 1.7B | `Qwen3-ASR-1.7B-auto-cpu-float32` |
| Fine-tuned Whisper (G7) + prompt | `ft-g7-turbo-auto-int8-b5-prompt` |
| Best system combination | `r3c-M11b` (also `r4-M13-rover5`) |
| Fine-tuned on held-out folds | `kfold-d2-heldout-breaks` |

### B1. Metrics module (by Sun Nov 15, ~4–7 h)

Create `src/lit_sp_en/metrics.py` and `tests/test_metrics.py`.

1. **CER** (character error rate) on normalized text. Normalize with
   `lit_sp_en.transcripts.normalize_text` (the same normalization WER uses), then
   compute a character-level error rate. `jiwer.cer` works, and jiwer is already
   installed.
2. **Per-language WER.** Label each reference word `eng` or `spa` using the shared
   lexicon `data/processed/bangor_lexicon.json`. Its `lexicon` key maps lowercase words to
   `eng`/`spa`; it was built with `build_lexicon` in `scripts/audit_data.py` (around line
   500), and `lexicon_mix` there shows how words are tokenized and looked up:
   - align reference and hypothesis with jiwer (`jiwer.process_words`), then count
     errors on reference words of each language;
   - report words the lexicon doesn't cover as `unknown`, along with the lexicon's
     coverage.
3. **Switch-point error rate.** A switch point is a pair of neighbouring reference words
   with different language labels. Count errors on reference words within ±1 word of a
   switch point, and compare that rate with the rate on all other words.
4. **Confidence intervals.** Wrap each metric with the existing bootstrap:
   `bootstrap_interval` and `paired_bootstrap` in `src/lit_sp_en/evaluation.py`.
5. **Tests.** Write small hand-made examples with known answers: one substitution, one
   switch, an empty hypothesis, and a word the lexicon doesn't know.

### B2. Run it on the existing systems (by Sun Nov 22, ~2–3 h)

Write `scripts/analyze_errors.py`.

- It reads each `<run>.csv` and `<run>.reference.csv` pair for the systems in the table.
- It writes `reports/error_analysis.json` with **aggregates only**: one entry per system
  with WER, CER, per-language WER, switch vs. non-switch error rate, and 95% intervals.
- Call `assert_no_transcript_leak` (from `scripts/audit_data.py`) on the output before
  writing it, as the other scripts do.
- Copy the structure of `scripts/compare_runs.py`, which already loads prediction CSVs
  and writes aggregate JSON.

### B3. Error taxonomy and figures (by Sun Nov 29, ~3–5 h)

1. Take about 50 errors from the best system (the combination run) and hand-label each:
   - wrong-language substitution (a Spanish word written as an English one, or the
     reverse);
   - translation instead of transcription;
   - word dropped at a switch;
   - name or proper noun;
   - filler or hesitation (uh, eh, um);
   - other.

   Keep the labelling sheet **local** (it contains transcript text) and commit only the
   counts.
2. `scripts/error_categories.py` already counts formatting-only errors (case, accents,
   fillers). Extend it or cite its output rather than recounting.
3. Make 3–4 figures with matplotlib (`uv add --optional dev matplotlib` adds it) and save
   them under `reports/figures/`:
   - WER and CER per system, with intervals;
   - per-language WER per system;
   - switch vs. non-switch error rate;
   - taxonomy counts.

**Deliverables:** `metrics.py` with tests, `analyze_errors.py`,
`reports/error_analysis.json`, figures, and the report sections (introduction, related
work, error analysis).

**Done when:** `uv run pytest -q` passes; the JSON covers all six systems; the figures
come out of a script, not by hand.

---

## Task C: better decoding for the existing models, no training (Teammate 3)

**Why.** The models are trained and stay as they are. Whisper's decoding settings
(prompt, beam size, voice-activity filtering, repetition penalty, language) can still
change accuracy. This task measures which settings help, using commands that already
exist.

### C1. Tuning protocol (by Sun Nov 15, ~1–2 h)

The rule is to pick settings on some clips and report on others, so no setting is chosen
on the clips it is scored on.

1. Regenerate the existing 5 clip folds. They come from a fixed seed, so this needs no
   extra files, and they match the folds the held-out results used:
   ```sh
   mkdir -p data/processed/folds
   uv run python -c "
   from pathlib import Path
   from scripts.prepare_dev_folds import clip_folds, SEED, FOLDS
   ids = [f'dev{i:03d}' for i in range(155)]
   for n, fold in enumerate(clip_folds(ids, FOLDS, SEED)):
       Path(f'data/processed/folds/clip{n}.txt').write_text('\n'.join(fold) + '\n')
   "
   ```
   This writes five files of 31 clip ids each. The folder is gitignored.
2. Write `docs/TUNING_PROTOCOL.md`, **before running anything**:
   - **tuning set:** folds 0–2 (93 clips); **report set:** folds 3–4 (62 clips);
   - the list of settings you will try (C2);
   - the selection rule, e.g. "lowest tuning WER; ties go to the simpler setting".

### C2. Compare decoding settings (by Sun Nov 22, ~4–5 h hands-on plus CPU time)

Run each setting on the **tuning** clips. One example, the fine-tuned model with a beam
size of 8:

```sh
cat data/processed/folds/clip{0,1,2}.txt > data/processed/folds/tune.txt
uv run python scripts/whisper_baseline.py --model artifacts/models/ft-g7 --language auto \
    --initial-prompt "<prompt>" --beam-size 8 --ids @data/processed/folds/tune.txt \
    --run-name c2-ftg7-beam8
```

Settings to compare, changing **one at a time** from the existing `ft-g7` + prompt
setup:

| Setting | Values | Flag |
|---|---|---|
| Prompt | 2–3 short mixed Spanish–English sentences | `--initial-prompt` |
| Beam size | 1, 5 (current), 8 | `--beam-size` |
| Voice-activity filter | off (current), on | `--vad-filter` |
| Repetition penalty | none (current), 1.1 | `--repetition-penalty` |
| Temperature fallback | on (current), off | `--no-temperature-fallback` |
| Language | auto (current), en, es | `--language` |

That's about 10 runs of 15–25 minutes each, which can run back to back unattended
(`--threads` controls CPU use). Compare each run with the current setting on the same
clips:

```sh
uv run python scripts/compare_matched.py c2-ftg7-beam8 <baseline-run-on-tune-clips>
```

The baseline is the current setting re-run on the tuning clips. Then pick the best
setting by your rule and run it **once** on the report folds (3–4).

### C3. System combination with the improved runs (by Sun Nov 29, ~2–3 h)

1. Combine the best new `ft-g7` run with the existing Qwen runs:
   ```sh
   uv run python scripts/combine_runs.py --name c3-mbr --method mbr <run> <run> ...
   ```
   Also try `--method rover-backbone`.
2. Check that the gain holds for both speakers:
   `uv run python scripts/speaker_split.py --candidate <run> --incumbent <run>`.

**Deliverables:** `docs/TUNING_PROTOCOL.md`, a results table (setting → tuning WER →
report-fold WER with interval), and the "decode-time improvements" report section.
Settings that made no difference are results too; report them.

**Done when:** every number in the table points to a file in `reports/baselines/`, and
the final setting was chosen on the tuning folds only.

---

## Report sections

| Section | Writer |
|---|---|
| Introduction, motivation, related work | Rachel |
| Data and preprocessing; models; baseline and fine-tuning results (from `reports/`) | Shreeya |
| Error analysis (Task B) | Rachel |
| Decode-time improvements (Task C) | Teammate 3 |
| Conclusion, limitations, future work | Everyone |

Every number in the report should point to a file in `reports/`.

## How we work

- Pull before starting: `git pull`. One branch per task: `task-b-error-analysis`,
  `task-c-decoding`.
- Open a pull request into `main`; another teammate reviews it.
- Run `uv run pytest -q` before opening a pull request.
- Never commit, upload or paste audio, transcripts, clip names or the shared inputs. Only
  aggregates go into `reports/` (`docs/DATA.md`).
- Blocked for more than a day? Say so in the group chat.
