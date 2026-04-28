# Evaluation and reporting

This guide describes how to score diarization outputs and generate Markdown reports for the benchmarks in this repository (**ROG-Dialog**, **ROG-Art**, **CHILDES-CCPCL**).

## Preferred: `scripts/run_evaluation_report.sh`

From the **repository root**, use the helper script to build the evaluation Docker image (or fall back to `uv`) and run **`generate_report_universal.py`** with **trimmed gold** paths and dataset-appropriate defaults:

```bash
./scripts/run_evaluation_report.sh --help
./scripts/run_evaluation_report.sh -y
./scripts/run_evaluation_report.sh --dataset rog_art -y
./scripts/run_evaluation_report.sh --dataset childes_ccpcl --gold /path/to/ccpcl_gold_standard_trimmed.rttm -y
./scripts/run_evaluation_report.sh --dataset all --yes
```

- **ROG-Dialog:** uses `evaluation/DATASET_ERRATA.json` (manual UEM for that dataset).
- **ROG-Art / CCPCL:** does not use the repo manual errata file; an empty manual JSON is passed so only **auto** `AUTO_DATASET_ERRATA.json` beside the gold (if present) is merged.

Options include `--gold`, `--output`, `--results-dir`, `--metadata`, `--use-docker`, `--use-uv`, `--rebuild`, and `--` to forward extra arguments to the report generator. `-y`, `--yes`, `--batch`, and `--non-interactive` all skip prompts. If both Docker and `uv` fail, the script prints install hints and exits non-zero.

Use `--dataset all` to run `rog_dialog`, `rog_art`, and `childes_ccpcl` in that order with standard per-dataset paths. Dataset-specific overrides (`--gold`, `--metadata`, `--results-dir`, `--output`, `--errata`) are intentionally rejected in `all` mode; global flags and forwarded report-generator args apply to every dataset.

When using **Docker**, the script reuses the existing image tag when present and builds only when missing; pass `--rebuild` (or `--force-rebuild`) after code/dependency changes. The image no longer bakes in `evaluation/DATASET_ERRATA.json`; the runner bind-mounts the resolved manual errata file (or a temporary empty JSON for datasets without manual errata), so the same image can evaluate multiple datasets. The script also mounts the **directory** that contains `--gold` (not the RTTM file alone) so **`AUTO_DATASET_ERRATA.json`** in that same folder is visible in the container. Plain `docker run` examples that bind only a single `.rttm` file would not see auto errata unless you mount the whole `ref_rttm` directory (or add a second `-v` for the JSON).

For gold RTTM construction, trimming, and provenance headers, see [Reference RTTM design](reference_rttm_design.md). For preparing data and Python environments, see [Data preparation](data_preparation.md). For inference execution and the complete workflow, see [Inference guide](inference.md) and [End-to-end pipeline](end_to_end.md).

## Prerequisites

- **Repository root:** Run Docker examples from the directory that contains `data/`, `results/`, and `evaluation/`, or use absolute `-v` paths. Otherwise mounts can point at empty directories and the report will see **no models**.
- **Results layout:** `--results_dir` must contain **one subdirectory per model run**, each with `benchmark_metadata.json` and per-file `*.rttm` hypotheses (stem = gold file id).
- **Local Python:** From `evaluation/`, run `uv sync` then `uv run python generate_report.py --help` (see [evaluation/README.md](../evaluation/README.md)).
- **Docker image:** `cd evaluation && docker build -t benchmark-eval .`, or use [`scripts/run_evaluation_report.sh`](../scripts/run_evaluation_report.sh) to build and run in one step.

## Which gold RTTM to use

For published-style benchmarks, prefer **silence-trimmed** gold when it exists for a dataset:

| Dataset | Example trimmed gold path |
| --- | --- |
| ROG-Dialog | `data/ROG-Dialog/ref_rttm/default_gold_standard_trimmed.rttm` |
| ROG-Art | `data/ROG-Art/ref_rttm/default_gold_standard_trimmed.rttm` |
| CHILDES-CCPCL | `data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard_trimmed.rttm` |

