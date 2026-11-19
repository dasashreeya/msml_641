"""Sample ASR word errors for private manual categorization."""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

import jiwer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lit_sp_en.transcripts import normalize_text

PREDICTIONS = ROOT / "data" / "interim" / "predictions"
RUN = "r3c-M11b"
OUTPUT = PREDICTIONS / "manual_error_labels.csv"
SAMPLE_SIZE = 50
SEED = 42


def read_transcripts(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as file:
        return {
            row["audio_filename"]: row["transcript"] or ""
            for row in csv.DictReader(file)
        }


def collect_errors(
    references: dict[str, str],
    hypotheses: dict[str, str],
) -> list[dict]:
    errors = []

    if references.keys() != hypotheses.keys():
        raise ValueError("Reference and hypothesis clips differ.")

    for name in sorted(references):
        ref = normalize_text(references[name])
        hyp = normalize_text(hypotheses[name])

        result = jiwer.process_words(ref, hyp)
        ref_words = ref.split()
        hyp_words = hyp.split()

        for chunk in result.alignments[0]:
            if chunk.type == "equal":
                continue

            r = ref_words[chunk.ref_start_idx:chunk.ref_end_idx]
            h = hyp_words[chunk.hyp_start_idx:chunk.hyp_end_idx]

            if chunk.type == "substitute":
                pairs = zip(r, h, strict=True)
            elif chunk.type == "delete":
                pairs = [(word, "") for word in r]
            elif chunk.type == "insert":
                pairs = [("", word) for word in h]
            else:
                continue

            for ref_word, hyp_word in pairs:
                errors.append({
                    "audio_filename": name,
                    "error_type": chunk.type,
                    "reference_word": ref_word,
                    "hypothesis_word": hyp_word,
                    "reference_context": references[name],
                    "hypothesis_context": hypotheses[name],
                    "category": "",
                })

    return errors
def main() -> int:
    references = read_transcripts(
        PREDICTIONS / f"{RUN}.reference.csv"
    )
    hypotheses = read_transcripts(
        PREDICTIONS / f"{RUN}.csv"
    )

    errors = collect_errors(references, hypotheses)

    if len(errors) < SAMPLE_SIZE:
        raise ValueError("Not enough errors for the requested sample.")

    sampled = random.Random(SEED).sample(errors, SAMPLE_SIZE)

    if OUTPUT.exists():
        raise FileExistsError(
            "Labeling sheet already exists. Refusing to overwrite it."
        )

    fieldnames = [
        "sample_id",
        "audio_filename",
        "error_type",
        "reference_word",
        "hypothesis_word",
        "reference_context",
        "hypothesis_context",
        "category",
    ]

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for index, error in enumerate(sampled, start=1):
            writer.writerow({"sample_id": index, **error})

    print(f"Total word errors: {len(errors)}")
    print(f"Sampled errors: {len(sampled)}")
    print(f"Random seed: {SEED}")
    print(f"Private labeling sheet: {OUTPUT.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
