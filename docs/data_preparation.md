# Data preparation

This repository ships one shell script per benchmark dataset under the project root (`prepare_data_<dataset>.sh`). A thin dispatcher, [`prepare_data.sh`](../prepare_data.sh), lists available datasets from those filenames, prints detailed help when run with no arguments, and can run every dataset script in sequence (`all`).

## Quick start

```bash
# List datasets and read the full workflow description
./prepare_data.sh

# Prepare one corpus (examples)
./prepare_data.sh ccpcl
./prepare_data.sh rog_art
./prepare_data.sh rog_dialog
./prepare_data.sh --yes all

# Run every prepare_data_*.sh script in sorted order (separator lines between scripts)
./prepare_data.sh all
```

Run `./prepare_data.sh --help` for the same long help as running with no arguments.

## Non-interactive mode

Use `-y`, `--yes`, `--batch`, or `--non-interactive` with [`prepare_data.sh`](../prepare_data.sh) to run without prompts:

```bash
./prepare_data.sh --yes all
export DIABENCH_PYTHON="uv run --group trim python"
./prepare_data.sh --batch rog_dialog
```

In non-interactive mode:

- Silence trimming is enabled by default for datasets that support it.
- CCPCL stops with a non-zero exit code if the available `.wav` stems do not exactly match the embedded benchmark list.
- If trimming was requested but the trim environment is unavailable (for example missing `numpy` or `praat-parselmouth`) or the audio directory is invalid, the run exits non-zero instead of continuing without a trimmed RTTM.
- Download, unzip, and Python failures still stop the wrapper because the underlying scripts use `set -e`.

## Python environment (uv)

