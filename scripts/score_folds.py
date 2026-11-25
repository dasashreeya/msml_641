"""Paired comparison of full-dev runs on a subset of dev folds (Task C3, docs/TUNING_PROTOCOL.md).

    uv run --no-sync python scripts/score_folds.py --ids @data/processed/folds/tune.txt \\
        --incumbent ft-g7-turbo-auto-int8-b5-prompt-breaks \\
        --output reports/baselines/c3-tune.json  c3-mbr-s3 c3-rover-order-s3 ...

combine_runs.py needs every candidate to cover the same clips, so combinations are built on all
155 dev clips. This scores them on the selected clips only (the tuning folds to choose, the report
folds to report), each against the incumbent on exactly those clips, with a paired bootstrap.
--by-speaker adds the same comparison within each speaker, for the C3 speaker check.

It refuses a post-processing mismatch, like compare_matched.py: a combination with sentence-break
post-processing is compared against an incumbent with the same rule. Intervals are labelled
BELOW ZERO (candidate better), ABOVE ZERO (candidate worse) or includes zero.

Writes aggregates only (WERs, differences, intervals, clip counts, a hash of the id list): no
transcript text, clip names or speaker codes.
Exit 0: every comparison made. 2: refused (post-processing). 1: clips or references don't match.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lit_sp_en.evaluation import paired_bootstrap, per_clip_counts  # noqa: E402
from scripts import compare_matched  # noqa: E402
from scripts.audit_data import assert_no_transcript_leak, read_dev_metadata  # noqa: E402
from scripts.whisper_baseline import DEV_DIR, PREDICTIONS_DIR, REPORTS_DIR, select_dev_ids  # noqa: E402


def read_run(run: str, predictions: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(hypotheses, references) by audio filename."""

    def read(path: Path) -> dict[str, str]:
        with path.open(encoding="utf-8", newline="") as handle:
            return {r["audio_filename"]: (r["transcript"] or "") for r in csv.DictReader(handle)}

    return read(predictions / f"{run}.csv"), read(predictions / f"{run}.reference.csv")


def wer_of(counts: list[dict[str, int]]) -> float:
    errors = sum(c["substitutions"] + c["deletions"] + c["insertions"] for c in counts)
    words = sum(c["reference_words"] for c in counts)
    return errors / words if words else 0.0


def label(low: float, high: float) -> str:
    if high < 0:
        return "BELOW ZERO"
    if low > 0:
        return "ABOVE ZERO"
    return "includes zero"


def compare(candidate: str, incumbent: str, names: list[str], groups: dict[str, list[bool]],
            predictions: Path, reps: int, seed: int) -> dict | None:
    """Candidate minus incumbent on `names`, overall and within each group mask."""

    cand_hyp, cand_ref = read_run(candidate, predictions)
    inc_hyp, inc_ref = read_run(incumbent, predictions)
    missing = [n for n in names if n not in cand_hyp or n not in inc_hyp]
    if missing:
        print(f"{candidate}: {len(missing)} selected clip(s) missing from a run; cannot compare")
        return None
    if any(cand_ref[n] != inc_ref[n] for n in names):
        print(f"{candidate}: references differ from {incumbent}; refusing to compare")
        return None
    refs = [cand_ref[n] for n in names]
    a = per_clip_counts(refs, [inc_hyp[n] for n in names])
    b = per_clip_counts(refs, [cand_hyp[n] for n in names])
    result = {"candidate": candidate, "groups": {}}
    for group, mask in groups.items():
        ga = [c for c, keep in zip(a, mask, strict=True) if keep]
        gb = [c for c, keep in zip(b, mask, strict=True) if keep]
        stats = paired_bootstrap(ga, gb, reps=reps, seed=seed)
        entry = {
            "clips": len(ga),
            "reference_words": sum(c["reference_words"] for c in ga),
            "incumbent_wer": round(wer_of(ga), 4),
            "candidate_wer": round(wer_of(gb), 4),
            "difference": stats["difference_b_minus_a"],
            "low": stats["low"],
            "high": stats["high"],
            "interval": label(stats["low"], stats["high"]),
        }
        result["groups"][group] = entry
        print(f"{candidate:<28} {group:<10} clips={entry['clips']:>3}  "
              f"incumbent={entry['incumbent_wer']:.4f}  candidate={entry['candidate_wer']:.4f}  "
              f"diff={entry['difference']:+.4f} [{entry['low']:+.4f}, {entry['high']:+.4f}]  "
              f"{entry['interval']}")
    return result


def main(argv: list[str] | None = None, *, dev_dir: Path = DEV_DIR,
         predictions: Path = PREDICTIONS_DIR, reports: Path = REPORTS_DIR) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("candidates", nargs="+", help="full-dev runs to score")
    parser.add_argument("--incumbent", required=True, help="full-dev run to compare against")
    parser.add_argument("--ids", required=True,
                        help="devNNN ids: comma-separated, or @path to a file with one per line")
    parser.add_argument("--by-speaker", action="store_true",
                        help="also compare within each speaker (speaker_1, speaker_2)")
    parser.add_argument("--output", type=Path, help="write the aggregates to this JSON file")
    parser.add_argument("--reps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--allow-mismatch", action="store_true",
                        help="compare even when post-processing differs or is unknown")
    args = parser.parse_args(argv)

    _, rows, _, _ = read_dev_metadata(dev_dir)
    rank = {s: f"speaker_{i + 1}" for i, (s, _) in
            enumerate(Counter(r["speaker"] for r in rows).most_common())}
    selected = select_dev_ids(rows, args.ids)
    names = [r["audio_filename"] for r in selected]
    groups = {"all": [True] * len(selected)}
    if args.by_speaker:
        speakers = [rank[r["speaker"]] for r in selected]
        for speaker in sorted(set(speakers)):
            groups[speaker] = [s == speaker for s in speakers]
    ids_text = args.ids[1:] if args.ids.startswith("@") else None
    position = {id(r): i for i, r in enumerate(rows)}
    id_list = sorted(f"dev{position[id(r)]:03d}" for r in selected)
    ids_hash = hashlib.sha256("\n".join(id_list).encode()).hexdigest()[:12]

    inc_pp = compare_matched.postprocessing(args.incumbent, reports)
    print(f"== {len(names)} clips (ids sha256 {ids_hash}) vs {args.incumbent} [{inc_pp}], "
          f"paired bootstrap {args.reps} resamples seed {args.seed} ==")
    results, worst = [], 0
    for candidate in args.candidates:
        cand_pp = compare_matched.postprocessing(candidate, reports)
        if not args.allow_mismatch and ("unknown" in (cand_pp, inc_pp) or cand_pp != inc_pp):
            print(f"REFUSED {candidate} [{cand_pp}]: post-processing differs from the incumbent "
                  f"[{inc_pp}] or is unknown")
            worst = max(worst, 2)
            continue
        result = compare(candidate, args.incumbent, names, groups, predictions,
                         args.reps, args.seed)
        if result is None:
            worst = max(worst, 1)
        else:
            results.append(result)

    if args.output:
        report = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "privacy": "aggregates only: no transcript text, clip names or speaker codes",
            "tool": "scripts/score_folds.py",
            "ids": {"file": Path(ids_text).name if ids_text else None, "clips": len(names),
                    "sha256_12": ids_hash},
            "incumbent": args.incumbent,
            "incumbent_postprocessing": inc_pp,
            "bootstrap": {"reps": args.reps, "seed": args.seed, "level": 0.95},
            "results": results,
        }
        assert_no_transcript_leak(report, [r["transcript"] for r in rows])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
