#!/bin/bash
set -e

DATASET_NAME="CHILDES-CCPCL"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Benchmark sample (20 sessions). Replication requires these exact WAV stems.
EXPECTED_WAV_STEMS=(
    "1-00606"
    "1-011610"
    "1-01308"
    "1-01801"
    "1-02209"
    "1-02604"
    "1-02808"
    "1-03007"
    "1-0605"
    "1-10106"
    "1-13112"
    "3-00112"
    "3-00503"
    "3-0114"
    "3-01606"
    "3-01707"
    "3-01804"
    "3-02709"
    "3-02912"
    "3-12012"
)

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

    expected_sorted="$(printf '%s\n' "${EXPECTED_WAV_STEMS[@]}" | LC_ALL=C sort -u)"
    actual_sorted="$(find "$DEST_DIR/audio" -maxdepth 2 -type f -iname "*.wav" -printf '%f\n' \
        | sed -E 's/\.[Ww][Aa][Vv]$//' \
        | LC_ALL=C sort -u)"

    missing="$(comm -23 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted"))"
    extra="$(comm -13 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted"))"

    if [ -n "$missing" ] || [ -n "$extra" ]; then
        echo "=== WARNING: WAV filename set does not match the benchmark sample ==="
        echo "Replication requires EXACTLY the WAV files with these stems (N=$(printf '%s\n' "$expected_sorted" | wc -l)):"
        printf '%s\n' "$expected_sorted" | sed 's/^/  - /'
        echo
        if [ -n "$missing" ]; then
            echo "Missing WAV stems (present in benchmark list, not found in $DEST_DIR/audio):"
            printf '%s\n' "$missing" | sed 's/^/  - /'
            echo
        fi
        if [ -n "$extra" ]; then
            echo "Extra WAV stems (found in $DEST_DIR/audio, not in benchmark list):"
            printf '%s\n' "$extra" | sed 's/^/  - /'
            echo
        fi

        read -rp "Continue and generate gold RTTM anyway? [y/N]: " answer
        case "$answer" in
            [Yy]*)
                ;;
            *)
                echo "Cancelled. Fix WAV filenames/files to reproduce the benchmark, then rerun."
                exit 0
                ;;
        esac
    else
        echo "=== WAV set matches benchmark sample (N=$(printf '%s\n' "$expected_sorted" | wc -l)) ==="
        read -rp "Generate gold RTTM from CCPCL transcripts now? [y/N]: " answer
        case "$answer" in
            [Yy]*)
                ;;
            *)
                echo "Skipped gold RTTM generation. Rerun when ready."
                exit 0
                ;;
        esac
    fi

    echo "Running ccpcl_data_process.py ..."
    CHA_DIR="$RAW_DIR/CCPCL"
    if [ -d "$RAW_DIR/CCPCL/CCPCL" ]; then
        CHA_DIR="$RAW_DIR/CCPCL/CCPCL"
    fi
    # merge_threshold / min_duration: omitted → argparse defaults from gold_rttm_from_annotations
    read -rp "Enable silence trimming (requires numpy + praat-parselmouth)? [Y/n]: " TRIM_ANS
    TRIM_FLAGS=()
    case "${TRIM_ANS:-Y}" in
        [Nn]*|[Nn]) ;;
        *) TRIM_FLAGS=(--enable_trimming) ;;
    esac
    python3 "$SCRIPT_DIR/ccpcl_data_process.py" "${TRIM_FLAGS[@]}" \
        --cha_dir "$CHA_DIR" \
        --audio_dir "$DEST_DIR/audio" \
        --output_file "$DEST_DIR/ref_rttm/ccpcl_gold_standard.rttm"
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