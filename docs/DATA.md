# Data: where to get it and how to set it up

Both datasets are public on Mozilla Data Collective (MDC). **Each team member downloads
their own copy** with their own free MDC account. Do not share archives with each other,
upload them anywhere, or commit them: MDC's terms forbid mirroring, and `.gitignore`
already excludes `data/`, `*.tar.gz` and audio files.

## 1. Lost in Transcription: Development Data (Spanish–English): evaluation set

| | |
|---|---|
| Page | https://mozilladatacollective.com/datasets/cmtj5u8dn006gnz08gjnknbji |
| License | CC-BY-SA-4.0 |
| Archive | ~16 MB `.tar.gz` (17,031,752 bytes, pinned in `configs/datasets.json`) |
| Content | ~35 min of WhatsApp voice notes from two Spanish–English bilinguals in North America; 155 clips (2–60 s, median ~13 s) with hand-corrected transcripts in `metadata.tsv` |

Rules on the dataset page: do not try to identify the speakers; no voice cloning and no
models that imitate the speakers.

## 2. Bangor Miami Spanish–English Corpus: training set

| | |
|---|---|
| Page | https://mozilladatacollective.com/datasets/cmmfulo4r018bnz07py4q9t09 |
| Original source and documentation | https://talkbank.org/biling/access/Bangor/Miami.html |
| License | GPL-3.0 |
| Archive | ~1.1 GB `.tar.gz` (MP3 audio, CHAT transcripts, word-level TSVs) |
| Content | 56 recorded conversations, ~35 h, 84 bilingual speakers in Miami |

Rules (dataset page and TalkBank):

- Cite it as the **Bangor Miami corpus**: Deuchar, M., & Parafita Couto, M. (2011).
  *The Bangor Miami Corpus*. TalkBank. doi:10.21415/T5J01D. MDC also asks for
  Deuchar et al. (2014), "Building bilingual corpora", *Advances in the Study of
  Bilingualism*.
- Send a copy of any publication that uses it to the corpus authors.
- **Do not train a large language model on it** unless all of that model's training
  data is public. Speech models are fine; an LLM-based transcript corrector trained on
  Bangor is not. This is why no LLM step exists in this repo.

## Download and verify

1. Sign in at https://mozilladatacollective.com, open each dataset page, accept the
   license, and click **Download**.
2. Ingest each archive. The script checks size and SHA-256 against
   `configs/datasets.json`, moves it into `data/downloads/`, extracts it to `data/raw/`,
   and writes a `PROVENANCE.json`:

   ```sh
   uv run python -m scripts.mdc_fetch ingest dev ~/Downloads/<dev archive>.tar.gz
   uv run python -m scripts.mdc_fetch ingest bangor_miami ~/Downloads/<bangor archive>.tar.gz \
     --accept-sha256 b2d3a0e4b6eadd9347bf79c97bdcca19fdb13e69c5a390009e849330545278a1
   ```

   The Bangor archive MDC serves does not match the catalog's listed checksum. The hash
   above is the one we verified on 2026-09-12 and accepted explicitly; if yours differs
   from **both** hashes, stop and tell the team before using it.

   Alternative: `uv run python -m scripts.mdc_fetch download dev` downloads through the
   MDC API if you set `MDC_API_KEY` (never commit or paste the key).

## Layout after ingest

```text
data/                       # gitignored
├── downloads/<alias>/      # verified archives
├── raw/dev/enspa_dev/      # dev clips + metadata.tsv
├── raw/bangor_miami/       # CHAT, MP3, word_level_tsvs/
├── processed/              # Bangor training segments, dev folds (built by scripts)
└── interim/predictions/    # per-run transcripts (contain Data-derived text)
```

## Working with the data

- Never paste transcripts, clip ids or audio into chat tools, issues or pull requests.
  Share aggregate numbers only; the scripts already write aggregates to `reports/`.
- Short examples for the final report (a few words around an error) are fine, with
  attribution to the dataset.
