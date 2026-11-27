#!/usr/bin/env bash
# Task C decoding runs for ft-g7 (docs/TUNING_PROTOCOL.md).
#
#   scripts/task_c_decode.sh tune                 # all 11 tuning runs, back to back
#   scripts/task_c_decode.sh compare              # each tuning run vs c2-base (paired bootstrap)
#   scripts/task_c_decode.sh report -- <flags>    # final setting + baseline on the report folds,
#                                                 # <flags> = the chosen setting's flag change,
#                                                 # e.g.  report -- --beam-size 8
#                                                 # (no prompt: report -- --initial-prompt "")
#   scripts/task_c_decode.sh c3-combine           # C3: incumbent + the 9 combinations (no decoding)
#   scripts/task_c_decode.sh c3-tune              # C3: score all 9 on the tuning folds
#   scripts/task_c_decode.sh c3-report <name>     # C3: the chosen combination, once, report folds
#
# A run whose reports/baselines/<run>.json already exists is skipped, so an interrupted
# sweep can be restarted. Needs artifacts/models/ft-g7/, the dev set, and the fold files
# from docs/WORK_SPLIT.md §C1.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL=${MODEL:-artifacts/models/ft-g7}
THREADS=${THREADS:-8}
TUNE=data/processed/folds/tune.txt
REPORT=data/processed/folds/report.txt
P0="Hola, ¿cómo estás? I'm good, gracias. Vamos a la tienda later, okay?"
P1="So, ¿qué hiciste ayer? Nada, I just stayed home y vi una película."
P2="Mi mamá dice que, you know, tenemos que ir al doctor mañana. Okay, pero after work."

# C3 (docs/TUNING_PROTOCOL.md, "C3"): combinations of existing full-dev runs.
FTG7=ft-g7-turbo-auto-int8-b5-prompt
C3_INCUMBENT=c3-ftg7-breaks
C3_RULE=sentence-breaks-keep-ellipsis
TURBO=large-v3-turbo-auto-int8-b5-prompt-guard
declare -A C3_SETS=(
  [s3]="$FTG7 $TURBO Qwen3-ASR-1.7B-auto-cpu-float32-ctx"
  [s4]="$FTG7 $TURBO Qwen3-ASR-1.7B-es-cpu-float32 Qwen3-ASR-1.7B-en-cpu-float32"
  [s5]="$FTG7 ft-s2-turbo-auto-int8-b5-prompt $TURBO Qwen3-ASR-1.7B-auto-cpu-float32-ctx Qwen3-ASR-1.7B-es-cpu-float32"
)
C3_METHODS="mbr rover-backbone rover-order"
C3_NAMES=$(for set in s3 s4 s5; do for m in $C3_METHODS; do echo "c3-$m-$set"; done; done)

decode() {  # decode <run-name> <ids-file> [extra flags...]; flags after the defaults win
  local name=$1 ids=$2; shift 2
  if [[ -f reports/baselines/$name.json ]]; then echo "skip $name (report exists)"; return; fi
  echo "=== $name  ($(date '+%H:%M:%S'))"
  uv run --no-sync python scripts/whisper_baseline.py --model "$MODEL" --compute-type int8 \
      --threads "$THREADS" --ids "@$ids" --run-name "$name" "$@"
}

need() { for f in "$@"; do [[ -e $f ]] || { echo "missing: $f" >&2; exit 1; }; done; }

