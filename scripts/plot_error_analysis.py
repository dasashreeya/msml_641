"""Generate figures for the ASR error analysis."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / f"matplotlib-{os.getuid()}"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

SYSTEM_LABELS = [
    "Whisper\nzero-shot",
    "Whisper\n+ prompt",
    "Qwen3-ASR\nzero-shot",
    "Fine-tuned\n+ prompt",
    "System\ncombination",
    "Held-out\nfine-tuned",
]

COLORS = ["#4477AA", "#EE7733"]


def save_figure(fig, filename: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {filename}")


def confidence_errors(systems, metric):
    values = np.array([s[metric] for s in systems]) * 100

    lower = np.array([
        s["confidence_intervals"][metric]["low"]
        for s in systems
    ]) * 100

    upper = np.array([
        s["confidence_intervals"][metric]["high"]
        for s in systems
    ]) * 100

    return np.array([values - lower, upper - values])

def plot_wer_cer(systems):
    x = np.arange(len(systems))
    width = 0.35

    wer = [s["wer"] * 100 for s in systems]
    cer = [s["cer"] * 100 for s in systems]

    fig, ax = plt.subplots(figsize=(11, 5.5))

    ax.bar(
        x - width / 2,
        wer,
        width,
        yerr=confidence_errors(systems, "wer"),
        capsize=4,
        label="WER",
        color=COLORS[0],
    )

    ax.bar(
        x + width / 2,
        cer,
        width,
        yerr=confidence_errors(systems, "cer"),
        capsize=4,
        label="CER",
        color=COLORS[1],
    )

    ax.set_ylabel("Error rate (%)")
    ax.set_title("WER and CER Across ASR Systems")
    ax.set_xticks(x, SYSTEM_LABELS)
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    save_figure(fig, "wer_cer_by_system.png")

def plot_language_wer(systems):
    x = np.arange(len(systems))
    width = 0.35

    english = [
        s["languages"]["eng"]["wer"] * 100
        for s in systems
    ]
    spanish = [
        s["languages"]["spa"]["wer"] * 100
        for s in systems
    ]

    fig, ax = plt.subplots(figsize=(11, 5.5))

    ax.bar(
        x - width / 2,
        english,
        width,
        label="English",
        color=COLORS[0],
    )

    ax.bar(
        x + width / 2,
        spanish,
        width,
        label="Spanish",
        color=COLORS[1],
    )

    ax.set_ylabel("Reference-word error rate (%)")
    ax.set_title("Per-Language WER Across ASR Systems")
    ax.set_xticks(x, SYSTEM_LABELS)
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    save_figure(fig, "language_wer_by_system.png")

def plot_switch_errors(systems):
    x = np.arange(len(systems))
    width = 0.35

    switch = [
        s["switch"]["wer"] * 100
        for s in systems
    ]
    non_switch = [
        s["non_switch"]["wer"] * 100
        for s in systems
    ]

    fig, ax = plt.subplots(figsize=(11, 5.5))

    ax.bar(
        x - width / 2,
        switch,
        width,
        label="Switch-adjacent",
        color=COLORS[0],
    )

    ax.bar(
        x + width / 2,
        non_switch,
        width,
        label="Non-switch",
        color=COLORS[1],
    )

    ax.set_ylabel("Reference-word error rate (%)")
    ax.set_title("Switch vs. Non-Switch Error Rates")
    ax.set_xticks(x, SYSTEM_LABELS)
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    save_figure(fig, "switch_error_rates.png")

def plot_taxonomy(taxonomy):
    labels = {
        "wrong_language": "Wrong-language substitution",
        "translation": "Translation",
        "dropped_at_switch": "Word dropped at switch",
        "proper_noun": "Name or proper noun",
        "filler": "Filler or hesitation",
        "other": "Other",
    }

    counts = taxonomy["counts"]
    categories = list(labels)
    values = [counts[key] for key in categories]

    fig, ax = plt.subplots(figsize=(9, 5))

    bars = ax.barh(
        [labels[key] for key in categories],
        values,
        color=COLORS[0],
    )

    ax.bar_label(bars, padding=4)
    ax.invert_yaxis()
    ax.set_xlabel("Number of sampled errors")
    ax.set_title(
        f"Manual Error Taxonomy "
        f"(n={taxonomy['sample_size']})"
    )
    ax.set_xlim(0, max(values) * 1.15)
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)

    save_figure(fig, "error_taxonomy.png")

def main() -> int:
    analysis = json.loads(
        (REPORTS / "error_analysis.json").read_text(
            encoding="utf-8"
        )
    )

    taxonomy = json.loads(
        (REPORTS / "error_taxonomy.json").read_text(
            encoding="utf-8"
        )
    )

    systems = analysis["systems"]

    plot_wer_cer(systems)
    plot_language_wer(systems)
    plot_switch_errors(systems)
    plot_taxonomy(taxonomy)

    print("\nAll four figures generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
