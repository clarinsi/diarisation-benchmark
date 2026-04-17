#!/bin/bash
set -e

DATASET_NAME="CHILDES-CCPCL"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1. Checking whether the dataset is already organized: $DATASET_NAME ==="
mkdir -p "$RAW_DIR"
mkdir -p "$DEST_DIR"
mkdir -p "$DEST_DIR/audio"
mkdir -p "$DEST_DIR/annotations/trs"
mkdir -p "$DEST_DIR/docs"

if [ ! -f "$RAW_DIR/CCPCL.zip" ]; then
    cat <<EOF
CCPCL.zip not found.
Download instructions:
https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html

After signing in, download the CCPCL.zip archive and place it at:
  $RAW_DIR/CCPCL.zip

Then rerun:
  ./prepare_data_ccpcl.sh
EOF
    exit 1
fi

echo "=== 2. CCPCL.zip found, extracting ==="

# optional checksum/log:
echo "CCPCL.zip: $(ls -lh "$RAW_DIR/CCPCL.zip")"

# extract to temp path
mkdir -p "$RAW_DIR/CCPCL"
unzip -q -o "$RAW_DIR/CCPCL.zip" -d "$RAW_DIR/CCPCL"

echo "=== 3. Extraction finished: $RAW_DIR/CCPCL ==="

# Original files should be placed in data/CHILDES-CCPCL/audio (if they already exist under the CCPCL structure)
# (If desired, you can add automatic copying here for any layout.)
# For now this is only an instruction reminder.

if [ ! -d "$DEST_DIR/audio" ]; then
    mkdir -p "$DEST_DIR/audio"
fi

wav_count=$(find "$DEST_DIR/audio" -maxdepth 2 -type f -iname "*.wav" | wc -l)

if [ "$wav_count" -gt 0 ]; then
    echo "=== Found $wav_count .wav files in $DEST_DIR/audio ==="
    read -rp "Do you want to prepare the reference dataset from existing WAV files? [y/N]: " answer
    case "$answer" in
        [Yy]*)
            echo "Running ccpcl_data_process.py ..."
            CHA_DIR="$RAW_DIR/CCPCL"
            if [ -d "$RAW_DIR/CCPCL/CCPCL" ]; then
                CHA_DIR="$RAW_DIR/CCPCL/CCPCL"
            fi
            python3 "$SCRIPT_DIR/ccpcl_data_process.py" --cha_dir "$CHA_DIR" --output_file "$DEST_DIR/ref_rttm/ccpcl_gold_standard.rttm" --merge_threshold 1.0 --min_duration 0.1
            ;;
        *)
            echo "Edit WAV files in $DEST_DIR/audio and rerun this script when ready."
            ;;
    esac
else
    cat <<EOF
=== No WAV files found in $DEST_DIR/audio ===
To continue, download audio files from:
https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav
and place them in:
  $DEST_DIR/audio
Then rerun:
  ./prepare_data_ccpcl.sh
EOF
fi

echo "=== Script finished: CHILDES-CCPCL step completed ==="