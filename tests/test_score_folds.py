import csv
import json
from pathlib import Path

import pytest

from scripts import score_folds

# Six clips, two speakers. Run "good" is perfect; run "bad" drops a word on clips 0, 2 and 4.
REFS = ["zorblat went to la tienda", "quixotic flurbs said hola", "pero maria no",
        "the vlorp is ready ya", "nos vemos manana okay", "glimmer said that is all"]
BAD = ["zorblat went to la", "quixotic flurbs said hola", "pero maria",
       "the vlorp is ready ya", "nos vemos manana", "glimmer said that is all"]


def _write(path: Path, names: list[str], texts: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["audio_filename", "transcript"])
        writer.writerows(zip(names, texts, strict=True))


def _report(reports: Path, run: str, preprocess: str) -> None:
    (reports / f"{run}.json").write_text(json.dumps({"backend": "x", "preprocess": preprocess}),
                                         encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    dev, predictions, reports = tmp_path / "dev", tmp_path / "pred", tmp_path / "reports"
    for d in (dev, predictions, reports):
        d.mkdir()
    names = [f"c{i}.mp3" for i in range(len(REFS))]
    lines = ["audio_filename\tspeaker\ttranscript\tlanguage\tconvo_id"]
    lines += [f"{n}\t{'AAABBB'[i]}\t{r}\tenspa\t1"
              for i, (n, r) in enumerate(zip(names, REFS, strict=True))]
    (dev / "metadata.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for run, texts in {"good": REFS, "bad": BAD, "good-breaks": REFS}.items():
        _write(predictions / f"{run}.csv", names, texts)
        _write(predictions / f"{run}.reference.csv", names, REFS)
    _report(reports, "good", "none")
    _report(reports, "bad", "none")
    _report(reports, "good-breaks", "sentence-breaks-keep-ellipsis")
    return {"dev_dir": dev, "predictions": predictions, "reports": reports, "root": tmp_path}


def _run(workspace: dict, argv: list[str]) -> int:
    return score_folds.main(argv, dev_dir=workspace["dev_dir"],
                            predictions=workspace["predictions"], reports=workspace["reports"])


def test_scores_only_selected_clips(workspace: dict) -> None:
    out = workspace["root"] / "out.json"
    # Clips 1 and 3 are identical in both runs, so on them alone the difference is zero.
    assert _run(workspace, ["bad", "--incumbent", "good", "--ids", "dev001,dev003",
                            "--output", str(out)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    entry = result["results"][0]["groups"]["all"]
    assert result["ids"]["clips"] == 2
    assert entry["clips"] == 2 and entry["difference"] == 0.0
    assert entry["interval"] == "includes zero"


def test_worse_candidate_is_labelled_above_zero(workspace: dict) -> None:
    out = workspace["root"] / "out.json"
    ids = workspace["root"] / "ids.txt"
    ids.write_text("dev000\r\ndev002\r\ndev004\r\n", encoding="utf-8")  # Windows line endings
    assert _run(workspace, ["bad", "--incumbent", "good", "--ids", f"@{ids}",
                            "--output", str(out)]) == 0
    entry = json.loads(out.read_text(encoding="utf-8"))["results"][0]["groups"]["all"]
    assert entry["candidate_wer"] > entry["incumbent_wer"] == 0.0
    assert entry["low"] > 0 and entry["interval"] == "ABOVE ZERO"


def test_by_speaker_splits_selected_clips(workspace: dict) -> None:
    out = workspace["root"] / "out.json"
    assert _run(workspace, ["bad", "--incumbent", "good", "--ids", "dev000,dev001,dev004",
                            "--by-speaker", "--output", str(out)]) == 0
    groups = json.loads(out.read_text(encoding="utf-8"))["results"][0]["groups"]
    # Speakers A and B have three clips each; A ranks first on the tie by first appearance.
    assert {g: groups[g]["clips"] for g in groups} == {"all": 3, "speaker_1": 2, "speaker_2": 1}


def test_refuses_postprocessing_mismatch(workspace: dict) -> None:
    assert _run(workspace, ["bad", "--incumbent", "good-breaks", "--ids", "dev000"]) == 2
    assert _run(workspace, ["bad", "--incumbent", "good-breaks", "--ids", "dev000",
                            "--allow-mismatch"]) == 0


def test_output_has_no_transcript_text(workspace: dict) -> None:
    out = workspace["root"] / "out.json"
    _run(workspace, ["bad", "--incumbent", "good", "--ids", "dev000,dev005", "--output", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "zorblat" not in text and "c0.mp3" not in text
