#!/usr/bin/env bash
# Build the evaluation Docker image and run generate_report_universal.py; if Docker is
# missing or fails, fall back to: (cd evaluation && uv run python …). See docs/evaluation.md
#
# Usage: from repository root:
#   ./scripts/run_evaluation_report.sh --help
#   ./scripts/run_evaluation_report.sh -y
#   ./scripts/run_evaluation_report.sh --dataset rog_art -y
#
set -euo pipefail

BENCHMARK_EVAL_IMAGE="${BENCHMARK_EVAL_IMAGE:-benchmark-eval}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Options (set early so we can re-parse dataset)
DATASET="rog_dialog"
GOLD=""
OUTPUT=""
METADATA=""
RESULTS_DIR=""
ERRATA_USER=""
SKIP_CONFIRM=0
USE_DOCKER=""
NO_AUTO_ERRATA=0
BOUNDARY_TOLERANCE="0.250"
ANALYSIS_COLLAR="0.25"
REMAINDER=()

die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }
info() { echo "==> $*" >&2; }

usage() {
  cat <<'EOF'
Usage: ./scripts/run_evaluation_report.sh [options] [-- extra args for generate_report_universal.py…]

  Preferred: Docker image from evaluation/Dockerfile (tag: benchmark-eval, or BENCHMARK_EVAL_IMAGE).
  If Docker is unavailable or build/run fails, uses: (cd evaluation && uv run python …)

  Run from the repository root (contains data/, results/, evaluation/).

Options:
  --dataset rog_dialog|rog_art|childes_ccpcl   (default: rog_dialog; aliases: ccpcl → childes_ccpcl)
  --gold PATH
  --output PATH
  --metadata PATH
  --results-dir PATH
  --image NAME              Docker image tag (default: benchmark-eval)
  --boundary-tolerance F    (default: 0.250)
  --analysis-collar F        (default: 0.25)
  --errata PATH              Manual UEM JSON (overrides ROG-Dialog default; for other datasets, default is to skip)
  --no-auto-errata
  -y, --yes                  No confirmation prompt; non-interactive default is continue without ask
  --use-docker                Use Docker only (no uv fallback)
  --use-uv                    Use uv only (no Docker)
  -h, --help
  --                          Pass remaining args to generate_report_universal.py

Default trimmed gold, metadata, and output (under reports/) match docs/evaluation.md.
ROG-Dialog uses evaluation/DATASET_ERRATA.json; ROG-Art and CCPCL do not use that file by default
(empty manual errata, auto errata can still load beside gold).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --dataset)
      DATASET="$2"
      shift 2
      ;;
    --gold) GOLD="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --metadata) METADATA="$2"; shift 2 ;;
    --results-dir) RESULTS_DIR="$2"; shift 2 ;;
    --errata) ERRATA_USER="$2"; shift 2 ;;
    --image) BENCHMARK_EVAL_IMAGE="$2"; shift 2 ;;
    --boundary-tolerance) BOUNDARY_TOLERANCE="$2"; shift 2 ;;
    --analysis-collar) ANALYSIS_COLLAR="$2"; shift 2 ;;
    --no-auto-errata) NO_AUTO_ERRATA=1; shift ;;
    -y|--yes) SKIP_CONFIRM=1; shift ;;
    --use-docker) USE_DOCKER=1; shift ;;
    --use-uv) USE_DOCKER=0; shift ;;
    --) shift; REMAINDER=("$@"); break ;;
    *) die "Unknown option: $1 (use --help)" ;;
  esac
done

# normalize dataset
DS="$(echo "$DATASET" | tr '[:upper:]' '[:lower:]' | tr '-' '_')"
case "$DS" in
  ccpcl) DS=childes_ccpcl ;;
  rog_dialog|rog_art|childes_ccpcl) ;;
  *) die "Invalid --dataset: $DATASET" ;;
esac
DATASET="$DS"

