#!/bin/bash

usage() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Run diarisation benchmark for the specified dataset."
  echo ""
  echo "Options:"
  echo "  -h, --help                    Show this help message"
  echo "  -t, --hf-token TOKEN          Set HuggingFace token"
  echo "  -p, --pyannote-key KEY        Set PyAnnote API key"
  echo "  -d, --dataset DATASET         Set dataset (default: ROG-Art)"
  echo ""
  echo "Examples:"
  echo "  $0 -t your_hf_token -p your_pyannote_key"
  echo "  $0 --dataset ROG-Dialog --hf-token your_token"
}

# Parse arguments
HF_TOKEN_ARG=""
PYANNOTE_API_KEY_ARG=""
DATASET_ARG=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      usage
      exit 0
      ;;
    -t|--hf-token)
      HF_TOKEN_ARG="$2"
      shift 2
      ;;
    -p|--pyannote-key)
      PYANNOTE_API_KEY_ARG="$2"
      shift 2
      ;;
    -d|--dataset)
      DATASET_ARG="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Set variables
if [ -n "$HF_TOKEN_ARG" ]; then
  HF_TOKEN="$HF_TOKEN_ARG"
else
  HF_TOKEN="YOUR_HUGGINGFACE_TOKEN"
fi

if [ -n "$PYANNOTE_API_KEY_ARG" ]; then
  PYANNOTE_API_KEY="$PYANNOTE_API_KEY_ARG"
else
  PYANNOTE_API_KEY="YOUR_PYANNOTE_API_KEY"
fi

if [ -n "$DATASET_ARG" ]; then
  DATASET="$DATASET_ARG"
else
  DATASET="ROG-Art"
fi

HOST_PWD="$(pwd)"
DATA_DIR="$HOST_PWD/data/$DATASET"
RESULT_DIR="$HOST_PWD/results/$DATASET"

if [ -z "$HF_TOKEN" ] || [ "$HF_TOKEN" = "YOUR_HUGGINGFACE_TOKEN" ]; then
  echo "ERROR: HF_TOKEN is not set. Pass -t/--hf-token or set HF_TOKEN before running run_inference.sh."
  exit 1
fi

# Check for required Docker images
REQUIRED_IMAGES=("benchmark-pyannote" "benchmark-diarizen" "benchmark-nemo")
MISSING_IMAGES=()

for image in "${REQUIRED_IMAGES[@]}"; do
  if [ -z "$(docker images -q "$image")" ]; then
    MISSING_IMAGES+=("$image")
    echo "WARNING: Docker image '$image' not found. Corresponding runs will be skipped."
  fi
done

if [ ${#MISSING_IMAGES[@]} -gt 0 ]; then
  echo "WARNING: The following Docker images are missing: ${MISSING_IMAGES[*]}"
  echo "Please build or pull them before running this script."
fi

# pyannote/speaker-diarization-3.1
if [ -n "$(docker images -q benchmark-pyannote)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/pyannote_3_1:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    -e HF_TOKEN="$HF_TOKEN" \
    benchmark-pyannote \
    --input /data/audio \
    --output /data/output \
    --model pyannote/speaker-diarization-3.1
else
  echo "WARNING: Skipping pyannote/speaker-diarization-3.1 run because Docker image 'benchmark-pyannote' is missing."
fi
# pyannote/speaker-diarization-community-1
if [ -n "$(docker images -q benchmark-pyannote)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/pyannote_community_1:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    -e HF_TOKEN="$HF_TOKEN" \
    benchmark-pyannote \
    --input /data/audio \
    --output /data/output \
    --model pyannote/speaker-diarization-community-1
else
  echo "WARNING: Skipping pyannote/speaker-diarization-community-1 run because Docker image 'benchmark-pyannote' is missing."
fi

#  Revai/reverb-diarization-v2
if [ -n "$(docker images -q benchmark-pyannote)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/reverb-diarization-v2:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    -e HF_TOKEN="$HF_TOKEN" \
    benchmark-pyannote \
    --input /data/audio \
    --output /data/output \
    --model Revai/reverb-diarization-v2
else
  echo "WARNING: Skipping Revai/reverb-diarization-v2 run because Docker image 'benchmark-pyannote' is missing."
fi
# BUT-FIT/diarizen-wavlm-large-s80-md-v2
if [ -n "$(docker images -q benchmark-diarizen)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/diarizen_v2:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    benchmark-diarizen \
    --input /data/audio \
    --output /data/output \
    --model BUT-FIT/diarizen-wavlm-large-s80-md-v2
else
  echo "WARNING: Skipping BUT-FIT/diarizen-wavlm-large-s80-md-v2 run because Docker image 'benchmark-diarizen' is missing."
fi

# BUT-FIT/diarizen-wavlm-large-s80-md-v2
if [ -n "$(docker images -q benchmark-diarizen)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/diarizen:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    benchmark-diarizen \
    --input /data/audio \
    --output /data/output \
    --model BUT-FIT/diarizen-wavlm-large-s80-md
else
  echo "WARNING: Skipping BUT-FIT/diarizen-wavlm-large-s80-md run because Docker image 'benchmark-diarizen' is missing."
fi

# nvidia/diar_streaming_sortformer_4spk-v2
if [ -n "$(docker images -q benchmark-nemo)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/diar_streaming_sortformer_4spk-v2:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    benchmark-nemo \
    --input /data/audio \
    --output /data/output \
    --model nvidia/diar_streaming_sortformer_4spk-v2
else
  echo "WARNING: Skipping nvidia/diar_streaming_sortformer_4spk-v2 run because Docker image 'benchmark-nemo' is missing."
fi

# nvidia/diar_streaming_sortformer_4spk-v2.1
if [ -n "$(docker images -q benchmark-nemo)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/diar_streaming_sortformer_4spk-v2.1:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    benchmark-nemo \
    --input /data/audio \
    --output /data/output \
    --model nvidia/diar_streaming_sortformer_4spk-v2.1
else
  echo "WARNING: Skipping nvidia/diar_streaming_sortformer_4spk-v2.1 run because Docker image 'benchmark-nemo' is missing."
fi

# nvidia/diar_sortformer_4spk-v1
if [ -n "$(docker images -q benchmark-nemo)" ]; then
  docker run --gpus all --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/diar_sortformer_4spk-v1:/data/output" \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    benchmark-nemo \
    --input /data/audio \
    --output /data/output \
    --model nvidia/diar_sortformer_4spk-v1 \
    --max-duration 1900
else
  echo "WARNING: Skipping nvidia/diar_sortformer_4spk-v1 run because Docker image 'benchmark-nemo' is missing."
fi

# pyannote/speaker-diarization-precision-2
if [ -z "$PYANNOTE_API_KEY" ] || [ "$PYANNOTE_API_KEY" = "YOUR_PYANNOTE_API_KEY" ]; then
  echo "WARNING: PYANNOTE_API_KEY is not set. Skipping pyannote/speaker-diarization-precision-2 run."
elif [ -z "$(docker images -q benchmark-pyannote)" ]; then
  echo "WARNING: Skipping pyannote/speaker-diarization-precision-2 run because Docker image 'benchmark-pyannote' is missing."
else
  docker run --rm \
    -v "$DATA_DIR/audio:/data/audio" \
    -v "$RESULT_DIR/pyannote_precision_2:/data/output" \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    -e HF_TOKEN="$PYANNOTE_API_KEY" \
    benchmark-pyannote \
    --input /data/audio \
    --output /data/output \
    --model pyannote/speaker-diarization-precision-2
fi