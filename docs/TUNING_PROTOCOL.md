# Task C tuning protocol: decoding settings for `ft-g7`

Owner: Srinickethan (Teammate 3). Written before any Task C decode was run (C1,
`docs/WORK_SPLIT.md`). Nothing below changes once the first C2 run starts. If something
has to change, add a dated entry under **Deviations**, with the reason, and never edit
the rules in place.

## Goal

Find decoding settings that lower WER for the existing fine-tuned model `ft-g7`
(Whisper large-v3-turbo fine-tuned on Bangor G7) without retraining, and report the gain
on clips that were never used to choose it.

## Clip split

The 155 dev clips (`dev000`–`dev154`) are split into the 5 clip folds from
`scripts/prepare_dev_folds.py` (`clip_folds`, seed `20260920`, 31 clips each). These are
the same folds the k-fold held-out results used. Regenerate them with the snippet in
`docs/WORK_SPLIT.md` §C1, then:

```sh
cat data/processed/folds/clip{0,1,2}.txt > data/processed/folds/tune.txt
cat data/processed/folds/clip{3,4}.txt   > data/processed/folds/report.txt
```

| Set | Folds | Clips | Used for |
|---|---|---|---|
| **Tuning** | 0, 1, 2 | 93 | every comparison and every choice |
| **Report** | 3, 4 | 62 | scored **once**, for the final setting and the baseline only |

The fold files are gitignored (`data/`). The two sets don't overlap and together cover all
155 clips (checked when the folds were generated).

**Existing full-dev numbers are not used for selection.** Earlier runs such as
`ft-g7-turbo-auto-int8-b5-promptR1` and `-promptR2` were scored on all 155 clips,
including the report folds. They are background only. No setting is chosen or ruled out
because of them.

## Baseline (the "current" setting)

The existing `ft-g7` + prompt configuration, `reports/baselines/ft-g7-turbo-auto-int8-b5-prompt.json`:

| | |
|---|---|
| Model | `artifacts/models/ft-g7` (CTranslate2), faster-whisper 1.2.1 |
| Compute | CPU, `int8`, `--threads 8` |
| Language | `auto` |
| Beam size | 5 |
| Prompt (P0) | `Hola, ¿cómo estás? I'm good, gracias. Vamos a la tienda later, okay?` (SHA-256 `c44393b0…8321d`, same as the existing report) |
| VAD filter | off |
| Repetition penalty | none (1.0) |
| Temperature fallback | on (faster-whisper default) |
| Post-processing | none |

Held fixed for **every** run: model, `int8`, CPU, `--threads 8`, faster-whisper version,
no post-processing, and the official normalizer and scorer (`vendor/runtime_score.py`).
Only the one setting under test changes.

The baseline is **re-run** on the tuning clips (`c2-base`), and every setting is compared
against that re-run. As a reproducibility check, `c2-base` is also compared with the
existing full-dev run on the same 93 clips. The two should agree exactly or almost
exactly. If they differ by more than 0.002 WER, stop and record it under Deviations
before going further.

## Settings tried (C2)

Each run changes **one** setting from the baseline. Run names are fixed now.

| # | Run name | Setting | Value | Flag change vs baseline |
|---|---|---|---|---|
| 0 | `c2-base` | — (baseline) | — | — |
| 1 | `c2-prompt-none` | Prompt | no prompt | drop `--initial-prompt` |
| 2 | `c2-prompt-p1` | Prompt | P1 | `--initial-prompt "<P1>"` |
| 3 | `c2-prompt-p2` | Prompt | P2 | `--initial-prompt "<P2>"` |
| 4 | `c2-beam1` | Beam size | 1 (greedy) | `--beam-size 1` |
| 5 | `c2-beam8` | Beam size | 8 | `--beam-size 8` |
| 6 | `c2-vad` | VAD filter | on | `--vad-filter` |
| 7 | `c2-rep1.1` | Repetition penalty | 1.1 | `--repetition-penalty 1.1` |
| 8 | `c2-notempfb` | Temperature fallback | off | `--no-temperature-fallback` |
| 9 | `c2-lang-en` | Language | en | `--language en` |
| 10 | `c2-lang-es` | Language | es | `--language es` |

Candidate prompts, written from scratch (not taken from any dev or Bangor transcript),
short, and in the same casual mixed style as P0:

- **P1:** `So, ¿qué hiciste ayer? Nada, I just stayed home y vi una película.`
- **P2:** `Mi mamá dice que, you know, tenemos que ir al doctor mañana. Okay, pero after work.`

That is 11 tuning runs. On a laptop CPU, each 93-clip run should take roughly 9–15 min,
since a full 155-clip run took about 24 min (`decode_seconds` ≈ 1,462 s). The whole sweep
should take about 2–3 h unattended. `scripts/task_c_decode.sh tune` runs them in this
order and skips any run whose report already exists.

## Comparison

For every setting:

```sh
uv run python scripts/compare_matched.py <run> c2-base
```

This gives a paired bootstrap (2,000 resamples) of the WER difference on the same 93
clips. Record the tuning WER, the difference vs `c2-base`, and its 95% interval for
every run, including the ones that made no difference.

## Selection rule

Decided now, applied mechanically:

1. **Margin.** A setting "helps" only if its tuning WER is lower than `c2-base`'s by at
   least **0.002 absolute** (about 6 of the ~3,000 reference words in the tuning set).
   Smaller differences count as ties.
2. **Pick.** The candidate is the run with the lowest tuning WER among those that help.
   If none helps, the final setting is the baseline, and that is the result.
3. **Ties.** When two runs are within 0.002 of each other, the simpler one wins. "Simpler"
   means the current value first, then fewer flags changed, then the faster decode
   (lower `decode_seconds`).
4. **One combination step, at most.** If settings from **different** rows each help,
   run one extra tuning decode with all of them together (`c2-combined`). It replaces
   the single best only if it beats it by at least 0.002. There is no further search.
5. **Report once.** Decode the chosen setting and the baseline on the report folds
   (`c2-final-report` and `c2-base-report`, `--ids @data/processed/folds/report.txt`),
   then:
   ```sh
   uv run python scripts/compare_matched.py c2-final-report c2-base-report
   ```
   This report-fold difference and its 95% interval is the headline number. Nothing is
   changed or re-chosen after seeing it, including when it shows no gain.

## What gets reported

- A table with one row per setting: setting → tuning WER → Δ vs baseline [95% CI]. For
  the final setting and the baseline, it also gives the report-fold WER [95% CI] and
  the report-fold Δ [95% CI].
- Every number points to a file in `reports/baselines/` (`c2-*.json`). Only aggregates
  are committed. Prediction CSVs stay in `data/interim/predictions/` (gitignored).
- Settings with no effect are reported as results.

## C3 (system combination), for planning

- **The MBR vs ROVER choice is made on the tuning clips too.**
- **`combine_runs.py` needs every run to cover the same clips.** It stops with
  `clips differ` otherwise, so the existing full-dev Qwen runs can't be combined with a
  93- or 62-clip run.
- **C3 therefore needs one more decode,** the final setting on all 155 clips. Its
  combinations are then scored on the report folds only. How to restrict
  `combine_runs.py` output to the report folds is to be settled before C3 starts, and
  recorded under Deviations.

## Deviations

_None yet._
