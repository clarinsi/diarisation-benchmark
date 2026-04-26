# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Diarizen inference backend** (`models/diarizen/`): Dockerfile, README, and `run_inference.py`
- **Benchmark outputs:** reorganized `results/`; CCPCL and ROG-Art RTTMs and `benchmark_metadata.json` (ROG-Art run folders: `pyannote_3_1`, `pyannote_community_1`, `speaker-diarization-precision-2`, `reverb-diarization-v2`, `diarizen`, `diarizen_v2`, `diar_sortformer_4spk-v1`, `diar_streaming_sortformer_4spk-v2`, `diar_streaming_sortformer_4spk-v2.1`)
- **Data prep dispatcher:** `prepare_data.sh` lists/runs root `prepare_data_<dataset>.sh` scripts; `docs/data_preparation.md` documents workflows and uv-based trim environments
- **uv lockfiles and trim env:** root `pyproject.toml` / `uv.lock` with optional groups `trim` and `trim-exb`; `scripts/with_trim_env.sh` to run tools under those groups; `evaluation/pyproject.toml` / `evaluation/uv.lock` for evaluation-only installs

### Changed

- **Shared inference plumbing:** updates to `models/nemo/run_inference.py`, `models/pyannote/run_inference.py`, pyannote Dockerfile, and `build_backends.sh` for multi-backend use
- **Model runners:** consistent English user-facing log messages in `models/pyannote`, `models/nemo`, and `models/diarizen` `run_inference.py`
- **Prepare pipelines:** unified CLI arguments across `prepare_data_*.sh` and optional silence-trim path integrated into those scripts; user-facing shell messages switched to English
- **Reporting:** ROG-Dialog benchmark report refreshed to include all models
- **Docs and packaging notes:** expanded `docs/data_ccpl.md`, `evaluation/requirements.txt`, `evaluation/README.md`, root `README.md`, and `docs/reference_rttm_design.md`; `.gitignore` and small edits in `compare_rttm.py`, `gold_rttm_from_annotations.py`, and dataset processors

### Fixed

- **CCPCL:** preprocessing and `prepare_data_ccpcl.sh` / `ccpcl_data_process.py` fixes
- **Pyannote runner:** when a remote/API pipeline rejects `hook=`, fall back to calling the pipeline without a progress hook for the remainder of the run (avoids `SDK.apply() got an unexpected keyword argument 'hook'`)

## [0.2.2] - 2026-04-16

### Added

- **Evaluation reporting: additional metrics**
  - `evaluation/generate_report.py` now computes and reports:
    - JER (Jaccard Error Rate)
    - boundary precision/recall and boundary F1 (with configurable tolerance)
  - new CLI flags for report generator:
    - `--boundary_tolerance` (default `0.250`)
    - `--analysis_collar` (default `0.25`) for domain plots/tables

### Changed

- **Visual & Domain Analysis** in the generated report now includes:
  - collar impact barplots for DER, JER, and Boundary F1
  - per-domain distribution plots and domain comparison tables for DER, JER, and Boundary F1
  - a shared model legend for domain comparison tables to reduce report size

## [0.2.1] - 2026-04-02

### Added

- **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)**
  - `prepare_data_ccpcl.sh`: archive presence check, extraction workflow, WAV presence prompt, and optional RTTM generation launch
  - `ccpcl_data_process.py`: `.cha` parser + linear merge + min duration + RTTM writer

## [0.2.0] - 2026-04-02

### Added

- **ROG-Art dataset support (Training corpus of spoken Slovenian ROG 1.1)**
  - `prepare_data_rog_art.sh`: download/unzip + reorganize + cleanup workflow
  - `rog_art_data_process.py`: filtered multi-speaker subset extraction and RTTM generation
  - multi-speaker selection from `ROG-speeches.tsv` using `SPK-IDsUTTS`
  - output RTTM naming, merge threshold, min duration, and .pog/.std selection toggles

- **ROG-Dialog pipeline hardening**
  - `prepare_data_rog_dialog.sh` with dataset existence check and skipped reorganization
  - `rog_dialog_data_process.py` parameterized, required `--output_filename`, improved help text
  - shared dataset reorganization + idempotent behavior for repeated runs

- **Docs update**
  - `docs/reference_rttm_design.md` now references new dataset scripts (`rog_dialog_data_process.py`, `rog_art_data_process.py`) instead of legacy script
  - minimal commands for reproducing gold RTTM pipeline

### Changed

- changed cleanup to preserve downloaded zip archives (`data/raw/*.zip`) while removing extracted `data/raw/data` directories
- `rog_art_data_process.py` now checks fallback metadata location in `data/ROG-Art/docs/ROG-speeches.tsv` when source path is missing

## [0.1.0] - 2026-03-01

### Added

- **Automated Dataset Management**: Scripts for downloading ROG-Dialog dataset and generating gold standard RTTM from TRS format
  - `prepare_data.sh`: Dataset download and setup automation
  - `convert_trs_to_rttm.py`: TRS to RTTM format conversion
  - Maintains reference `rog-dialog.rttm` for comparison

- **Inference Pipeline**: Complete ML model evaluation framework
  - **PyAnnote Models** (`models/pyannote/`): Inference runner for pyannote-compatible speaker diarization models
    - Support for legacy 3.1, community-1, and precision-2 variants
    - Docker containerization for reproducible environments
  - **NVIDIA Softformer Models** (`models/nemo/`): Inference runner for diar_sortformer family
    - Support for offline (v1) and streaming (v2, v2.1) variants
    - Optimized for high-performance GPUs (Grace Blackwell/Hopper/Ampere)

- **Evaluation & Reporting Module** (`evaluation/`)
  - `score.py`: Quick CLI tool for DER calculation against gold standard
    - Supports configurable collar values and margin settings
  - `generate_report.py`: Comprehensive benchmark report generation with visualizations
    - Multi-metric evaluation: DER (Diarization Error Rate), Purity, Coverage
    - Dataset-specific errata handling via UEM (Universal Evaluation Maps)
    - Automated processing of all model results
  - `DATASET_ERRATA.json`: Configuration for handling transcription errors in dataset

- **Benchmark Results & Reports**
  - Multiple model evaluations across ROG-Dialog dataset
  - Result collections: pyannote_3_1, pyannote_community_1, pyannote_precision_2, diar_sortformer variants
  - Generated benchmark reports with comparative analysis

- **Documentation**
  - Module-specific READMEs with usage instructions and Docker commands
  - Markdown reports with visualizations and detailed metrics
  - Root reference documentation on dataset, models, and evaluation methodology
