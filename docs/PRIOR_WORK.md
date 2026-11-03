# Prior work this project builds on

The pipeline in this repo was carried over from Shreeya's earlier work on Mozilla Data
Collective's **Lost in Transcription** challenge (Spanish–English track, Sept 2026):
https://github.com/dasashreeya/mozilla_spanish_english

That repo has the full history and design notes. This repo keeps the code and the
aggregate results (`reports/`), so the course project builds directly on them
(see `docs/WORK_SPLIT.md`). The final report should state that this
foundation predates the course.

## Carried over (working, tested)

| Area | Code |
|---|---|
| Data download, verification, provenance | `scripts/mdc_fetch.py`, `configs/datasets.json` |
| Data audit (durations, audio stats, transcript conventions, switch rates) | `scripts/audit_data.py`, `docs/DATA_AUDIT.md` |
| Bangor CHAT → plain transcripts, segmentation into training clips | `src/lit_sp_en/chat.py`, `chat_convert.py`, `segment.py`, `scripts/prepare_bangor.py`, `prepare_bangor_variant.py`, `segment_languages.py`, `docs/BANGOR_PREP.md` |
| Zero-shot baselines: Whisper (faster-whisper) and Qwen3-ASR, with prompting | `scripts/whisper_baseline.py` |
| Scoring: competition normalizer, WER, bootstrap intervals, paired comparison | `vendor/runtime_score.py`, `src/lit_sp_en/evaluation.py`, `transcripts.py`, `scripts/compare_runs.py`, `compare_matched.py` |
| Whisper fine-tuning on Modal GPUs, with a cost watchdog | `src/lit_sp_en/finetune.py`, `scripts/modal_finetune.py`, `modal_watchdog.py`, `finetune_dry_run.py`, `dump_training_args.py`, `evaluate_finetuned.py` |
| Dev cross-validation folds and second-stage fine-tune | `scripts/prepare_dev_folds.py`, `modal_finetune_dev.py`, `evaluate_kfold.py`, `score_kfold.py`, `prefetch_kfold.py`, `modal_chunk.py`, `fetch_chunks.py` |
| System combination (MBR selection, ROVER) | `src/lit_sp_en/combination.py`, `submission_src/selection.py`, `scripts/combine_runs.py` |
| Diagnostics: per-speaker split, error categories, convention rates, switch density | `scripts/speaker_split.py`, `error_categories.py`, `convention_rates.py`, `ellipsis_cost.py`, `switch_density.py`, `build_switch_dense.py` |

Some docstrings cite `docs/METHODS.md`, `docs/FINETUNE_PLAN.md` or `revision.md`; those
files are in the original repo.

## Left out, and why

| Left out | Reason |
|---|---|
| GER: LLM transcript corrector (`build_ger_*`, `modal_ger_*`, `score_ger`, `modal_decode`, `modal_probe`) | Trained an LLM on Bangor-derived text; the Bangor terms forbid that unless all training data is public |
| Competition submission packaging (`submission_src/main.py`, `pack_submission`, `validate_submission`, `pin_model`, `longform_harness`, `apply_prompt_guard`) | Only needed for the challenge's runtime |
| Private Hugging Face data mirror (`hf_upload`) | Redistribution; each member downloads from MDC instead |
| Leaderboard records, submission evidence, LLM-corrector results, design and handover notes | Challenge-specific; the original repo keeps them |

The code is under MPL-2.0 (`LICENSE`), the license the challenge rules attach to publicly
shared code.
