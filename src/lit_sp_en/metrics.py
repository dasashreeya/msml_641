"""Metrics for Spanish-English code-switched speech recognition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import jiwer

from lit_sp_en.evaluation import (
    bootstrap_interval,
    paired_bootstrap,
    per_clip_counts,
)
from lit_sp_en.transcripts import normalize_text


LANGUAGES = ("eng", "spa", "unknown")


def _rate(errors: int, denominator: int) -> float | None:
    """Calculate an error rate, or None when the denominator is zero."""
    return round(errors / denominator, 4) if denominator else None


def _word_labels(
    words: list[str],
    lexicon: Mapping[str, str],
) -> list[str]:
    """Assign each reference word an English, Spanish, or unknown label."""
    return [lexicon.get(word.lower(), "unknown") for word in words]


def _clip_breakdown(
    reference: str,
    hypothesis: str,
    lexicon: Mapping[str, str],
) -> dict:
    """Count reference-word errors by language and switch proximity.

    Insertions contribute to overall WER and CER but are not assigned
    to language or switch-point groups because they have no reference word.
    """
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    ref_words = ref.split()

    alignment = jiwer.process_words(ref, hyp)
    labels = _word_labels(ref_words, lexicon)

    word_errors = [False] * len(ref_words)

    for chunk in alignment.alignments[0]:
        if chunk.type in ("substitute", "delete"):
            for index in range(chunk.ref_start_idx, chunk.ref_end_idx):
                word_errors[index] = True

    language_counts = {
        language: {"errors": 0, "reference_words": 0}
        for language in LANGUAGES
    }

    for label, is_error in zip(labels, word_errors, strict=True):
        language_counts[label]["reference_words"] += 1
        language_counts[label]["errors"] += int(is_error)

    switch_indices = set()

    for index in range(len(labels) - 1):
        left, right = labels[index], labels[index + 1]

        if left in ("eng", "spa") and right in ("eng", "spa") and left != right:
            switch_indices.update((index, index + 1))

    non_switch_indices = set(range(len(ref_words))) - switch_indices

    return {
        "languages": language_counts,
        "switch": {
            "errors": sum(word_errors[i] for i in switch_indices),
            "reference_words": len(switch_indices),
        },
        "non_switch": {
            "errors": sum(word_errors[i] for i in non_switch_indices),
            "reference_words": len(non_switch_indices),
        },
        "covered_words": sum(label != "unknown" for label in labels),
        "reference_words": len(ref_words),
    }


def corpus_metrics(
    references: Sequence[str],
    hypotheses: Sequence[str],
    lexicon: Mapping[str, str],
) -> dict:
    """Calculate corpus, language-specific, and switch-point metrics."""
    if len(references) != len(hypotheses):
        raise ValueError("References and hypotheses must have equal lengths.")

    counts = per_clip_counts(references, hypotheses)
    total = {
        "errors": sum(
            c["substitutions"] + c["deletions"] + c["insertions"]
            for c in counts
        ),
        "reference_words": sum(c["reference_words"] for c in counts),
    }

    cer_errors = 0
    reference_characters = 0

    language_totals = {
        language: {"errors": 0, "reference_words": 0}
        for language in LANGUAGES
    }
    switch_totals = {"errors": 0, "reference_words": 0}
    non_switch_totals = {"errors": 0, "reference_words": 0}
    covered_words = 0


    for reference, hypothesis in zip(references, hypotheses, strict=True):
        ref = normalize_text(reference)
        hyp = normalize_text(hypothesis)

        char_result = jiwer.process_characters(ref, hyp)
        cer_errors += (
            char_result.substitutions
            + char_result.deletions
            + char_result.insertions
        )
        reference_characters += len(ref)

        breakdown = _clip_breakdown(reference, hypothesis, lexicon)

        for language in LANGUAGES:
            for key in ("errors", "reference_words"):
                language_totals[language][key] += (
                    breakdown["languages"][language][key]
                )

        for category, totals in (
            ("switch", switch_totals),
            ("non_switch", non_switch_totals),
        ):
            for key in ("errors", "reference_words"):
                totals[key] += breakdown[category][key]

        covered_words += breakdown["covered_words"]

    def rate_result(values: dict) -> dict:
        return {
            **values,
            "wer": _rate(values["errors"], values["reference_words"]),
        }

    return {
        "wer": _rate(total["errors"], total["reference_words"]),
        "cer": _rate(cer_errors, reference_characters),
        "errors": total["errors"],
        "reference_words": total["reference_words"],
        "reference_characters": reference_characters,
        "substitutions": sum(c["substitutions"] for c in counts),
        "deletions": sum(c["deletions"] for c in counts),
        "insertions": sum(c["insertions"] for c in counts),
        "cer_errors": cer_errors,
        "languages": {
            language: rate_result(values)
            for language, values in language_totals.items()
        },
        "switch": rate_result(switch_totals),
        "non_switch": rate_result(non_switch_totals),
        "lexicon_coverage": {
            "covered_words": covered_words,
            "reference_words": total["reference_words"],
            "rate": _rate(covered_words, total["reference_words"]),
        },
    }


def _subgroup_interval(
    references: Sequence[str],
    hypotheses: Sequence[str],
    lexicon: Mapping[str, str],
    category: str,
    language: str | None = None,
    reps: int = 2000,
    seed: int = 0,
) -> dict:
    """Bootstrap a subgroup error rate by resampling clips."""
    counts = []

    for reference, hypothesis in zip(references, hypotheses, strict=True):
        breakdown = _clip_breakdown(reference, hypothesis, lexicon)

        if language is not None:
            values = breakdown["languages"][language]
        else:
            values = breakdown[category]

        counts.append({
            "substitutions": values["errors"],
            "deletions": 0,
            "insertions": 0,
            "reference_words": values["reference_words"],
        })

    if not any(item["reference_words"] for item in counts):
        return None
   
    return bootstrap_interval(counts, reps=reps, seed=seed)


def corpus_confidence_intervals(
    references: Sequence[str],
    hypotheses: Sequence[str],
    lexicon: Mapping[str, str],
    reps: int = 2000,
    seed: int = 0,
) -> dict:
    """Calculate 95% bootstrap intervals for WER and subgroup rates."""
    if len(references) != len(hypotheses):
        raise ValueError("References and hypotheses must have equal lengths.")

    counts = per_clip_counts(references, hypotheses)

    return {
        "wer": bootstrap_interval(counts, reps=reps, seed=seed),
        "languages": {
            language: _subgroup_interval(
                references, hypotheses, lexicon,
                "languages", language, reps, seed,
            )
            for language in LANGUAGES
        },
        "switch": _subgroup_interval(
            references, hypotheses, lexicon,
            "switch", reps=reps, seed=seed,
        ),
        "non_switch": _subgroup_interval(
            references, hypotheses, lexicon,
            "non_switch", reps=reps, seed=seed,
        ),
    }


def paired_wer_interval(
    references: Sequence[str],
    hypotheses_a: Sequence[str],
    hypotheses_b: Sequence[str],
    reps: int = 2000,
    seed: int = 0,
) -> dict:
    """Bootstrap the paired difference WER(B) - WER(A)."""
    counts_a = per_clip_counts(references, hypotheses_a)
    counts_b = per_clip_counts(references, hypotheses_b)

    return paired_bootstrap(
        counts_a, counts_b, reps=reps, seed=seed
    )