case ${1:-} in
  tune)
    need "$MODEL" "$TUNE"
    decode c2-base         "$TUNE" --language auto --beam-size 5 --initial-prompt "$P0"
    decode c2-prompt-none  "$TUNE" --language auto --beam-size 5
    decode c2-prompt-p1    "$TUNE" --language auto --beam-size 5 --initial-prompt "$P1"
    decode c2-prompt-p2    "$TUNE" --language auto --beam-size 5 --initial-prompt "$P2"
    decode c2-beam1        "$TUNE" --language auto --beam-size 1 --initial-prompt "$P0"
    decode c2-beam8        "$TUNE" --language auto --beam-size 8 --initial-prompt "$P0"
    decode c2-vad          "$TUNE" --language auto --beam-size 5 --initial-prompt "$P0" --vad-filter
    decode c2-rep1.1       "$TUNE" --language auto --beam-size 5 --initial-prompt "$P0" --repetition-penalty 1.1
    decode c2-notempfb     "$TUNE" --language auto --beam-size 5 --initial-prompt "$P0" --no-temperature-fallback
    decode c2-lang-en      "$TUNE" --language en   --beam-size 5 --initial-prompt "$P0"
    decode c2-lang-es      "$TUNE" --language es   --beam-size 5 --initial-prompt "$P0"
    ;;
  compare)
    # Reproducibility check first: the re-run baseline vs the existing full-dev run.
    uv run --no-sync python scripts/compare_matched.py c2-base ft-g7-turbo-auto-int8-b5-prompt || true
    for run in c2-prompt-none c2-prompt-p1 c2-prompt-p2 c2-beam1 c2-beam8 c2-vad \
               c2-rep1.1 c2-notempfb c2-lang-en c2-lang-es c2-combined; do
      [[ -f reports/baselines/$run.json ]] || continue
      uv run --no-sync python scripts/compare_matched.py "$run" c2-base || true
    done
    ;;
  report)
    shift; [[ ${1:-} == -- ]] && shift
    need "$MODEL" "$REPORT"
    # The chosen flags come last, so they override the baseline values (argparse keeps
    # the last one). A prompt change is passed as --initial-prompt "<text>".
    decode c2-base-report  "$REPORT" --language auto --beam-size 5 --initial-prompt "$P0"
    decode c2-final-report "$REPORT" --language auto --beam-size 5 --initial-prompt "$P0" "$@"
    uv run --no-sync python scripts/compare_matched.py c2-final-report c2-base-report
    ;;
  c3-combine)
    for run in $(for set in s3 s4 s5; do echo "${C3_SETS[$set]}"; done | tr ' ' '\n' | sort -u); do
      need "data/interim/predictions/$run.csv" "data/interim/predictions/$run.reference.csv"
    done
    if [[ -f reports/baselines/$C3_INCUMBENT.json ]]; then echo "skip $C3_INCUMBENT (report exists)"
    else
      echo "=== $C3_INCUMBENT"
      uv run --no-sync python scripts/combine_runs.py "$FTG7" --name "$C3_INCUMBENT" --method "$C3_RULE"
    fi
    for set in s3 s4 s5; do
      for m in $C3_METHODS; do
        name="c3-$m-$set"
        if [[ -f reports/baselines/$name.json ]]; then echo "skip $name (report exists)"; continue; fi
        echo "=== $name"
        # shellcheck disable=SC2086  # the set is a space-separated list of run names
        uv run --no-sync python scripts/combine_runs.py ${C3_SETS[$set]} --name "$name" \
            --method "$m" --preprocess "$C3_RULE"
      done
    done
    echo "Full-dev WERs above include the report folds: do not choose from them. Next: c3-tune"
    ;;
  c3-tune)
    need "$TUNE"
    # shellcheck disable=SC2086
    uv run --no-sync python scripts/score_folds.py $C3_NAMES --incumbent "$C3_INCUMBENT" \
        --ids "@$TUNE" --output reports/baselines/c3-tune.json
    ;;
  c3-report)
    chosen=${2:-}
    grep -qx -- "$chosen" <<< "$C3_NAMES" || { echo "c3-report needs one of:" $C3_NAMES >&2; exit 2; }
    need "$REPORT"
    # Headline: the combination's own gain, against ft-g7 with the same post-processing.
    uv run --no-sync python scripts/score_folds.py "$chosen" --incumbent "$C3_INCUMBENT" \
        --ids "@$REPORT" --by-speaker --output reports/baselines/c3-report.json
    # Secondary: total gain over C2's final setting (post-processing + combination).
    uv run --no-sync python scripts/score_folds.py "$chosen" --incumbent "$FTG7" \
        --ids "@$REPORT" --allow-mismatch --output reports/baselines/c3-report-vs-plain.json
    ;;
  *) sed -n '2,16p' "$0"; exit 2 ;;
esac
