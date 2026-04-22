# DiariZen Benchmarking Module

This module enables benchmarking of the DiariZen speaker diarization models
from HuggingFace:

- `BUT-FIT/diarizen-wavlm-large-s80-md`
- `BUT-FIT/diarizen-wavlm-large-s80-md-v2`

These models require a HuggingFace token with accepted model licensing.
Weights are released under CC BY-NC 4.0, so please ensure non-commercial use.

## Prerequisites

1. Docker.
2. A valid HuggingFace token with access to the DiariZen model repository.
3. Optional: mount your local HuggingFace cache to avoid repeated downloads.

## 1. Build the Docker image

```
cd models/diarizen
docker build -t benchmark-diarizen .
```

## 2. Run the benchmark

```
docker run --gpus all --rm \
  -v "$(pwd)/../../data/ROG-Dialog/audio:/data/audio" \
  -v "$(pwd)/../../results/ROG-Dialog/diarizen_v2:/data/output" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  -e HF_TOKEN="YOUR_HUGGINGFACE_TOKEN" \
  benchmark-diarizen \
  --input /data/audio \
  --output /data/output \
  --model BUT-FIT/diarizen-wavlm-large-s80-md-v2
```

> Note: this image installs CPU-only PyTorch wheels and is compatible with ARM hosts. GPU support is not enabled in this container.

### Supported models

- `BUT-FIT/diarizen-wavlm-large-s80-md`
- `BUT-FIT/diarizen-wavlm-large-s80-md-v2`

The default model is `BUT-FIT/diarizen-wavlm-large-s80-md-v2`.

## 3. Output

The benchmark produces:

1. `*.rttm` files in the output directory
2. `benchmark_metadata.json` with performance metrics

## Notes

- If GPU is not available, the script will fall back to CPU, but inference may be much slower.
- Mounting the HuggingFace cache directory is strongly recommended to avoid repeated model downloads.
- The script writes RTTM files directly to the output directory using the session name.