Trimmed files carry `; gold_rttm …` and `; trim_params …` header lines; the report **§0 Gold RTTM** decodes these into tables. When trimming hits per-edge caps (`max_trim_s`), the gold pipeline may write **`AUTO_DATASET_ERRATA.json`** next to the trimmed RTTM (same directory). Reports and `score.py` **merge** that file with optional manual errata by default (see below).

## Manual errata (ROG-Dialog only in this repo)

The checked-in **[`evaluation/DATASET_ERRATA.json`](../evaluation/DATASET_ERRATA.json)** contains **ROG-Dialog** recording ids and transcription-boundary corrections. It is **not** populated for ROG-Art or CCPCL.

- **ROG-Dialog** examples: mount or pass `--errata` pointing at that JSON (or a host copy).
- **ROG-Art / CCPCL** examples: **omit** `--errata` and the Docker `-v …DATASET_ERRATA.json` mount unless you maintain a separate file for those datasets. Auto errata beside the gold RTTM is still loaded when present.

## Universal evaluation maps (UEM) and errata merge

- **Manual JSON** (`--errata`): map `file_id` → optional `trim_start`, `trim_end`, `reason`, optional `source`.
- **Auto JSON:** `dirname(<gold_rttm>) / AUTO_DATASET_ERRATA.json`, written by the gold preparation pipeline when residual silence remains beyond capped edge trim.
- **Merge (default):** per `file_id`, `trim_start` = max(manual, auto) when both set; `trim_end` = min(manual, auto) when both set. Metrics and timelines use `Timeline([Segment(eval_start, eval_end)])` intersected with per-file audio duration from `benchmark_metadata.json` (reports) or gold extent (`score.py`).
- **Disable auto file:** `generate_report.py` / `generate_report_universal.py` → `--no_auto_errata`; `score.py` → `--no-auto-errata`.

Section **§0** of generated reports includes manual vs auto tables and merged bounds when errata is loaded.

## Quick scoring (`evaluation/score.py`)

Scores one model folder against a single gold RTTM (no Markdown report). From the **repository root**, build the eval image once (`cd evaluation && docker build -t benchmark-eval .`).

**ROG-Dialog** (trimmed gold + manual errata):

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

**ROG-Art** (trimmed gold; omit `--errata` unless you supply a dataset-specific file):

```bash
docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Art:/data/rog" \
  -v "$(pwd)/results/ROG-Art/pyannote_3_1:/data/system" \
  benchmark-eval \
  score.py \
  --gold /data/rog/ref_rttm/default_gold_standard_trimmed.rttm \
  --system /data/system \
  --collar 0.25
```

## Full report: `generate_report.py` (ROG-Dialog defaults)

Default image `ENTRYPOINT` runs `generate_report.py`. Example with trimmed gold and **ROG-Dialog** errata:

