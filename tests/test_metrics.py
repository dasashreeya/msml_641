from lit_sp_en.metrics import (
    corpus_metrics,
    corpus_confidence_intervals,
    paired_wer_interval,
)


LEXICON = {
    "hola": "spa",
    "mundo": "spa",
    "hello": "eng",
    "the": "eng",
    "casa": "spa",
}


def test_one_substitution():
    result = corpus_metrics(
        ["hola hello mundo"],
        ["hola hallo mundo"],
        LEXICON,
    )

    assert result["errors"] == 1
    assert result["reference_words"] == 3
    assert result["wer"] == 0.3333
    assert result["languages"]["eng"]["errors"] == 1
    assert result["languages"]["spa"]["errors"] == 0


def test_switch_point_error():
    result = corpus_metrics(
        ["hola mundo hello"],
        ["hola mundo hallo"],
        LEXICON,
    )

    assert result["switch"]["reference_words"] == 2
    assert result["switch"]["errors"] == 1
    assert result["switch"]["wer"] == 0.5
    assert result["non_switch"]["reference_words"] == 1
    assert result["non_switch"]["errors"] == 0


def test_empty_hypothesis():
    result = corpus_metrics(
        ["hola hello"],
        [""],
        LEXICON,
    )

    assert result["wer"] == 1.0
    assert result["deletions"] == 2
    assert result["languages"]["spa"]["errors"] == 1
    assert result["languages"]["eng"]["errors"] == 1


def test_unknown_lexicon_word():
    result = corpus_metrics(
        ["hola desconocido"],
        ["hola desconocido"],
        LEXICON,
    )

    assert result["languages"]["unknown"]["reference_words"] == 1
    assert result["languages"]["unknown"]["errors"] == 0
    assert result["lexicon_coverage"]["covered_words"] == 1
    assert result["lexicon_coverage"]["rate"] == 0.5


def test_confidence_intervals():
    references = ["hola hello", "the casa"]
    hypotheses = ["hola hallo", "the casa"]

    intervals = corpus_confidence_intervals(
        references, hypotheses, LEXICON, reps=100
    )

    assert "wer" in intervals
    assert "eng" in intervals["languages"]
    assert "spa" in intervals["languages"]
    assert "switch" in intervals
    assert "non_switch" in intervals


def test_paired_wer_interval():
    references = ["hola hello", "the casa"]
    hypotheses_a = ["hola hallo", "the casa"]
    hypotheses_b = ["hola hello", "the casa"]

    interval = paired_wer_interval(
        references, hypotheses_a, hypotheses_b, reps=100
    )

    assert interval["low"] <= interval["high"]
