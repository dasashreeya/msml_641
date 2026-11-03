# Speech recognition for Spanish–English code-switched conversation

MSML641 (Natural Language Processing, Fall 2026) term project:
**Rachel Bubeck, Shreeya Dasa Lakshminath, Teammate 3 (name TBD).**

Bilingual speakers often switch between Spanish and English mid-sentence. Speech
recognizers built for one language at a time handle this badly: they translate instead of
transcribing, respell Spanish words as English ones, or drop words at the switch. This
project measures and improves transcription of code-switched conversation by:

- comparing pretrained models;
- testing prompting;
- fine-tuning on bilingual conversational speech;
- analysing where the remaining errors come from.

| | |
|---|---|
| Evaluation data | Lost in Transcription Dev Data (Spanish–English), ~35 min, CC-BY-SA-4.0 |
| Training data | Bangor Miami Spanish–English Corpus, ~35 h, GPL-3.0 |
| Models | Whisper large-v3-turbo (MIT), Qwen3-ASR 1.7B (Apache-2.0), both open-weight |
| Metric | WER after normalization; CER, per-language WER, switch-point error rate, bootstrap intervals |

**Start here:**

- `docs/WORK_SPLIT.md`: who does what, and by when
- `docs/DATA.md`: where to download the data and the rules for using it
- `docs/PRIOR_WORK.md`: what already works, and where it came from

## Setup

Requirements: Python 3.12, [`uv`](https://docs.astral.sh/uv/), and `ffmpeg`/`ffprobe` on
`PATH`.

```sh
git clone https://github.com/dasashreeya/msml_641.git && cd msml_641
uv sync --extra audit --extra dev --extra prep --extra baseline
uv run pytest -q
```

Then download and ingest both datasets as described in `docs/DATA.md`.

## Pipeline

| Step | Command | Output |
|---|---|---|
| Audit the data | `uv run python scripts/audit_data.py` | `reports/data_audit.json` |
| Bangor → training clips | `uv run python scripts/prepare_bangor.py --write --export-audio` | `data/processed/bangor_segments/` |
| Dev-length variant (G7) | `uv run python scripts/prepare_bangor_variant.py g7 --target-min 8 --target-max 20 --max-gap 3 --min-seconds 3` | `data/processed/bangor_segments_g7/` |
| Zero-shot Whisper | `uv run python scripts/whisper_baseline.py --model large-v3-turbo --language auto` | `reports/baselines/<run>.json` |
| Whisper + prompt | same, with `--initial-prompt "<mixed Spanish–English sentence>"` | |
| Fine-tuned model | same, with `--model artifacts/models/ft-g7` (shared privately, see `docs/WORK_SPLIT.md`) | |
| Compare runs | `uv run python scripts/compare_runs.py --output reports/baselines/<name>.json <run> <run> ...` | paired bootstrap |
| Per-speaker check | `uv run python scripts/speaker_split.py --candidate <run> --incumbent <run>` | |
| Combine systems | `uv run python scripts/combine_runs.py --name <name> --method mbr <run> <run> ...` | MBR or ROVER |

Every script documents its options at the top of the file (`--help` also works). A smoke
run on a few clips: add `--limit 10` to `whisper_baseline.py`.

### Qwen3-ASR

Qwen3-ASR's pinned dependencies conflict with the default environment, so it gets its
own:

```sh
UV_PROJECT_ENVIRONMENT=.venv-qwen uv sync --extra qwen --extra audit
UV_PROJECT_ENVIRONMENT=.venv-qwen uv run --no-sync python scripts/whisper_baseline.py \
  --backend qwen --model Qwen/Qwen3-ASR-1.7B
```

### Fine-tuning on Modal (GPU)

The fine-tuned models already exist (`reports/finetune/`), and the remaining tasks need no
GPU. These steps are how they were trained, for reference or retraining. Fine-tuning runs
on an A100 through [Modal](https://modal.com); agree on a budget before launching anything.

```sh
uv sync --extra train && uv run --extra train modal setup        # one-time login
uv run --extra train modal volume create lit-sp-en-train          # one-time
UV_PROJECT_ENVIRONMENT=.venv-qwen uv run --no-sync python scripts/finetune_dry_run.py  # CPU check, whisper-tiny
uv run --extra train modal volume put lit-sp-en-train data/processed/bangor_segments_g7 /bangor_g7
uv run --extra train python scripts/modal_watchdog.py full <run-id> --max-minutes 35 \
    --stage-arg=--dataset=g7 --stage-arg=--expected-items=4715
uv run --extra train python scripts/evaluate_finetuned.py full-<run-id> --prefix g7
```

The watchdog stops the Modal app at the wall-clock limit, so a hung job can't keep
billing.

## Layout

| Path | What |
|---|---|
| `src/lit_sp_en/` | Library: audio probing, CHAT parsing and conversion, segmentation, transcript normalization, evaluation, fine-tuning, combination |
| `scripts/` | Command-line steps (one per file, documented at the top) |
| `submission_src/selection.py` | Dependency-free MBR selection used by `combine_runs.py` |
| `vendor/runtime_score.py` | The challenge's official normalizer and scorer, unchanged |
| `configs/datasets.json` | Pinned dataset IDs, sizes and checksums |
| `tests/` | `uv run pytest -q` |
| `reports/` | Existing results, aggregates only: baselines, fine-tuning, k-fold held-out, combinations (`reports/README.md`) |
| `data/` | Downloaded and derived data, **gitignored** |

## Data rules (short version)

- Each member downloads from Mozilla Data Collective.
- Never commit, upload or paste audio, transcripts or clip ids.
- No speaker identification or voice cloning.
- No LLM training on Bangor.
- Cite both datasets.

Details are in `docs/DATA.md`.

## License and citation

Code: MPL-2.0 (`LICENSE`). Data is not included and keeps its own licenses. If you use
the Bangor Miami corpus, cite Deuchar & Parafita Couto (2011), *The Bangor Miami Corpus*,
TalkBank, doi:10.21415/T5J01D.
