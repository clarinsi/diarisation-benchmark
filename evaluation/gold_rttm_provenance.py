"""
Read provenance comment lines from gold RTTM files.

Gold RTTMs written by ``gold_rttm_from_annotations`` start with:

1. ``; gold_rttm pipeline=...`` from ``format_gold_rttm_header`` (merge/min_duration,
   source trs/cha, output name, directories).

2. When edge trimming is applied, ``; trim_params ...`` from ``format_trim_provenance_line``
   (second line, before ``SPEAKER`` rows).

Standalone trimming (``trim_gold_silences_rttm``) preserves existing header lines when writing.
"""
from __future__ import annotations

import os
from typing import Any


_GOLD_RTTM_KEY_HELP: dict[str, str] = {
    "gold_rttm": "Record type tag",
    "pipeline": "Benchmark pipeline / dataset name",
    "source": "Annotation source (e.g. trs, cha)",
    "merge_threshold": "Adjacent same-speaker merge threshold (s)",
    "min_duration": "Minimum kept segment duration (s)",
    "prioritize_pog": "ROG TRS variant preference (pog/std)",
    "output": "Gold RTTM filename written",
    "trs_dir": "TRS directory used",
    "cha_dir": "CHA directory used",
    "audio_dir": "Audio directory used for trimming / filtering",
}

_TRIM_PARAMS_KEY_HELP: dict[str, str] = {
    "pitch_floor": "Lower bound (Hz) for Praat pitch tracking when locating voiced speech at segment edges",
    "pitch_ceiling": "Upper bound (Hz) for Praat pitch tracking",
    "intensity_drop_db": "dB below local max intensity treated as non-speech for edge refinement",
    "guard_ms": "Minimum margin (ms) kept at trimmed boundaries after VAD",
    "max_trim_s": "Maximum seconds an edge may move inward (caps aggressive trims)",
    "min_duration": "Segments shorter than this (s) after trimming are dropped",
    "pad_s": "Padding (s) added back after trimming to avoid cutting into speech",
    "time_step": "Analysis frame step (s) for pitch/intensity sampling",
    "method": "VAD mode: pitch_or_intensity | pitch_only | intensity_only",
    "trim_silence_within": "If true, split segments at internal silences (not only edge trim)",
    "min_silence_dur": "Minimum internal silence duration (s) required to split a segment",
    "verbose": "If true, trimmer emits detailed per-file diagnostics to the console",
}


def read_leading_rttm_comments(path: str, max_lines: int = 2) -> list[str]:
    """
    Return up to ``max_lines`` consecutive comment lines from the start of the file.

    Stops at the first non-blank line that does not start with ``;`` or ``#``.
    """
    out: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith(";") or stripped.startswith("#"):
                out.append(stripped)
                if len(out) >= max_lines:
                    break
                continue
            break
    return out


def parse_semicolon_kv_line(line: str) -> list[tuple[str, str]]:
    """Parse `; gold_rttm k=v ...` or `; trim_params k=v ...` into key/value pairs."""
    s = line.strip()
    if s.startswith(";"):
        s = s[1:].strip()
    if not s:
        return []
    parts = s.split()
    if not parts:
        return []
    head, rest = parts[0], parts[1:]
    if head == "gold_rttm":
        tokens = rest
    elif head.startswith("trim_params"):
        tokens = rest
    else:
        tokens = parts
    rows: list[tuple[str, str]] = []
    for p in tokens:
        if "=" not in p:
            continue
        k, _, v = p.partition("=")
        rows.append((k.strip(), v.strip()))
    return rows


def _format_kv_markdown_table(rows: list[tuple[str, str]], key_help: dict[str, str]) -> str:
    if not rows:
        return ""
    lines = [
        "| Key | Value | Description |",
        "|---|---|---|",
    ]
    for k, v in rows:
        desc = key_help.get(k, "")
        lines.append(f"| `{k}` | `{v}` | {desc} |")
    lines.append("")
    return "\n".join(lines)


def format_gold_rttm_report_section(gold_path: str, errata_meta: dict[str, Any] | None = None) -> str:
    """Markdown block for report preamble (section 0)."""
    resolved = os.path.abspath(os.path.normpath(gold_path))
    basename = os.path.basename(gold_path)
    comments = read_leading_rttm_comments(gold_path, max_lines=2)

    lines: list[str] = [
        "## 0. Gold RTTM",
        "",
        f"- **File:** `{basename}`",
        f"- **Path (resolved):** `{resolved}`",
        "",
        "The benchmark gold reference is the RTTM above. When generated in this repository, "
        "the first header line is produced by `gold_rttm_from_annotations.format_gold_rttm_header` "
        "(fields such as `pipeline`, `source`, `merge_threshold`, `min_duration`, `output`, "
        "and annotation/audio directories). If silence **edge** trimming was applied when "
        "building the file, a second line records trim parameters via "
        "`format_trim_provenance_line` (`; trim_params …`).",
        "",
    ]

    if not comments:
        lines.append(
            "*No leading `;` / `#` comment lines were found at the top of this RTTM "
            "(file may predate provenance headers or come from an external source).*"
        )
        lines.append("")
        if errata_meta:
            from errata_merge import format_errata_report_md

            lines.append(format_errata_report_md(errata_meta))
        return "\n".join(lines)

    lines.append("**Embedded header lines (verbatim from the gold RTTM):**")
    lines.append("")
    for i, c in enumerate(comments, start=1):
        if "trim_params" in c:
            label = "Silence-edge trim parameters (`format_trim_provenance_line`)"
        elif "gold_rttm" in c:
            label = "Gold generation provenance (`format_gold_rttm_header`)"
        else:
            label = "Leading comment"
        lines.append(f"{i}. {label}")
        lines.append("")
        lines.append("```text")
        lines.append(c)
        lines.append("```")
        lines.append("")

    if comments and "gold_rttm" in comments[0]:
        kv = parse_semicolon_kv_line(comments[0])
        if kv:
            lines.append("**Decoded gold generation metadata (from first header line):**")
            lines.append("")
            lines.append(_format_kv_markdown_table(kv, _GOLD_RTTM_KEY_HELP))

    if len(comments) > 1 and "trim_params" in comments[1]:
        tkv = parse_semicolon_kv_line(comments[1])
        if tkv:
            lines.append("**Decoded trim parameters (from second header line):**")
            lines.append("")
            lines.append(_format_kv_markdown_table(tkv, _TRIM_PARAMS_KEY_HELP))

    if errata_meta:
        from errata_merge import format_errata_report_md

        lines.append(format_errata_report_md(errata_meta))

    return "\n".join(lines)
