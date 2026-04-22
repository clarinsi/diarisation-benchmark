#!/usr/bin/env bash
# Run Python with repo-root uv groups `trim` (and optionally `trim-exb`).
# Requires uv on PATH unless DIABENCH_INSTALL_UV=1 (runs Astral install script).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    if [[ "${DIABENCH_INSTALL_UV:-0}" == "1" ]]; then
        echo "diarisation-benchmark: uv not found; installing via https://astral.sh/uv/install.sh (DIABENCH_INSTALL_UV=1)" >&2
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="${HOME}/.local/bin:${PATH}"
    fi
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    cat >&2 <<'EOF'
error: uv is not installed (or not on PATH).

Install uv (pick one):
  curl -LsSf https://astral.sh/uv/install.sh | sh
  pipx install uv

Then ensure ~/.local/bin is on your PATH (or open a new shell).

Docs: docs/data_preparation.md#installing-uv

To auto-run the Astral installer from this script:
  DIABENCH_INSTALL_UV=1 scripts/with_trim_env.sh your_script.py ...
EOF
    exit 1
}

ensure_uv
cd "$REPO_ROOT"

# Optional: uv reuses extracted sdist trees under ~/.cache/uv/sdists-v9/pypi/.
# If a prior failed build left CMakeCache from "Unix Makefiles" and a later
# run uses "-G Ninja", CMake errors with "Does not match the generator used
# previously". Clearing this cache forces a clean configure (see docs).
PRAAT_UV_CACHE="${HOME}/.cache/uv/sdists-v9/pypi/praat-parselmouth"
if [[ "${DIABENCH_CLEAR_PRAAT_UV_CACHE:-0}" == "1" ]] && [[ -d "$PRAAT_UV_CACHE" ]]; then
    echo "diarisation-benchmark: removing cached praat-parselmouth sdist (DIABENCH_CLEAR_PRAAT_UV_CACHE=1)" >&2
    rm -rf "$PRAAT_UV_CACHE"
fi

UV_GROUPS=(--group trim)
if [[ "${DIABENCH_TRIM_EXB:-0}" == "1" ]]; then
    UV_GROUPS+=(--group trim-exb)
fi

uv sync "${UV_GROUPS[@]}"
exec uv run "${UV_GROUPS[@]}" python "$@"
