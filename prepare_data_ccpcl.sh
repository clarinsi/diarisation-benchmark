#!/bin/bash
# Turn off xtrace so wrappers (e.g. an old "bash -x" habit) do not leak debug noise to users.
set +x
set -e

DATASET_NAME="CHILDES-CCPCL"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# May be multiple words, e.g. "uv run --group trim python" — do not quote when invoking.
: "${DIABENCH_PYTHON:=python3}"

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
  ./prepare_data_ccpcl.sh [optional_gold_basename]
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

# Session metadata (TalkBank release) for universal reports: copy next to dataset docs.
for DEMO_CAND in "$RAW_DIR/CCPCL/CCPCL/0demo.xlsx" "$RAW_DIR/CCPCL/0demo.xlsx"; do
    if [ -f "$DEMO_CAND" ]; then
        cp -f "$DEMO_CAND" "$DEST_DIR/docs/0demo.xlsx"
        echo "Copied 0demo.xlsx to $DEST_DIR/docs/ (reporting metadata)."
        break
    fi
done

# Original files should be placed in data/CHILDES-CCPCL/audio (if they already exist under the CCPCL structure)
# (If desired, you can add automatic copying here for any layout.)
# For now this is only an instruction reminder.

if [ ! -d "$DEST_DIR/audio" ]; then
    mkdir -p "$DEST_DIR/audio"
fi

wav_count=$(find "$DEST_DIR/audio" -maxdepth 2 -type f -iname "*.wav" | wc -l)

OUTPUT_FILENAME="${1:-ccpcl_gold_standard}"
if [[ "$OUTPUT_FILENAME" != *.rttm ]]; then
    OUTPUT_FILENAME="$OUTPUT_FILENAME.rttm"
fi
mkdir -p "$DEST_DIR/ref_rttm"
OUTPUT_PATH="$DEST_DIR/ref_rttm/$OUTPUT_FILENAME"

if [ "$wav_count" -gt 0 ]; then
    echo "=== Found $wav_count .wav files in $DEST_DIR/audio ==="

    # Normalized sorted stem lists (strip CRLF, drop blank lines) for reliable comm/compare.
    expected_sorted="$(printf '%s\n' "${EXPECTED_WAV_STEMS[@]}" | LC_ALL=C sort -u | tr -d '\r' | sed '/^$/d')"
    actual_sorted="$(find "$DEST_DIR/audio" -maxdepth 2 -type f -iname "*.wav" -printf '%f\n' \
        | sed -E 's/\.[Ww][Aa][Vv]$//' \
        | LC_ALL=C sort -u | tr -d '\r' | sed '/^$/d')"

    expected_n="$(printf '%s\n' "$expected_sorted" | sed '/^$/d' | wc -l | tr -d ' ')"
    actual_n="$(printf '%s\n' "$actual_sorted" | sed '/^$/d' | wc -l | tr -d ' ')"

    echo "Benchmark WAV stems (required, N=${expected_n}):"
    if [ -z "$expected_sorted" ]; then
        echo "  (none)"
    else
        printf '%s\n' "$expected_sorted" | sed 's/^/  - /'
    fi
    echo
    echo "WAV stems found under $DEST_DIR/audio (N=${actual_n}):"
    if [ -z "$actual_sorted" ]; then
        echo "  (none)"
    else
        printf '%s\n' "$actual_sorted" | sed 's/^/  - /'
    fi
    echo

    missing="$(comm -23 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted") | sed '/^$/d')"
    extra="$(comm -13 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted") | sed '/^$/d')"

    if [ -n "$missing" ] || [ -n "$extra" ]; then
        echo "=== WARNING: WAV filename set does not match the benchmark sample ==="
        echo "Replication uses exactly the benchmark stems above. Differences:"
        echo
        echo "Missing (in benchmark, not on disk as <stem>.wav):"
        if [ -z "$missing" ]; then
            echo "  (none)"
        else
            printf '%s\n' "$missing" | sed '/^$/d' | sed 's/^/  - /'
        fi
        echo
        echo "Extra (on disk, not in benchmark list):"
        if [ -z "$extra" ]; then
            echo "  (none)"
        else
            printf '%s\n' "$extra" | sed '/^$/d' | sed 's/^/  - /'
        fi
        echo

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
        echo "=== WAV set matches benchmark sample (N=${expected_n}) ==="
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

    echo "Running ccpcl_data_process.py (output: $OUTPUT_PATH) ..."
    CHA_DIR="$RAW_DIR/CCPCL"
    if [ -d "$RAW_DIR/CCPCL/CCPCL" ]; then
        CHA_DIR="$RAW_DIR/CCPCL/CCPCL"
    fi
    # merge_threshold / min_duration: omitted → argparse defaults from gold_rttm_from_annotations
    read -rp "Enable silence trimming (requires numpy + praat-parselmouth; uv: docs/data_preparation.md)? [Y/n]: " TRIM_ANS
    TRIM_FLAGS=()
    case "${TRIM_ANS:-Y}" in
        [Nn]*|[Nn]) ;;
        *) TRIM_FLAGS=(--enable_trimming) ;;
    esac
    # shellcheck disable=SC2086
    $DIABENCH_PYTHON "$SCRIPT_DIR/ccpcl_data_process.py" "${TRIM_FLAGS[@]}" \
        --cha_dir "$CHA_DIR" \
        --audio_dir "$DEST_DIR/audio" \
        --output_file "$OUTPUT_PATH"
else
    cat <<EOF
=== No WAV files found in $DEST_DIR/audio ===
To continue, download audio files from:
https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav
and place them in:
  $DEST_DIR/audio
Then rerun:
  ./prepare_data_ccpcl.sh [optional_gold_basename]
EOF
fi

echo "=== Script finished: CHILDES-CCPCL step completed ==="