Use [uv](https://docs.astral.sh/uv/) to keep trimming and evaluation dependencies in project-local virtual environments (remove with `rm -rf .venv` at the repo root, or `rm -rf evaluation/.venv` for evaluation only).

### Installing uv

If `command -v uv` prints nothing, install **uv** before running `uv sync` (pick one):

```bash
# Official installer (adds ~/.local/bin/uv; restart the shell or add ~/.local/bin to PATH)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pipx
pipx install uv
```

Further options: [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

**Optional:** to let the trim helper script run that installer for you when `uv` is missing, use `DIABENCH_INSTALL_UV=1` with [`scripts/with_trim_env.sh`](../scripts/with_trim_env.sh) (see below).

### Silence trimming (data prep)

From the repository root:

```bash
uv sync --group trim
```

Optional EXB-related packages (`lxml`, pinned `exbee`):

```bash
uv sync --group trim --group trim-exb
```

Then either:

- Export **`DIABENCH_PYTHON`** so `prepare_data_*.sh` use the uv environment, for example after `uv sync --group trim`. The value may be **several words** (e.g. `uv run --group trim python`); the scripts split it into a command plus arguments, so use exactly:

  ```bash
  export DIABENCH_PYTHON="uv run --group trim python"
  ./prepare_data.sh rog_dialog
  ```

  Ensure **`uv`** is on `PATH` (often `~/.local/bin` after the Astral installer).

- Or run Python via **[`scripts/with_trim_env.sh`](../scripts/with_trim_env.sh)** (syncs groups then runs `uv run`):

  ```bash
  ./scripts/with_trim_env.sh ccpcl_data_process.py --help
  ```

Set **`DIABENCH_TRIM_EXB=1`** before calling `with_trim_env.sh` to include the `trim-exb` group. Set **`DIABENCH_INSTALL_UV=1`** to run the Astral `uv` installer when `uv` is not on `PATH`.

#### Building `praat-parselmouth` from source (Linux)

On many **aarch64** (ARM) machines there is **no prebuilt wheel**, so `uv sync --group trim` **builds** `praat-parselmouth` with CMake. That needs system compilers, CMake, Ninja, and **Python development headers** on the machine.

**Standard `pyproject.toml` / uv cannot declare or install apt or rpm packages** (only PyPI-style dependencies; uv does not invoke your OS package manager). This repo records a **documentation-only** list of Debian-style names under **`[tool.diarisation-benchmark.system-packages]`** in [`pyproject.toml`](../pyproject.toml) for copy-paste into `apt-get install`.

Example (Debian / Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build python3-dev
```

If `uv` uses a specific interpreter (e.g. **Python 3.12**) and errors still mention **`patchlevel.h`** or **`Could NOT find Python (missing: … Development.Module)`**, install headers for that minor version, for example:

```bash
sudo apt-get install -y python3.12-dev
```

If CMake reports **`unable to find a build program corresponding to "Ninja"`**, install **`ninja-build`** (see the first `apt-get` line above), then run `uv sync --group trim` again.

If the build fails with **`Does not match the generator used previously`** (**Ninja** vs **Unix Makefiles**), uv’s **cached extracted sdist** for `praat-parselmouth` has a stale `CMakeCache.txt`. Remove only that package cache, then sync again:

```bash
rm -rf ~/.cache/uv/sdists-v9/pypi/praat-parselmouth
uv sync --group trim --group trim-exb
```

Or run **`DIABENCH_CLEAR_PRAAT_UV_CACHE=1 ./scripts/with_trim_env.sh …`** once so the helper script deletes that cache directory before `uv sync`.

### Evaluation (reports and scoring)

```bash
cd evaluation
uv sync
uv run python generate_report.py --help
```

The Docker image for evaluation installs from [`evaluation/requirements.txt`](../evaluation/requirements.txt) (exported from that folder’s uv project). **Preferred:** run the universal report from the repo root with **[`scripts/run_evaluation_report.sh`](../scripts/run_evaluation_report.sh)** (Docker or `uv` fallback). **Manual** command-line examples, `score.py`, errata, and trimmed gold paths are in **[Evaluation and reporting](evaluation.md)**. The universal report also writes a **`.machine.json`** file (versioned schema); see [Machine-readable report JSON](evaluation.md#machine-readable-report-json-machinejson).

## Common options and defaults

| Topic | Behaviour |
| --- | --- |
| Shell strictness | Each `prepare_data_*.sh` uses `set -e` (abort on first failing command). |
| Gold RTTM merge / min duration | Python pipelines default to `merge_threshold=1.0` seconds and `min_duration=0.1` seconds via [`gold_rttm_from_annotations.py`](../gold_rttm_from_annotations.py). Shell scripts invoke `*data_process.py` without overriding these unless you edit the scripts. |
| Silence trimming | When prompted, enabling trimming requires **numpy** and **praat-parselmouth** and produces a trimmed RTTM alongside the base gold file where supported. Use **uv** and `DIABENCH_PYTHON` as in [Python environment (uv)](#python-environment-uv) to avoid installing these into the system Python. |
| Python interpreter for prep scripts | Defaults to `python3`. Override with **`DIABENCH_PYTHON`** (e.g. `uv run --group trim python`) so `prepare_data_*.sh` call your uv environment. |
| Forwarding arguments | After the dataset name, `prepare_data.sh` forwards remaining arguments to the underlying script. **ROG-Art**, **ROG-Dialog**, and **CCPCL** accept an optional first positional argument: the gold RTTM **basename** under `ref_rttm/` (`.rttm` is appended if missing). |

## Per-dataset preparation

### CHILDES-CCPCL (`ccpcl`)

- **Script:** [`prepare_data_ccpcl.sh`](../prepare_data_ccpcl.sh)
- **Manual download:** place TalkBank archive at `data/raw/CCPCL.zip` (see script output and [CCPCL appendix](data_ccpl.md) for links).
- **Extracts transcripts to:** `data/raw/CCPCL/` (nested `CCPCL/` directory is auto-detected for `.cha` files).
- **Audio:** place benchmark `.wav` files under `data/CHILDES-CCPCL/audio/`. The script checks stems against the fixed 20-file benchmark list embedded in the shell script. When WAVs are present it prints a **benchmark stem list**, then **stems found on disk**, then (if needed) **missing** and **extra** stems before any prompt.
- **Gold RTTM output:** `data/CHILDES-CCPCL/ref_rttm/<basename>.rttm`. Default basename **`ccpcl_gold_standard`** (same as the historical fixed path). Pass a first positional argument to `prepare_data_ccpcl.sh` or `./prepare_data.sh ccpcl …` to change the basename.

Further methodology and session table: [docs/data_ccpl.md](data_ccpl.md) (CCPCL corpus appendix).

### ROG-Art (`rog_art`)

- **Script:** [`prepare_data_rog_art.sh`](../prepare_data_rog_art.sh)
- **Downloads (when missing):** `ROG.zip` and `ROG-Art.wav.zip` from CLARIN.SI into `data/raw/`.
- **Layout:** `data/ROG-Art/` with `audio/`, `annotations/{trs,exb,exs}`, `docs/`, `ref_rttm/`.
- **Python:** [`rog_art_data_process.py`](../rog_art_data_process.py)
- **Optional argument:** first extra argument to `prepare_data.sh rog_art …` is the gold RTTM basename (default `default_gold_standard` → `default_gold_standard.rttm`).

### ROG-Dialog (`rog_dialog`)

- **Script:** [`prepare_data_rog_dialog.sh`](../prepare_data_rog_dialog.sh)
- **Downloads (when missing):** `ROG-Dialog.zip` and `ROG-Dialog_audio.zip` from CLARIN.SI into `data/raw/`.
- **Layout:** `data/ROG-Dialog/` with the same structural idea as ROG-Art.
- **Python:** [`rog_dialog_data_process.py`](../rog_dialog_data_process.py)
- **Optional argument:** first extra argument is the gold RTTM basename (same default as ROG-Art).

## Invoking dataset scripts directly

You may call the underlying scripts without the dispatcher:

```bash
./prepare_data_ccpcl.sh
./prepare_data_ccpcl.sh my_ccpcl_experiment
./prepare_data_rog_art.sh my_gold_name
./prepare_data_rog_dialog.sh
```

Behaviour is identical to `./prepare_data.sh <alias> …` for a single dataset.

## Related documentation

- [Inference guide](inference.md)
- [End-to-end pipeline](end_to_end.md)
- [Evaluation and reporting](evaluation.md)
- [Reference RTTM design](reference_rttm_design.md)
- [CCPCL corpus appendix (methodology and sample table)](data_ccpl.md)
