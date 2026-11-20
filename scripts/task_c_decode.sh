#!/usr/bin/env bash
# Task C decoding runs for ft-g7 (docs/TUNING_PROTOCOL.md).
#
#   scripts/task_c_decode.sh tune                 # all 11 tuning runs, back to back
#   scripts/task_c_decode.sh compare              # each tuning run vs c2-base (paired bootstrap)
#   scripts/task_c_decode.sh report -- <flags>    # final setting + baseline on the report folds,
#                                                 # <flags> = the chosen setting's flag change,
#                                                 # e.g.  report -- --beam-size 8
#                                                 # (no prompt: report -- --initial-prompt "")
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
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
