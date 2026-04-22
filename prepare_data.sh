#!/usr/bin/env bash
# Wrapper for per-dataset prepare_data_<alias>.sh scripts. Run with no args for help.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

discover_dataset_aliases() {
    local f base
    shopt -s nullglob
    for f in "$SCRIPT_DIR"/prepare_data_*.sh; do
        base="$(basename "$f")"
        [[ "$base" == prepare_data.sh ]] && continue
        if [[ "$base" =~ ^prepare_data_(.+)\.sh$ ]]; then
            printf '%s\n' "${BASH_REMATCH[1]}"
        fi
    done | LC_ALL=C sort -u
}

is_known_alias() {
    local want="$1" a
    while IFS= read -r a; do
        [[ "$a" == "$want" ]] && return 0
    done < <(discover_dataset_aliases)
    return 1
}

usage_short() {
    printf 'Usage: %s <dataset|all> [args...]\n' "$(basename "$0")"
    printf '       %s -h|--help\n' "$(basename "$0")"
    echo
    echo "Datasets (from prepare_data_<name>.sh in this directory):"
    local a
    while IFS= read -r a; do
        printf '  %s\n' "$a"
    done < <(discover_dataset_aliases)
    echo "  all    Run every dataset script in sorted order (banner between each; no xtrace)."
    echo
    echo "Run with no arguments for full description and per-dataset notes."
}

usage_long() {
    usage_short
    cat <<'EOF'

Description
  prepare_data.sh dispatches to one of the repository's prepare_data_<dataset>.sh
  scripts, which download or extract corpora, lay out data/<Dataset>/..., and invoke
  the matching *data_process.py where applicable.

  Pass additional arguments after the dataset name; they are forwarded to the
  underlying script. ROG and CCPCL scripts accept an optional first positional argument:
  the gold RTTM filename basename (see per-dataset notes below).

Common behaviour (all per-dataset scripts)
  - Scripts use "set -e" and stop on the first failing command.
  - Interactive prompts: silence trimming (Parselmouth) where the underlying Python
    pipeline supports it; CCPCL also prompts when WAV stems differ from the benchmark list.
  - Gold RTTM merge/min-duration defaults come from gold_rttm_from_annotations.py
    (merge_threshold=1.0 s, min_duration=0.1 s) unless you change the Python invocation.

Optional positional argument (gold RTTM basename)
  output_basename   Passed to prepare_data_rog_*.sh and prepare_data_ccpcl.sh as the
                    first extra argument. If the value does not end in .rttm, .rttm is
                    appended. Defaults: ROG scripts use default_gold_standard; CCPCL uses
                    ccpcl_gold_standard (written under data/<dataset>/ref_rttm/).

Examples
  ./prepare_data.sh rog_dialog
  ./prepare_data.sh rog_art my_experiment_gold
  ./prepare_data.sh ccpcl
  ./prepare_data.sh ccpcl my_ccpcl_gold
  ./prepare_data.sh all

EOF

    echo "Per-dataset scripts (paths relative to repository root):"
    local a path
    while IFS= read -r a; do
        path="prepare_data_${a}.sh"
        case "$a" in
            ccpcl)
                cat <<EOF

  ${path}
    Dataset layout: data/CHILDES-CCPCL/
    Prereq: place TalkBank archive at data/raw/CCPCL.zip (see script output for URL).
    Extracts to data/raw/CCPCL/ (nested CCPCL/ folder is detected automatically).
    WAVs must live under data/CHILDES-CCPCL/audio/ (see script for benchmark stem check).
    Output RTTM: data/CHILDES-CCPCL/ref_rttm/<basename>.rttm (default basename ccpcl_gold_standard).
    Optional first extra arg: gold RTTM basename (same convention as ROG prepare scripts).
EOF
                ;;
            rog_art)
                cat <<EOF

  ${path}
    Dataset layout: data/ROG-Art/
    Downloads ROG.zip and ROG-Art.wav.zip from CLARIN.SI into data/raw when needed.
    Runs rog_art_data_process.py; optional first extra arg: output RTTM basename.
EOF
                ;;
            rog_dialog)
                cat <<EOF

  ${path}
    Dataset layout: data/ROG-Dialog/
    Downloads ROG-Dialog.zip and ROG-Dialog_audio.zip from CLARIN.SI into data/raw.
    Runs rog_dialog_data_process.py; optional first extra arg: output RTTM basename.
EOF
                ;;
            *)
                cat <<EOF

  ${path}
    See script comments and repository docs for details.
EOF
                ;;
        esac
    done < <(discover_dataset_aliases)
    echo
}

if [[ $# -eq 0 ]]; then
    usage_long
    exit 0
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage_long
    exit 0
fi

DATASET="$1"
shift

if [[ "$DATASET" == "all" ]]; then
    mapfile -t _aliases < <(discover_dataset_aliases)
    if [[ ${#_aliases[@]} -eq 0 ]]; then
        echo "ERROR: No prepare_data_<alias>.sh scripts found under ${SCRIPT_DIR}" >&2
        exit 1
    fi
    for a in "${_aliases[@]}"; do
        target="$SCRIPT_DIR/prepare_data_${a}.sh"
        echo "================================================================================"
        echo " prepare_data.sh: running ${target##*/} $*"
        echo "================================================================================"
        bash "$target" "$@"
    done
    exit 0
fi

if ! is_known_alias "$DATASET"; then
    echo "ERROR: Unknown dataset '${DATASET}'." >&2
    echo >&2
    usage_short >&2
    exit 1
fi

exec bash "$SCRIPT_DIR/prepare_data_${DATASET}.sh" "$@"