```bash
cd evaluation
docker build -t benchmark-eval .
cd ..
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

Useful flags: `--no_auto_errata`, `--boundary_tolerance`, `--analysis_collar` (snapped to `COLLAR_SETTINGS` in code).

## Universal report: `generate_report_universal.py`

Override entrypoint to `python` and pass **`--dataset`** `rog_dialog` | `rog_art` | `childes_ccpcl`, plus **`--metadata`** (ROG speeches TSV or CCPCL `0demo.xlsx`).

**ROG-Dialog** (trimmed gold + manual errata):

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

**ROG-Art** (trimmed gold; **no** `DATASET_ERRATA.json` — not used for this dataset):

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

**CHILDES-CCPCL** (trimmed gold; **no** manual errata mount):

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

Optional: `--report_title`, `--report_filename`, `--category_axis_label`, `--audio_dir` (override directory used to probe audio format / sample rate / nominal PCM bitrate for the dataset overview), `--json_output`, `--no_json` (universal script).

## Machine-readable report JSON (`*.machine.json`)

`generate_report_universal.py` writes a second artifact next to the Markdown report: **`<report_filename_stem>.machine.json`** inside `--output` (for example `ROG_Dialog_Benchmark_Report.machine.json` when using the default Markdown name). Use **`--no_json`** to skip it, or **`--json_output path`** to set the file path (relative paths are resolved under `--output` unless absolute).

**Compatibility:** the document includes **`schema_version`** (currently **`"1.0"`**). Non-breaking additions (new optional keys) may appear without a bump; **removing or renaming keys** should bump `schema_version`.

**Top-level keys (v1.0):**

| Key | Meaning |
| --- | --- |
| `schema_version` | String schema tag for downstream parsers. |
| `generated_at` | UTC ISO-8601 timestamp. |
| `report` | Run metadata: title, `dataset`, absolute paths (`gold_rttm`, `results_dir`, `metadata`), evaluation knobs (`boundary_tolerance`, `analysis_collar_requested`, `domain_collar`), `markdown_report_filename`, optional `audio_dir_override`. |
| `gold_provenance` | Verbatim leading `comments` from the gold RTTM plus parsed string maps `gold_rttm` and `trim_params`. |
| `dataset` | `files`: array of per-recording records (`file_id`, `gold_timeline_span_s`, `gold_speech_s`, `metadata`, `errata`, optional `audio_probe`). |
| `dataset_aggregate` | Counts, duration aggregates, category histograms, and `audio_summary` (formats / sample rates when probing succeeded). |
| `models` | `huggingface_links` (display name → model id) and `summary_rows` (same metrics as the executive summary table, one row per model × collar). |
| `files` | Nested map: `file_id` → collar string (e.g. `"0.25"`) → model display name → per-file metric dict (as in the deep-dive tables). |
| `errata` | `merged_per_file` evaluation map and optional `merge_meta` from the errata loader. |

**Example (truncated):**

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-04-28T10:15:00+00:00",
  "report": {
    "title": "ROG-Dialog Benchmark Report",
    "dataset": "rog_dialog",
    "domain_collar": 0.25
  },
  "dataset": {
    "files": [
      {
        "file_id": "ROG-Dia-Example",
        "gold_timeline_span_s": 120.5,
        "gold_speech_s": 95.0,
        "audio_probe": null
      }
    ]
  },
  "models": {
    "huggingface_links": { "pyannote 3 1": "pyannote/speaker-diarization-3.1" },
    "summary_rows": []
  }
}
```

## Executive summary: how aggregates work

Headline **DER, JER, boundary F1, purity, coverage** are **micro-pooled only over files where the model produced a valid hypothesis** (`Status == OK` in per-file tables — the numerator of the **Completed** column). **Miss / FA / Conf** in that summary row are **means over the same OK files**. Failed or missing recordings still appear in per-file deep-dive sections with `FAIL` / `OOM/ERR` but do not inflate headline DER. A short note under the executive summary table states this explicitly.

## CCPCL: primary category (domain) axis

Participant metadata from `0demo.xlsx` uses CHILDES-style chronological age (`years;months`). For stratification (domain boxplots and tables), **`Domain`** is **`Age {Y} / {Gender}`** with **Y = whole years** (months collapsed) so categories are not fragmented by month. When month detail existed, it is preserved in **`Keywords`** as `chronological_age=…` (see `recording_metadata.load_ccpcl_0demo_xlsx`).

## Related files

| File | Role |
| --- | --- |
| `evaluation/generate_report.py` | ROG-Dialog-oriented report + metric implementation |
| `evaluation/generate_report_universal.py` | Multi-dataset report |
| `evaluation/score.py` | CLI DER breakdown for one run folder |
| `evaluation/errata_merge.py` | Manual + auto errata load/merge + markdown tables |
| `evaluation/gold_rttm_provenance.py` | Gold header parsing and §0 markdown |
| `evaluation/recording_metadata.py` | ROG TSV + CCPCL xlsx → `Domain` / metadata |
| `evaluation/dataset_summary.py` | Dataset overview + optional audio probing (Markdown §2 and machine JSON) |
