#!/bin/bash
set +x
# Prekini izvajanje ob napaki
set -e

# Ime dataseta - enostavno spremenljivo za prihodnje datasete
DATASET_NAME="ROG-Dialog"
BASE_DIR="data/$DATASET_NAME"

echo "=== 1. Checking whether the dataset is already organized: $DATASET_NAME ==="
mkdir -p "$BASE_DIR/audio"
mkdir -p "$BASE_DIR/annotations/trs"
mkdir -p "$BASE_DIR/annotations/exb"
mkdir -p "$BASE_DIR/annotations/exs"
mkdir -p "$BASE_DIR/docs"
mkdir -p "$BASE_DIR/ref_rttm"  # Preimenovano v rttm
mkdir -p data/raw

SKIP_REORG=false
if [ -d "$BASE_DIR/audio" ] && [ -d "$BASE_DIR/annotations/trs" ] && [ -d "$BASE_DIR/annotations/exb" ] && [ -d "$BASE_DIR/annotations/exs" ] && [ -d "$BASE_DIR/docs" ]; then
    if [ "$(ls -A "$BASE_DIR/audio" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/trs" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/exb" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/exs" 2>/dev/null)" ]; then
        echo "Dataset already organized; skipping download, extraction, and reorganization."
        SKIP_REORG=true
    fi
fi

if [ "$SKIP_REORG" = true ]; then
    echo "=== Skipping download and reorganization ==="
else
    # Premik v mapo za prenose
    cd data/raw

    echo "=== 2. Downloading files ==="
if [ ! -f "ROG-Dialog.zip" ] || [ ! -f "ROG-Dialog_audio.zip" ]; then
    echo "Downloading from CLARIN.SI..."
    curl --remote-name-all https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2073{/ROG-Dialog.zip,/ROG-Dialog_audio.zip}
else
    echo "Files already present."
fi

echo "=== 3. Extracting archives ==="
unzip -q -o ROG-Dialog_audio.zip
unzip -q -o ROG-Dialog.zip

echo "=== 4. Reorganizing into '$BASE_DIR' ==="
cd ../..
fi

# Audio
if [ -d "data/raw/ROG-Dialog/DATA/WAV" ]; then
    mv data/raw/ROG-Dialog/DATA/WAV/*.wav "$BASE_DIR/audio/"
fi

# Annotations (TRS, EXB, EXS)
if [ -d "data/raw/ROG-Dialog/DATA/TRS" ]; then
    mv data/raw/ROG-Dialog/DATA/TRS/*.trs "$BASE_DIR/annotations/trs/"
fi
if [ -d "data/raw/ROG-Dialog/DATA/EXB" ]; then
    mv data/raw/ROG-Dialog/DATA/EXB/*.exb "$BASE_DIR/annotations/exb/"
fi
if [ -d "data/raw/ROG-Dialog/DATA/EXS" ]; then
    mv data/raw/ROG-Dialog/DATA/EXS/*.exs "$BASE_DIR/annotations/exs/"
fi

# Docs
if [ -d "data/raw/ROG-Dialog/DOCS" ]; then
    mv data/raw/ROG-Dialog/DOCS/* "$BASE_DIR/docs/"
fi

echo "=== 5. Cleaning up ==="
rm -rf data/raw/ROG-Dialog

OUTPUT_FILENAME="${1:-default_gold_standard}"
if [[ "$OUTPUT_FILENAME" != *.rttm ]]; then
    OUTPUT_FILENAME="$OUTPUT_FILENAME.rttm"
fi

echo "=== 6. Generating gold RTTM ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# May be multiple words, e.g. "uv run --group trim python" — do not quote when invoking.
: "${DIABENCH_PYTHON:=python3}"
case "${DIABENCH_PREPARE_NONINTERACTIVE:-0}" in
    1|true|TRUE|yes|YES) NONINTERACTIVE=1 ;;
    *) NONINTERACTIVE=0 ;;
esac
# merge_threshold / min_duration / prioritize_pog: omitted → defaults in gold_rttm_from_annotations
TRIM_FLAGS=()
if [ "$NONINTERACTIVE" -eq 1 ]; then
    TRIM_FLAGS=(--enable_trimming)
else
    read -rp "Enable silence trimming (requires numpy + praat-parselmouth; uv: docs/data_preparation.md)? [Y/n]: " TRIM_ANS
    case "${TRIM_ANS:-Y}" in
        [Nn]*|[Nn]) ;;
        *) TRIM_FLAGS=(--enable_trimming) ;;
    esac
fi
# shellcheck disable=SC2086
$DIABENCH_PYTHON "$SCRIPT_DIR/rog_dialog_data_process.py" "${TRIM_FLAGS[@]}" --output_filename "$OUTPUT_FILENAME"

echo "=== Script finished: $DATASET_NAME preparation completed ==="
echo "Dataset $DATASET_NAME is ready."