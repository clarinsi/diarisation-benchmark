# Diarization evaluation and reporting

This module computes diarization and segmentation metrics (DER, JER, boundary P/R/F1, purity, coverage) and writes Markdown reports with plots. It supports **UEM** via merged **manual** and **auto** errata JSON next to the gold RTTM.

**Preferred way to run the universal report:** from the repository root, [`../scripts/run_evaluation_report.sh`](../scripts/run_evaluation_report.sh) (reuses/builds the Docker image or uses `uv`, then runs `generate_report_universal.py` with trimmed-gold defaults). Use `--dataset all --yes` to evaluate all supported datasets in sequence; `--batch` / `--non-interactive` are aliases for `--yes`, and `--rebuild` forces a Docker image rebuild.

**Full operator guide (Docker, datasets, errata, aggregates):** [../docs/evaluation.md](../docs/evaluation.md)

**Machine-readable output:** `generate_report_universal.py` writes **`<report_filename_stem>.machine.json`** in `--output` by default (for example `ROG_Dialog_Benchmark_Report.machine.json`). Use `--no_json` to skip or `--json_output` to set the path. Schema and keys: [Machine-readable report JSON](../docs/evaluation.md#machine-readable-report-json-machinejson).

## Structure

| Artifact / script | Purpose |
| --- | --- |
| `DATASET_ERRATA.json` | **Manual** UEM corrections; entries in the repo file are **ROG-Dialog** ids only. Use `--errata` for ROG-Dialog; omit for ROG-Art/CCPCL unless you maintain a separate file. |
| `AUTO_DATASET_ERRATA.json` | **Auto** errata written beside **trimmed** gold when silence trim is capped; auto-loaded from `dirname(gold)`. |
| `errata_merge.py` | Merge manual + auto; markdown tables for the report. |
| `generate_report.py` | ROG-Dialog-oriented report (default Docker `ENTRYPOINT`). |
| `generate_report_universal.py` | Same metrics for `rog_dialog`, `rog_art`, `childes_ccpcl`. |
| `gold_rttm_provenance.py` | §0 Gold RTTM: header comments, decoded KV tables, errata subsection. |
| `recording_metadata.py` | ROG TSV + CCPCL `0demo.xlsx` → `Domain` / fields (CCPCL `Domain` uses **whole-year** age for stratification). |
| `dataset_summary.py` | Dataset overview stats and optional audio probing (Markdown §2 + `.machine.json`). |
| `score.py` | Quick per-run DER breakdown (CLI). |

## Local Python (uv)

Install [uv](https://docs.astral.sh/uv/) if needed (see [Installing uv](../docs/data_preparation.md#installing-uv)). From this directory:

```bash
cd evaluation
uv sync
uv run python generate_report.py --help
uv run python generate_report_universal.py --help
uv run python score.py --help
```

Remove the venv when finished: `rm -rf .venv`.

`requirements.txt` is exported from `pyproject.toml` / `uv.lock` for the Docker image.

## Docker image

```bash
cd evaluation
docker build -t benchmark-eval .
```

## Reporting: prefer trimmed gold

For benchmark-style evaluation, prefer **trimmed** gold RTTMs when available (see [Reference RTTM design](../docs/reference_rttm_design.md)):

- ROG-Dialog: `data/ROG-Dialog/ref_rttm/default_gold_standard_trimmed.rttm`
- ROG-Art: `data/ROG-Art/ref_rttm/default_gold_standard_trimmed.rttm`
- CCPCL: `data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard_trimmed.rttm`

Run `docker` from the **repository root** so `$(pwd)/data` and `$(pwd)/results` resolve correctly.

### ROG-Dialog (`generate_report.py`, with manual errata)

```bash
docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/default_gold_standard_trimmed.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --errata /app/DATASET_ERRATA.json \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/ROG_Dia_GoldTrimmed_Report
```

### Universal script (examples)

**ROG-Dialog** — mount manual errata (same as above). **ROG-Art** and **CCPCL** — do **not** mount `DATASET_ERRATA.json` unless you have a dataset-specific file.

```bash
docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  generate_report_universal.py \
  --dataset rog_dialog \
  --gold /data/rog/ref_rttm/default_gold_standard_trimmed.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --errata /app/DATASET_ERRATA.json \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/ROG_Dialog_Universal_Report
```

```bash
docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Art:/data/rog" \
  -v "$(pwd)/results/ROG-Art:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  generate_report_universal.py \
  --dataset rog_art \
  --gold /data/rog/ref_rttm/default_gold_standard_trimmed.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-speeches.tsv \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/ROG_Art_Universal_Report
```

```bash
docker run --rm --entrypoint python \
  -v "$(pwd)/data/CHILDES-CCPCL:/data/ccpcl" \
  -v "$(pwd)/results/CHILDES-CCPCL:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  generate_report_universal.py \
  --dataset childes_ccpcl \
  --gold /data/ccpcl/ref_rttm/ccpcl_gold_standard_trimmed.rttm \
  --results_dir /data/results \
  --metadata /data/ccpcl/docs/0demo.xlsx \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/CCPCL_Universal_Report
```

## Metrics and CLI flags (summary)

- DER, JER, Miss/FA/Conf, boundary P/R/F1, purity, coverage.
- `--boundary_tolerance` (default `0.250` s) for boundary metrics.
- `--analysis_collar` (default `0.25` s) for category/domain plots; snapped to `COLLAR_SETTINGS` in code.
- `--no_auto_errata` — skip `AUTO_DATASET_ERRATA.json` beside `--gold` (reports).
- `--no-auto-errata` — same for `score.py`.

**Errata schema (per `file_id`):** optional `trim_start`, `trim_end`, `reason`, optional `source`. Merge: `trim_start` = max of both sources; `trim_end` = min. See [docs/evaluation.md](../docs/evaluation.md).

**Executive summary:** Headline DER/JER/… are pooled only over per-file **`Status == OK`** (same set as the **Completed** numerator); failed files are listed in the deep dive but excluded from those headline aggregates (see note in generated report).

## Quick score (`score.py`)

**ROG-Dialog** with manual errata:

```bash
docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog/pyannote_3_1:/data/system" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  benchmark-eval \
  score.py \
  --gold /data/rog/ref_rttm/default_gold_standard_trimmed.rttm \
  --system /data/system \
  --errata /app/DATASET_ERRATA.json \
  --collar 0.25
```

For ROG-Art/CCPCL, omit `--errata` and the errata volume unless you supply your own JSON.
