# diarisation-benchmark
First steps in setting up a diarisation benchmark for Slovenian and related languages

## Dataset

We currently support three datasets:

- **ROG-Dialog** (primary benchmark)
  - official source: http://hdl.handle.net/11356/2073
  - use `prepare_data_rog_dialog.sh` to download/unpack/reorganize and generate `data/ROG-Dialog/ref_rttm/*.rttm`
  - converter: `rog_dialog_data_process.py` (merge/min filtering, optional `.pog` vs `.std` selection)

- **ROG Art** (Training corpus of spoken Slovenian ROG 1.1)
  - official source: https://www.clarin.si/repository/xmlui/handle/11356/2062
  - use `prepare_data_rog_art.sh` to download/unpack/reorganize and generate `data/ROG-Art/ref_rttm/*.rttm`
  - converter: `rog_art_data_process.py` (multi-speaker subset from `ROG-speeches.tsv`, merge/min filtering, `.pog`/`.std` preference)
  - this benchmark uses only multi-speaker recordings as filtered by `SPK-IDsUTTS`

- **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)**
  - source: requires registration/login via https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html
  - download archive manually to `data/raw/CCPCL.zip`, then run `./prepare_data_ccpcl.sh` (optional first argument: gold RTTM basename, default `ccpcl_gold_standard`; see [docs/data_preparation.md](docs/data_preparation.md))
  - `prepare_data_ccpcl.sh` extracts to `data/raw/CCPCL`, validates `.wav` availability and optionally runs `ccpcl_data_process.py`
  - `ccpcl_data_process.py` reads `data/raw/CCPCL/CCPCL/*.cha` (or nested layout resolved by the shell script), writes `data/CHILDES-CCPCL/ref_rttm/<basename>.rttm` with the same merge/min-duration defaults as other datasets

## Models

Explicit supported model names (canonical Hugging Face or vendor ids), as stored in each run’s `benchmark_metadata.json` under `model_name`:

**NVIDIA NeMo (Sortformer)**

- `nvidia/diar_sortformer_4spk-v1`
- `nvidia/diar_streaming_sortformer_4spk-v2`
- `nvidia/diar_streaming_sortformer_4spk-v2.1`

**PyAnnote**

- `pyannote/speaker-diarization-3.1`
- `pyannote/speaker-diarization-community-1`
- `pyannote/speaker-diarization-precision-2`

**Revai**

- `Revai/reverb-diarization-v2`

**DiariZen**

- `BUT-FIT/diarizen-wavlm-large-s80-md`
- `BUT-FIT/diarizen-wavlm-large-s80-md-v2`

Metadata for reporting is read from `results/<Dataset>/<run_folder>/benchmark_metadata.json` (for example `results/ROG-Dialog/pyannote_3_1/benchmark_metadata.json`). The `run_folder` names in the repo mirror the benchmark layout (e.g. `diarizen`, `diar_streaming_sortformer_4spk-v2`, `speaker-diarization-precision-2`).

Inference backends: `models/pyannote/`, `models/nemo/`, `models/diarizen/`, and Revai via the pyannote container where applicable—see each module’s README.


## Evaluation

**Preferred:** from the repository root, run [`scripts/run_evaluation_report.sh`](scripts/run_evaluation_report.sh) (`--help` lists options; builds the eval Docker image or falls back to `uv`). Full detail (Docker/`uv`, **trimmed gold**, **errata** — manual file **ROG-Dialog only** in this repo, optional **auto** `AUTO_DATASET_ERRATA.json`, **OK-only** headline aggregates) is in **[docs/evaluation.md](docs/evaluation.md)**. Module-level notes: [evaluation/README.md](evaluation/README.md).

The Markdown report includes DER / Miss / FA / Conf, JER, boundary P/R/F1, purity and coverage, hardware RTF/VRAM, per-file deep dive, and (for `generate_report_universal.py`) category plots driven by dataset metadata.

Additional report controls:
- `--boundary_tolerance` — boundary P/R/F1 tolerance (seconds)
- `--analysis_collar` — collar for category/domain plots and tables (snapped to `COLLAR_SETTINGS`)
- `--no_auto_errata` — skip merged auto errata beside `--gold` (reports); `--no-auto-errata` on `score.py`

## Python environments (uv)