# defaults (host paths) — trimmed gold / universal report folders
case "$DATASET" in
  rog_dialog)
    GOLD=${GOLD:-"$REPO_ROOT/data/ROG-Dialog/ref_rttm/gold_standard_trimmed_15.rttm"}
    METADATA=${METADATA:-"$REPO_ROOT/data/ROG-Dialog/docs/ROG-Dia-meta-speeches.tsv"}
    RESULTS_DIR=${RESULTS_DIR:-"$REPO_ROOT/results/ROG-Dialog"}
    OUTPUT=${OUTPUT:-"$REPO_ROOT/reports/ROG_Dialog_Universal_Report"}
    ;;
  rog_art)
    GOLD=${GOLD:-"$REPO_ROOT/data/ROG-Art/ref_rttm/default_gold_standard_trimmed.rttm"}
    METADATA=${METADATA:-"$REPO_ROOT/data/ROG-Art/docs/ROG-speeches.tsv"}
    RESULTS_DIR=${RESULTS_DIR:-"$REPO_ROOT/results/ROG-Art"}
    OUTPUT=${OUTPUT:-"$REPO_ROOT/reports/ROG_Art_Universal_Report"}
    ;;
  childes_ccpcl)
    GOLD=${GOLD:-"$REPO_ROOT/data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard_trimmed.rttm"}
    METADATA=${METADATA:-"$REPO_ROOT/data/CHILDES-CCPCL/docs/0demo.xlsx"}
    RESULTS_DIR=${RESULTS_DIR:-"$REPO_ROOT/results/CHILDES-CCPCL"}
    OUTPUT=${OUTPUT:-"$REPO_ROOT/reports/CCPCL_Universal_Report"}
    ;;
esac

# errata: ROG-Dialog only unless overridden
if [[ -n "$ERRATA_USER" ]]; then
  ERRATA_EFFECTIVE="$ERRATA_USER"
  ERRATA_DOCKER_MODE=user
else
  case "$DATASET" in
    rog_dialog)
      ERRATA_EFFECTIVE="$REPO_ROOT/evaluation/DATASET_ERRATA.json"
      ERRATA_DOCKER_MODE=bind
      ;;
    *)
      ERRATA_EFFECTIVE=""
      ERRATA_DOCKER_MODE=empty_json
      ;;
  esac
fi

[[ -f "$GOLD" ]] || die "Gold RTTM not found: $GOLD"
[[ -d "$RESULTS_DIR" ]] || die "Results directory not found: $RESULTS_DIR"
if [[ -n "$METADATA" && ! -f "$METADATA" ]]; then
  die "Metadata file not found: $METADATA"
fi
if [[ "$ERRATA_DOCKER_MODE" == "bind" ]] && [[ ! -f "$ERRATA_EFFECTIVE" ]]; then
  die "Manual errata file not found: $ERRATA_EFFECTIVE"
fi
if [[ -n "$ERRATA_USER" ]] && [[ ! -f "$ERRATA_USER" ]]; then
  die "--errata file not found: $ERRATA_USER"
fi

if [[ "$SKIP_CONFIRM" != 1 ]] && [[ -t 0 ]] && [[ -t 1 ]]; then
  echo "--- Report generation ---" >&2
  echo "  dataset:   $DATASET" >&2
  echo "  gold:      $GOLD" >&2
  echo "  results:   $RESULTS_DIR" >&2
  echo "  metadata:  ${METADATA:-<none>}" >&2
  echo "  output:    $OUTPUT" >&2
  if [[ "$ERRATA_DOCKER_MODE" == "bind" ]]; then
    echo "  errata:    $ERRATA_EFFECTIVE" >&2
  elif [[ "$ERRATA_DOCKER_MODE" == "user" ]]; then
    echo "  errata:    $ERRATA_EFFECTIVE" >&2
  else
    echo "  errata:    (none; auto from gold dir if present)" >&2
  fi
  read -r -p "Proceed? [Y/n] " _a || true
  if [[ -n "${_a:-}" && "${_a:0:1}" =~ [nN] ]]; then die "Aborted."; fi
fi

mkdir -p "$OUTPUT"

# Resolved --errata: repo manual file, or a temp `{}` so manual dict is empty (ROG-Art / CCPCL default)
if [[ "$ERRATA_DOCKER_MODE" == "bind" ]] || [[ "$ERRATA_DOCKER_MODE" == "user" ]]; then
  ERRATA_FOR_PY="$ERRATA_EFFECTIVE"
else
  ERRATA_FOR_PY="$(mktemp -t "diabench_empty_errata.XXXXXX.json")"
  echo '{}' > "$ERRATA_FOR_PY"
  # shellcheck disable=SC2064
  trap 'rm -f "$ERRATA_FOR_PY"' EXIT
