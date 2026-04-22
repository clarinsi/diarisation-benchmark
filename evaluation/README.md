# **Diarization Evaluation & Reporting Module**

This module calculates diarization/segmentation metrics and generates comprehensive benchmark reports. It natively supports **UEM (Universal Evaluation Maps)** via a JSON errata file to account for dataset transcription errors.

## **1\. Structure**

* DATASET\_ERRATA.json: Configuration file defining regions of audio that should be ignored during evaluation (e.g., if the Gold Standard stops transcribing before the audio ends).  
* generate\_report.py: Generates the full Markdown report with visualizations.  
* score.py: Quick CLI tool to get the score for a single model.

## **2\. Local Python (uv)**

Install [uv](https://docs.astral.sh/uv/) if you do not already have it (see [Installing uv](../docs/data_preparation.md#installing-uv) in the data preparation guide). From this directory:

```bash
cd evaluation
uv sync
uv run python generate_report.py --help
uv run python score.py --help
```

To remove the local environment when you are done: `rm -rf .venv`.

The **`requirements.txt`** in this folder is generated from **`pyproject.toml`** / **`uv.lock`** (`uv export`) so the [Docker image](#3-building-the-docker-image) stays in sync with the uv project.

## **3\. Building the Docker Image**

```

cd evaluation
docker build -t benchmark-eval .

```

## **4\. Generating the Full Report**

The report generator scans every **subdirectory** of `--results_dir` (when you mount `results/ROG-Dialog`, that is one folder per model run, each containing `benchmark_metadata.json` and RTTMs).

```
# Evaluate with gold_standard_trimmed_15
docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/gold_standard_trimmed_15.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/ROG-Dia_GoldTrimmed_Report

```

### Metrics included in the report

- **DER** (Diarization Error Rate) + Miss/FA/Conf breakdown
- **JER** (Jaccard Error Rate)
- **Boundary P/R/F1** (segmentation boundary precision/recall/F1)
- **Purity/Coverage**

### Additional CLI arguments

- `--boundary_tolerance <float>`: tolerance window (seconds) for boundary precision/recall/F1. Default is `0.250`.
- `--analysis_collar <float>`: collar (seconds) used for domain-level boxplots and domain comparison tables. Default is `0.25`.\n  The value is **snapped** to the nearest collar in `COLLAR_SETTINGS` (currently `0.0` and `0.25`) to avoid float mismatch.

### Generate report on other "gold" rttm

Copy "gold" rttm (e.g. rog-dialog.rttm from root of this project) to path `data/ROG-Dialog/ref_rttm/your.rttm` and then start the generator by:

```
 
docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/your.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --boundary_tolerance 0.250 \
  --analysis_collar 0.25 \
  --output /data/reports/ROG-Dia_Test_Report

```

**Customizing Errata:**

If you find new errors in the dataset, simply edit evaluation/DATASET\_ERRATA.json on your host machine. Because we map it via \-v, the Docker container will immediately use your updated rules without requiring a rebuild.

## **5\. Quick Evaluation (score.py)**

If you just want the numbers for one model without generating the full report:

```

docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog/pyannote_3_1:/data/system" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  benchmark-eval \
  score.py \
  --gold /data/rog/ref_rttm/gold_standard.rttm \
  --system /data/system \
  --collar 0.25

```
