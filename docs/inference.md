# Inference Guide

This guide explains how to run diarization inference in this repository, either as a batch run across supported models or as individual backend/model runs.

## Prerequisites

- Docker (and NVIDIA Container Toolkit for GPU-backed containers).
- Input audio prepared under `data/<Dataset>/audio`.
- Access credentials:
  - HuggingFace token for open-weights backends/models.
  - PyAnnote API key only when using `pyannote/speaker-diarization-precision-2`.

## Build backend images

From repository root, either build all backends at once:

```bash
./build_backends.sh
```

Or build individually:

```bash
docker build -t benchmark-pyannote models/pyannote
docker build -t benchmark-diarizen models/diarizen
docker build -t benchmark-nemo models/nemo
```

## Batch inference with `run_inference.sh`

The orchestrator script runs all configured models for a selected dataset:

```bash
./run_inference.sh --help
./run_inference.sh --dataset ROG-Dialog --hf-token "$HF_TOKEN"
./run_inference.sh --dataset ROG-Art --hf-token "$HF_TOKEN" --pyannote-key "$PYANNOTE_API_KEY"
```

Behavior to expect from `run_inference.sh`:

- Missing Docker images are reported and corresponding model runs are skipped.
- Missing HuggingFace token stops the script (required for most models).
- Missing PyAnnote API key only skips `pyannote/speaker-diarization-precision-2`.
- Outputs are written to `results/<Dataset>/<run_folder>/`.

## Individual backend/model runs

For backend-specific options, troubleshooting, and manual per-model commands, use:

- [PyAnnote backend README](../models/pyannote/README.md)
- [NeMo backend README](../models/nemo/README.md)
- [DiariZen backend README](../models/diarizen/README.md)

This manual path is useful when full batch inference is not possible (for example, no PyAnnote API key at run time, or you want to rerun only one backend/model).

## Important input handling note

- **NeMo backend** currently preprocesses audio to satisfy model/runtime constraints in its inference script: it converts multi-channel audio to mono and resamples audio to 16 kHz before diarization.
- **Other backends** use their own pipeline-level input handling and are not forced through this specific NeMo preprocessing path.

## Output layout

Inference artifacts are written under:

- `results/<Dataset>/<run_folder>/*.rttm`
- `results/<Dataset>/<run_folder>/benchmark_metadata.json`

These outputs are consumed by evaluation/reporting (see [Evaluation and reporting](evaluation.md)) and the full flow in [End-to-end pipeline](end_to_end.md).
