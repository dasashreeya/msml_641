"""Aggregate WER, CER, and code-switching error metrics for the six project systems."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lit_sp_en.metrics import corpus_metrics, corpus_confidence_intervals
from scripts.audit_data import assert_no_transcript_leak

PREDICTIONS_DIR = ROOT / "data" / "interim" / "predictions"
LEXICON_PATH = ROOT / "data" / "processed" / "bangor_lexicon.json"
OUTPUT_PATH = ROOT / "reports" / "error_analysis.json"

SYSTEMS = [
    ("Zero-shot Whisper turbo", "large-v3-turbo-auto-int8-b5"),
    ("Whisper turbo + prompt", "large-v3-turbo-auto-int8-b5-prompt"),
    ("Zero-shot Qwen3-ASR 1.7B", "Qwen3-ASR-1.7B-auto-cpu-float32"),
    ("Fine-tuned Whisper (G7) + prompt", "ft-g7-turbo-auto-int8-b5-prompt"),
    ("Best system combination", "r3c-M11b"),
    ("Fine-tuned on held-out folds", "kfold-d2-heldout-breaks"),
]


def read_predictions(path: Path) -> tuple[list[str], list[str]]:
    """Read audio filenames and transcripts from a prediction CSV."""
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if not {"audio_filename", "transcript"}.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required columns in {path.name}")

        rows = list(reader)

    filenames = [row["audio_filename"] for row in rows]
    transcripts = [row["transcript"] or "" for row in rows]

    if any(not name for name in filenames):
        raise ValueError(f"Empty audio filename in {path.name}")
    if len(filenames) != len(set(filenames)):
        raise ValueError(f"Duplicate audio filenames in {path.name}")

    return filenames, transcripts


def load_lexicon() -> dict[str, str]:
    """Load the shared English/Spanish word lexicon."""
    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    lexicon = data.get("lexicon")

    if not isinstance(lexicon, dict):
        raise ValueError("Invalid Bangor lexicon: missing 'lexicon' mapping.")

    if any(language not in {"eng", "spa"} for language in lexicon.values()):
        raise ValueError("Lexicon contains an unsupported language label.")

    return lexicon


def analyze_system(
    label: str,
    run: str,
    references: list[str],
    hypotheses: list[str],
    lexicon: dict[str, str],
    reps: int = 2000,
    seed: int = 0,
) -> dict:
    """Calculate aggregate metrics and confidence intervals for one system."""
    metrics = corpus_metrics(references, hypotheses, lexicon)
    intervals = corpus_confidence_intervals(
        references, hypotheses, lexicon, reps=reps, seed=seed
    )

    return {
        "label": label,
        "run": run,
        "clips": len(references),
        **metrics,
        "confidence_intervals": intervals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reps",
        type=int,
        default=2000,
        help="Number of bootstrap repetitions (default: 2000).",
    )
    args = parser.parse_args()

    if args.reps < 1:
        parser.error("--reps must be at least 1")

    lexicon = load_lexicon()
    report = {
        "description": "Aggregate error analysis of six code-switched ASR systems.",
        "confidence_level": 0.95,
        "bootstrap_repetitions": args.reps,
        "systems": [],
    }

    all_transcripts = []
    expected_filenames = None
    expected_references = None

    for label, run in SYSTEMS:
        prediction_path = PREDICTIONS_DIR / f"{run}.csv"
        reference_path = PREDICTIONS_DIR / f"{run}.reference.csv"

        filenames, hypotheses = read_predictions(prediction_path)
        ref_filenames, references = read_predictions(reference_path)

        if filenames != ref_filenames:
            raise ValueError(f"Reference and prediction rows differ for {run}")

        if expected_filenames is None:
            expected_filenames = filenames
            expected_references = references
        elif filenames != expected_filenames or references != expected_references:
            raise ValueError(f"Reference clips or transcripts differ for {run}")

        all_transcripts.extend(references)
        all_transcripts.extend(hypotheses)

        print(f"Analyzing {label}...")
        result = analyze_system(
            label, run, references, hypotheses, lexicon, reps=args.reps
        )
        report["systems"].append(result)

    assert_no_transcript_leak(report, all_transcripts)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nWrote aggregate analysis for {len(report['systems'])} systems.")
    print(f"Output: {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
