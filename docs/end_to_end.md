# End-to-End Pipeline

This page describes the full benchmark flow: prepare data, run inference, then evaluate and generate reports.

## 1) Prepare data

From repository root:

```bash
./prepare_data.sh --help
./prepare_data.sh rog_dialog
./prepare_data.sh --yes all
```

For detailed dataset-specific preparation, optional trimming behavior, and environment setup, see [Data preparation](data_preparation.md).

## 2) Build inference backends

Build all backend images:

```bash
./build_backends.sh
```

Or build one backend only:

```bash
docker build -t benchmark-pyannote models/pyannote
docker build -t benchmark-diarizen models/diarizen
docker build -t benchmark-nemo models/nemo
```

## 3) Run inference

Batch run across supported models for one dataset:

```bash
./run_inference.sh --dataset ROG-Dialog --hf-token "$HF_TOKEN"
```

If needed, include PyAnnote API key (for precision-2 cloud model):

```bash
./run_inference.sh --dataset ROG-Dialog --hf-token "$HF_TOKEN" --pyannote-key "$PYANNOTE_API_KEY"
```

If one backend/key is unavailable, run individual backends/models manually using:

- [Inference guide](inference.md)
- [PyAnnote backend README](../models/pyannote/README.md)
- [NeMo backend README](../models/nemo/README.md)
- [DiariZen backend README](../models/diarizen/README.md)

Important input handling detail:

- NeMo inference currently converts audio to mono and resamples to 16 kHz in its inference script due to model pipeline limitations.
- Other backends follow their own pipeline input handling.

## 4) Evaluate and generate reports

Use the universal report runner:

```bash
./scripts/run_evaluation_report.sh --help
./scripts/run_evaluation_report.sh --dataset rog_dialog --yes
./scripts/run_evaluation_report.sh --dataset all --yes
```

For full report options and dataset defaults, see [Evaluation and reporting](evaluation.md).

## Artifacts produced

- Data preparation:
  - Gold RTTM under `data/<Dataset>/ref_rttm/`
- Inference:
  - `results/<Dataset>/<run_folder>/*.rttm`
  - `results/<Dataset>/<run_folder>/benchmark_metadata.json`
- Evaluation/reporting:
  - Markdown report in `reports/.../*.md`
  - Machine-readable report in `reports/.../*.machine.json`
