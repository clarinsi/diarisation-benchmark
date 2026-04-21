#!/bin/bash

# Prekini izvajanje ob napaki
set -e

DATASET_NAME="ROG-Art"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1. Checking whether the dataset is already organized: $DATASET_NAME ==="
mkdir -p "$RAW_DIR"
mkdir -p "$DEST_DIR"
mkdir -p "$DEST_DIR/audio"
mkdir -p "$DEST_DIR/annotations/trs"
mkdir -p "$DEST_DIR/annotations/exb"
mkdir -p "$DEST_DIR/annotations/exs"
mkdir -p "$DEST_DIR/docs"

SKIP_REORG=false
if [ -d "$DEST_DIR/audio" ] && [ -d "$DEST_DIR/annotations/trs" ] && [ -d "$DEST_DIR/annotations/exb" ] && [ -d "$DEST_DIR/annotations/exs" ] && [ -d "$DEST_DIR/docs" ]; then
    if [ "$(ls -A "$DEST_DIR/audio" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/trs" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/exb" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/exs" 2>/dev/null)" ]; then
        echo "Dataset already organized; skipping download, extraction, and reorganization."
        SKIP_REORG=true
    fi
fi

if [ "$SKIP_REORG" = true ]; then
    echo "=== Skipping download and reorganization ==="
else
    # Prenos v data/raw
    cd "$SCRIPT_DIR/$RAW_DIR"

    echo "=== 2. Downloading files ==="
    if [ ! -f "ROG.zip" ] || [ ! -f "ROG-Art.wav.zip" ]; then
        echo "Downloading from CLARIN.SI..."
        curl --remote-name-all https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2062{/ROG.zip,/ROG-Art.wav.zip}
    else
        echo "Files already present."
    fi

    echo "=== 3. Extracting archives into $DEST_DIR ==="
    mkdir -p "$DEST_DIR"
    unzip -q -o "ROG.zip" -d "$DEST_DIR"
    unzip -q -o "ROG-Art.wav.zip" -d "$DEST_DIR"
fi

OUTPUT_FILENAME="${1:-default_gold_standard}"
if [[ "$OUTPUT_FILENAME" != *.rttm ]]; then
    OUTPUT_FILENAME="$OUTPUT_FILENAME.rttm"
fi

echo "=== 4. Generating gold RTTM ==="
# merge_threshold / min_duration / prioritize_pog: omitted → defaults in gold_rttm_from_annotations
read -rp "Enable silence trimming (requires numpy + praat-parselmouth)? [Y/n]: " TRIM_ANS
TRIM_FLAGS=()
case "${TRIM_ANS:-Y}" in
    [Nn]*|[Nn]) ;;
    *) TRIM_FLAGS=(--enable_trimming) ;;
esac
python3 "$SCRIPT_DIR/rog_art_data_process.py" "${TRIM_FLAGS[@]}" --output_filename "$OUTPUT_FILENAME"

# Odstranimo samo razširjene vmesne mape (struktura iz razpakiranega .zip), zip datoteke ohranimo za ponovno uporabo.
echo "=== 5. Cleaning up ==="
rm -rf "$RAW_DIR/data"

echo "=== 6. Script finished: $DATASET_NAME preparation completed ==="
echo "Dataset $DATASET_NAME is ready at $DEST_DIR."

