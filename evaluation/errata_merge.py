"""
Load and merge manual dataset errata with auto-generated errata from gold preparation.

Auto file: ``AUTO_DATASET_ERRATA.json`` in the same directory as the gold RTTM
(see ``gold_rttm_from_annotations.write_auto_dataset_errata_json``).

Merge rules (per ``file_id``):
- ``trim_start``: if both manual and auto define it, use **max** (larger ignored prefix).
  If only one defines it, use that value.
- ``trim_end``: if both define it, use **min** (stricter / earlier end). If only one, use it.
- ``reason``: short joined note listing which sources contributed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


AUTO_ERRATA_BASENAME = "AUTO_DATASET_ERRATA.json"


def _load_json_dict(path: str | os.PathLike[str]) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def _float_or_none(d: dict[str, Any], key: str) -> float | None:
    if key not in d or d[key] is None:
        return None
    try:
        return float(d[key])
    except (TypeError, ValueError):
        return None


def merge_errata_for_evaluation(
    manual: dict[str, Any],
    auto: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return file_id -> {trim_start?, trim_end?, reason} for metrics/plots."""
    out: dict[str, dict[str, Any]] = {}
    all_ids = set(manual) | set(auto)
    for fid in sorted(all_ids):
        m = manual.get(fid, {}) if isinstance(manual.get(fid), dict) else {}
        a = auto.get(fid, {}) if isinstance(auto.get(fid), dict) else {}
        m_ts, a_ts = _float_or_none(m, "trim_start"), _float_or_none(a, "trim_start")
        m_te, a_te = _float_or_none(m, "trim_end"), _float_or_none(a, "trim_end")

        rec: dict[str, Any] = {}
        if m_ts is not None and a_ts is not None:
            rec["trim_start"] = max(m_ts, a_ts)
        elif m_ts is not None:
            rec["trim_start"] = m_ts
        elif a_ts is not None:
            rec["trim_start"] = a_ts

        if m_te is not None and a_te is not None:
            rec["trim_end"] = min(m_te, a_te)
        elif m_te is not None:
            rec["trim_end"] = m_te
        elif a_te is not None:
            rec["trim_end"] = a_te

        if "trim_start" not in rec and "trim_end" not in rec:
            continue

        mr = str(m.get("reason", "")).strip()
        ar = str(a.get("reason", "")).strip()
        bits = []
        if mr:
            bits.append(f"manual: {mr}")
        if ar:
            bits.append(f"auto: {ar}")
        if bits:
            rec["reason"] = " | ".join(bits)
        else:
            rec["reason"] = "merged errata (trim bounds only)"

        out[fid] = rec
    return out


def load_merged_errata(
    gold_path: str | os.PathLike[str],
    manual_errata_path: str | None,
    *,
    merge_auto: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """
    Load manual errata (if path exists) and optional auto errata beside gold.

    Returns:
        eval_errata: merged dict for ``evaluate_model_comprehensive`` / score.py
        report_meta: ``{"manual": ..., "auto": ..., "auto_path": ..., "merged": ...}``
    """
    manual = _load_json_dict(manual_errata_path) if manual_errata_path else {}
    gold_parent = Path(gold_path).resolve().parent
    auto_path = gold_parent / AUTO_ERRATA_BASENAME
    auto: dict[str, Any] = {}
    if merge_auto:
        auto = _load_json_dict(auto_path)

    merged = merge_errata_for_evaluation(manual, auto) if (manual or auto) else {}

    report_meta: dict[str, Any] = {
        "manual": manual,
        "auto": auto,
        "merged": merged,
        "auto_path": str(auto_path) if merge_auto else None,
        "manual_path": str(manual_errata_path) if manual_errata_path else None,
    }
    return merged, report_meta


def _errata_table_rows(err: dict[str, Any]) -> list[list[str]]:
    rows = []
    for fid in sorted(err.keys()):
        e = err[fid]
        if not isinstance(e, dict):
            continue
        rows.append(
            [
                fid,
                str(e.get("trim_start", "")),
                str(e.get("trim_end", "")),
                str(e.get("source", "")),
                str(e.get("reason", ""))[:200],
            ]
        )
    return rows


def format_errata_report_md(meta: dict[str, Any]) -> str:
    """Markdown subsection: manual vs auto errata and merged effective UEM."""
    manual = meta.get("manual") or {}
    auto = meta.get("auto") or {}
    merged = meta.get("merged") or {}
    lines: list[str] = [
        "### Errata and evaluation window (UEM)",
        "",
        "Metrics and timelines use a single evaluation interval per file: "
        "`[trim_start, trim_end]` when set (seconds), intersected with audio duration from run metadata. "
        "Auto errata is written beside trimmed gold as `AUTO_DATASET_ERRATA.json` and merged with manual errata by default.",
        "",
    ]
    ap = meta.get("auto_path")
    mp = meta.get("manual_path")
    if mp:
        lines.append(f"- **Manual errata path:** `{mp}`")
    if ap:
        lines.append(f"- **Auto errata path:** `{ap}`")
    lines.append("")

    if not manual and not auto and not merged:
        lines.append("*No errata entries were loaded for this report.*")
        lines.append("")
        return "\n".join(lines)

    hdr = "| File ID | trim_start (s) | trim_end (s) | source | reason (trunc.) |\n|---|---|---|---|---|"

    if manual:
        lines.append("#### Manual / gold errata")
        lines.append("")
        lines.append(hdr)
        for r in _errata_table_rows(manual):
            lines.append("| " + " | ".join(r) + " |")
        lines.append("")
    else:
        lines.append("*No manual errata file entries.*")
        lines.append("")

    if auto:
        lines.append("#### Auto-generated errata (silence trim caps)")
        lines.append("")
        lines.append(hdr)
        for r in _errata_table_rows(auto):
            lines.append("| " + " | ".join(r) + " |")
        lines.append("")
    else:
        lines.append("*No auto errata file (`AUTO_DATASET_ERRATA.json`) or it is empty.*")
        lines.append("")

    if merged:
        lines.append("#### Merged effective UEM (used for scoring)")
        lines.append("")
        lines.append("| File ID | trim_start (s) | trim_end (s) | reason |")
        lines.append("|---|---|---|---|")
        for fid in sorted(merged.keys()):
            m = merged[fid]
            lines.append(
                "| "
                + " | ".join(
                    [
                        fid,
                        str(m.get("trim_start", "")),
                        str(m.get("trim_end", "")),
                        str(m.get("reason", ""))[:200],
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)