Optional [uv](https://docs.astral.sh/uv/) setups isolate **silence-trimming** dependencies (Parselmouth) and the **evaluation** stack from your system Python. Install **uv** first if it is missing (see [Installing uv](docs/data_preparation.md#installing-uv)), then follow [Python environment (uv)](docs/data_preparation.md#python-environment-uv): `uv sync --group trim` at the repo root, `export DIABENCH_PYTHON="uv run --group trim python"` before `./prepare_data.sh …`, and `cd evaluation && uv sync` for reports. Remove the envs when finished: `rm -rf .venv` (repo root) and `rm -rf evaluation/.venv`.


# Peter : Running the pipeline through and through

1. Download the data:

`bash prepare_data.sh`

2. Run pyannote:
    1. Build the docker image:

    ```bash
    cd models/pyannote
    docker build -t benchmark-pyannote .
    cd ../..
    ```

    2. Run first model:

    ```bash
    sudo docker run --rm \
        -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
        -v "$(pwd)/results/ROG-Dialog/pyannote_3_1:/data/output" \
        -e HOST_UID=$(id -u) \
        -e HOST_GID=$(id -g) \
        -e HF_TOKEN="YOURTOKEN" \
        benchmark-pyannote \
        --input /data/audio \
        --output /data/output \
        --model pyannote/speaker-diarization-3.1
    ```

    This works, but on GPU2 there is no docker, and on my laptop, there is no GPU.

    Consequently, processing takes ages, with RTF = 2!


3. Nemo models:
   1. Build the docker image:

    ```bash
    cd models/nemo
    sudo docker build -t benchmark-nemo .
    cd ../..
    ```

    2. Run first model:

    ```bash
    sudo docker run --rm \
        -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
        -v "$(pwd)/results/ROG-Dialog/diar_streaming_sortformer_4spk-v2:/data/output" \
        -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
        -e HOST_UID=$(id -u) \
        -e HOST_GID=$(id -g) \
        -e HF_TOKEN="YOURTOKEN" \
        benchmark-nemo \
        --input /data/audio \
        --output /data/output
    ```

    This runs faster, with RTF of 0.1 cca.

4. DiariZen models:

   Build and run as in [models/diarizen/README.md](models/diarizen/README.md) (CPU-oriented image; mount `results/ROG-Dialog/diarizen` or `results/ROG-Dialog/diarizen_v2` for output). Example:

   ```bash
   cd models/diarizen
   docker build -t benchmark-diarizen .
   cd ../..

   sudo docker run --rm \
     -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
     -v "$(pwd)/results/ROG-Dialog/diarizen_v2:/data/output" \
     -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
     -e HOST_UID=$(id -u) \
     -e HOST_GID=$(id -g) \
     -e HF_TOKEN="YOURTOKEN" \
     benchmark-diarizen \
     --input /data/audio \
     --output /data/output \
     --model BUT-FIT/diarizen-wavlm-large-s80-md-v2
   ```

5. Run the eval

```bash
cd evaluation
sudo docker build -t benchmark-eval .
cd ..

sudo docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/ROG-Dialog:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/gold_standard_trimmed_15.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --errata /app/DATASET_ERRATA.json \
  --output /data/reports/ROG-Dia-Trim
```

# Ivan: Auto-trim silences from Gold intervals with Praat (Apr2026)

Human-annotated segment boundaries in the gold RTTM often include leading/trailing silence (annotators clicking a bit too early or too late). The `trim_gold_silences_rttm.py` module uses Praat's pitch and intensity analysis (via Parselmouth) to detect actual speech onset/offset and tighten those boundaries automatically. It can also split segments at long internal silences.

## What it does

- Loads each audio file and analyses segments using pitch detection + intensity relative to segment peak
- Trims segment edges to where speech actually starts/ends, with a configurable guard margin
- Optionally splits segments at internal silences (e.g. ≥500ms gaps within a single annotation)
- Drops segments that become too short after trimming (configurable threshold)
- Writes results incrementally per file (crash-safe — no data lost if it fails mid-run)

### Impact of Gold Standard Trimming on Evaluation Metrics

Trimming the gold standard consistently lowers DER across all models, driven almost entirely by reduced Miss rates — the original annotations include silence at segment edges that unfairly penalizes models for not predicting speech where there is none. FA increases slightly (smaller speech denominator), while Confusion stays stable since trimming doesn't affect speaker identity.

Example using the best-performing model (pyannote speaker-diarization-precision-2, collar=0.25):

| Metric   | Original Gold | Trimmed Gold |
| -------- | ------------- | ------------ |
| DER      | 20.25%        | **9.52%**    |
| Miss     | 17.40%        | **5.78%**    |
| FA       | **1.26%**     | 2.37%        |
| Conf     | **1.22%**     | 1.36%        |
| Purity   | **86.91%**    | 86.89%       |
| Coverage | **89.32%**    | 89.09%       |

The trimmed evaluation better reflects actual diarisation performance by removing measurement artifacts from imprecise annotation boundaries.

## Two ways to use it

### 1. Standalone CLI (trim an existing RTTM)

```bash
python trim_gold_silences_rttm.py \
    --rttm data/ROG-Dialog/ref_rttm/gold_standard.rttm \
    --audio-dir data/ROG-Dialog/audio \
    --output data/ROG-Dialog/ref_rttm/gold_trimmed.rttm \
    --trim-silence-within \
    --verbose
```

Run `python trim_gold_silences_rttm.py --help` for all options (pitch range, intensity threshold, guard margin, max trim, etc.).

### 2. Integrated in the TRS→RTTM pipeline (recommended)

`convert_trs_to_trim_rttm.py` imports the trimming module and runs the full pipeline: parse TRS → merge segments → trim with audio → write RTTM + optional EXB files. All settings are configured at the top of the script:

```python
ENABLE_TRIMMING = True       # set False to skip audio analysis
GENERATE_EXB = True          # generate EXB files for visual inspection
TRIM_PARAMS = TrimParams(
    intensity_drop_db=15.0,  # dB below segment peak = "silence"
    trim_silence_within=True,
    min_silence_dur=0.5,
    verbose=False,
    # ... other params with sensible defaults
)
```

```bash
python convert_trs_to_trim_rttm.py
```

Output filename is automatic: `gold_standard_trimmed_{int}db.rttm` when trimming is on, `gold_standard.rttm` when off. A `_metadata.txt` file with full parameters and statistics is written alongside.

### EXB output

When `GENERATE_EXB = True`, the script produces EXB files with `[Dia_gold_trim]` tiers that can be opened in EXMARaLDA Partitur Editor alongside the original transcription tiers for visual verification of trim quality.

### Note on file_id

TRS filenames (e.g. `ROG-Dia-GSO-P0005-std.trs`) are stripped of `-std`/`-pog` suffixes to derive the file ID (`ROG-Dia-GSO-P0005`). This must match the corresponding `.wav` and `.exb` filenames.