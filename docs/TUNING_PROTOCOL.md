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
order and skips any run whose report already exists. On Windows, `scripts\task_c_decode.ps1 tune`
runs the same runs with the same names and prompts.

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

## C3: system combination

Written on 2026-11-25, after C2 and before any C3 run.

**What is being measured.** Combining `ft-g7` with other systems (MBR selection or ROVER
voting, `scripts/combine_runs.py`) lowered full-dev WER in earlier work, to 0.0885 at best
(`rover4-qeqn.json`). Those candidate sets and methods were chosen on all 155 clips,
including the report folds. C3 chooses among them on the tuning folds only and reports the
choice once on the report folds. This gives a held-out estimate of the combination gain.

**Inputs: no new decoding.** C2's final setting is the baseline, so the existing full-dev
run `ft-g7-turbo-auto-int8-b5-prompt` already is the best `ft-g7` run (see Deviations,
2026-11-25). All inputs are existing full-dev prediction CSVs from the shared handover.

**Incumbent.** `c3-ftg7-breaks` is `ft-g7` with the same post-processing rule the
combinations use (`sentence-breaks-keep-ellipsis`, docs M11b), built with `combine_runs.py`.
A combination is compared against it, so the measured gain is the combination's own.
`score_folds.py` refuses comparisons whose post-processing differs.

**Candidates: 3 sets × 3 methods = 9 combinations, fixed now.** `ft-g7` comes first in
every set, so it is the tie-break and the ROVER order backbone.

| Set | Systems |
|---|---|
| s3 | `ft-g7`, `large-v3-turbo-auto-int8-b5-prompt-guard`, `Qwen3-ASR-1.7B-auto-cpu-float32-ctx` |
| s4 | `ft-g7`, `large-v3-turbo-auto-int8-b5-prompt-guard`, `Qwen3-ASR-1.7B-es-cpu-float32`, `Qwen3-ASR-1.7B-en-cpu-float32` |
| s5 | `ft-g7`, `ft-s2-turbo-auto-int8-b5-prompt`, `large-v3-turbo-auto-int8-b5-prompt-guard`, `Qwen3-ASR-1.7B-auto-cpu-float32-ctx`, `Qwen3-ASR-1.7B-es-cpu-float32` |

Methods: `mbr`, `rover-backbone`, `rover-order`. Run names: `c3-<method>-<set>`, for
example `c3-rover-order-s4`. Every combination uses `--preprocess sentence-breaks-keep-ellipsis`.
These are the sets behind the earlier best results (`r3c-g7-rover`, `rover4-qeqn`,
`rover5-noq06`), so the choice is not new search on the report folds.

**Scoring.** `scripts/score_folds.py` scores each full-dev combination on a fold list
only, against the incumbent on the same clips (paired bootstrap, 2,000 resamples).

**Selection rule:**

1. A combination **helps** only if it lowers tuning WER (folds 0–2) by at least 0.002
   absolute against `c3-ftg7-breaks`. Smaller differences count as ties.
2. The candidate is the helpful combination with the lowest tuning WER. If none helps,
   C3 reports that combination did not help on held-out clips.
3. Ties go to the simpler combination: fewer systems, then `mbr`, then `rover-backbone`,
   then `rover-order`.
4. The chosen combination is scored **once** on the report folds (3–4), against the
   incumbent, overall and per speaker (`--by-speaker`). That is the headline. Nothing is
   re-chosen after seeing it.
5. Secondary, on the report folds: the chosen combination against plain `ft-g7` (no
   post-processing, `--allow-mismatch`). This gives the total gain over C2's final setting,
   from post-processing and combination together, and is labelled as such.

**Known limit.** The three sets were picked by earlier full-dev experiments that saw the
report folds. Even the held-out number keeps some optimism from that, and the report says so.

**Commands:** `scripts/task_c_decode.ps1` (or `.sh`) stages `c3-combine`, `c3-tune` and
`c3-report`.

## Deviations

- **2026-11-25, C2 reproducibility check.** The re-run baseline differs from the original
  run by −0.0020 [−0.0047, +0.0003] on the tuning clips (`c2-comparisons.txt`). That is
  exactly the 0.002 limit, not over it, so C2 went ahead. The cause is decoding on a
  different machine (int8 on CPU is not bit-identical across hardware). All C2 comparisons
  use runs from one machine.
- **2026-11-25, interval labels.** `compare_matched.py` labels every interval that is not
  entirely below zero as `includes zero`, including intervals entirely above zero. The C2
  results were read from the interval bounds, not the label. `score_folds.py` labels
  intervals ABOVE ZERO, BELOW ZERO or includes zero.
- **2026-11-25, C3 inputs.** The C3 plan above (C1) expected one more full-dev decode of the
  final setting. The final setting is the baseline, and its full-dev run already exists, so
  C3 uses that run (decoded on the original machine, like the other systems it is combined
  with) and no new decode is made. The restriction to fold lists is done by the new
  `scripts/score_folds.py`.
- **2026-11-27, extra full-dev decode.** A full-dev decode of the baseline was made anyway on the C2 laptop (`c3-ftg7-full`, 0.1059 vs 0.1077 for the original run). It is used only as a reproducibility check; C3 combines the original run, as planned.
