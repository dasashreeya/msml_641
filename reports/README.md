# reports/

Results carried over from the prior work (`docs/PRIOR_WORK.md`): `baselines/` (zero-shot,
prompted, fine-tuned, k-fold held-out and combination runs, plus paired comparisons),
`finetune/` (training reports and run logs), and data summaries at the top level.

Committable outputs only: aggregate numbers (counts, WER, intervals), never transcript
text, clip ids, speaker codes or audio. The scripts write here through a leak guard
(`scripts/audit_data.py::assert_no_transcript_leak`).

Anything that contains Data (predictions, manifests, per-clip rows) goes under the
gitignored `data/` tree instead.