fi

build_docker_image() {
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi
  if ! docker info >/dev/null 2>&1; then
    return 1
  fi
  info "docker build -t $BENCHMARK_EVAL_IMAGE -f evaluation/Dockerfile evaluation/"
  docker build -t "$BENCHMARK_EVAL_IMAGE" -f "$REPO_ROOT/evaluation/Dockerfile" "$REPO_ROOT/evaluation"
}

run_docker() {
  # Mount the directory that contains the gold RTTM (not only the file) so
  # AUTO_DATASET_ERRATA.json beside the gold on the host is visible inside the
  # container (load_merged_errata uses dirname(gold) / AUTO_DATASET_ERRATA.json).
  local gold_dir gold_base
  gold_dir="$(cd "$(dirname "$GOLD")" && pwd)"
  gold_base="$(basename "$GOLD")"

  local -a run=(
    docker run --rm --entrypoint python
    -e "HOST_UID=$(id -u)"
    -e "HOST_GID=$(id -g)"
    -v "$gold_dir:/g/gold_dir:ro"
    -v "$RESULTS_DIR:/g/results:ro"
    -v "$OUTPUT:/g/out"
    -v "$ERRATA_FOR_PY:/g/errata.json:ro"
  )
  if [[ -n "$METADATA" ]]; then
    run+=(-v "$METADATA:/g/meta:ro")
  fi
  run+=("$BENCHMARK_EVAL_IMAGE"
    generate_report_universal.py
    --dataset "$DATASET"
    --gold "/g/gold_dir/${gold_base}"
    --results_dir /g/results
    --output /g/out
    --boundary_tolerance "$BOUNDARY_TOLERANCE"
    --analysis_collar "$ANALYSIS_COLLAR"
  )
  if [[ -n "$METADATA" ]]; then
    run+=(--metadata /g/meta)
  fi
  run+=(--errata /g/errata.json)
  if [[ "$NO_AUTO_ERRATA" -eq 1 ]]; then
    run+=(--no_auto_errata)
  fi
  run+=("${REMAINDER[@]}")
  info "Running (Docker)…"
  "${run[@]}"
}

run_uv() {
  command -v uv >/dev/null 2>&1 || return 1
  info "Running (uv)…"
  (
    cd "$REPO_ROOT/evaluation" || exit 1
    u=(
      uv run python generate_report_universal.py
      --dataset "$DATASET"
      --gold "$GOLD"
      --results_dir "$RESULTS_DIR"
      --output "$OUTPUT"
      --boundary_tolerance "$BOUNDARY_TOLERANCE"
      --analysis_collar "$ANALYSIS_COLLAR"
    )
    if [[ -n "$METADATA" ]]; then
      u+=(--metadata "$METADATA")
    fi
    u+=(--errata "$ERRATA_FOR_PY")
    if [[ "$NO_AUTO_ERRATA" -eq 1 ]]; then
      u+=(--no_auto_errata)
    fi
    u+=("${REMAINDER[@]}")
    "${u[@]}"
  )
}

FAIL_HINT() {
  cat <<'EOM' >&2
Could not run the report. Install one of:

  Docker: https://docs.docker.com/get-docker/
    then:  docker build -f evaluation/Dockerfile -t benchmark-eval evaluation

  uv:     https://docs.astral.sh/uv/getting-started/installation/
    then:  cd evaluation && uv sync
EOM
}

if [[ "$USE_DOCKER" == "0" ]]; then
  run_uv || { die "uv run failed."; FAIL_HINT; exit 1; }
  exit 0
fi

if [[ "$USE_DOCKER" == "1" ]]; then
  command -v docker >/dev/null 2>&1 || { die "Docker not found (--use-docker)."; FAIL_HINT; exit 1; }
  build_docker_image || exit 1
  run_docker
  exit 0
fi

# Auto: try Docker, then uv
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if build_docker_image; then
    if run_docker; then
      exit 0
    fi
    warn "Docker run failed; trying uv…"
  else
    warn "Docker build failed; trying uv…"
  fi
else
  warn "Docker not available; trying uv…"
fi

if run_uv; then
  exit 0
fi

die "Report generation failed with both Docker and uv."
FAIL_HINT
exit 1
