"""
Shared gold RTTM generation from TRS (ROG) or CHA (CCPCL): defaults, provenance header, merge, parse, write.
Optional audio-informed silence trimming via trim_gold_silences_rttm (lazy import).
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any, NamedTuple, TextIO


class TrsRttmParseResult(NamedTuple):
    """One TRS parse: RTTM line count, unmapped ref drops, sum of written segment durations (s)."""

    lines_written: int
    dropped_unknown_speaker_refs: int
    speech_seconds: float


DEFAULT_MERGE_THRESHOLD = 1.0
DEFAULT_MIN_DURATION = 0.1
DEFAULT_PRIORITIZE_POG = False


_REPO_ROOT = Path(__file__).resolve().parent


def _metadata_rel_path(path: Path | None) -> str | None:
    """
    Format a path for provenance metadata.

    If the resolved path is within this repository, return a repo-relative POSIX path
    (e.g. `data/ROG-Dialog/audio`). Otherwise, fall back to the resolved absolute path.
    """
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def format_gold_rttm_header(
    *,
    pipeline: str,
    source: str,
    merge_threshold: float,
    min_duration: float,
    prioritize_pog: bool | str,
    output_name: str,
    trs_dir: str | None = None,
    cha_dir: str | None = None,
    audio_dir: str | None = None,
) -> str:
    """Single semicolon provenance line for generated gold RTTM files."""
    if prioritize_pog is True or prioritize_pog is False:
        pog_s = str(prioritize_pog).lower()
    else:
        pog_s = str(prioritize_pog)
    parts = [
        "gold_rttm",
        f"pipeline={pipeline}",
        f"source={source}",
        f"merge_threshold={merge_threshold}s",
        f"min_duration={min_duration}s",
        f"prioritize_pog={pog_s}",
        f"output={output_name}",
    ]
    if trs_dir is not None:
        parts.append(f"trs_dir={trs_dir}")
    if cha_dir is not None:
        parts.append(f"cha_dir={cha_dir}")
    if audio_dir is not None:
        parts.append(f"audio_dir={audio_dir}")
    return "; " + " ".join(parts) + "\n"


def format_trim_provenance_line(trim_params: Any) -> str:
    """Second RTTM comment line documenting silence-trim parameters."""
    items = [f"{k}={v}" for k, v in asdict(trim_params).items()]
    return "; trim_params " + " ".join(items) + "\n"


AUTO_ERRATA_FILENAME = "AUTO_DATASET_ERRATA.json"


def _auto_errata_record_from_edge_caps(edge_caps: dict[str, Any]) -> dict[str, Any] | None:
    """One file_id entry for AUTO_DATASET_ERRATA.json, or None if no UEM adjustment needed."""
    if edge_caps.get("trim_start") is None and edge_caps.get("trim_end") is None:
        return None
    rec: dict[str, Any] = {
        "source": "auto",
        "reason": (
            "auto: VAD-informed speech boundary exceeds what max_trim_s can move on the gold "
            "RTTM edge; residual margin still contains misleading speech labels. UEM excludes "
            "these edges during evaluation."
        ),
    }
    if edge_caps.get("trim_start") is not None:
        rec["trim_start"] = float(edge_caps["trim_start"])
    if edge_caps.get("trim_end") is not None:
        rec["trim_end"] = float(edge_caps["trim_end"])
    for k in ("max_trim_s", "audio_duration_s", "residual_leading_s", "residual_trailing_s"):
        if k in edge_caps:
            rec[k] = float(edge_caps[k])
    return rec


def write_auto_dataset_errata_json(trimmed_rttm_path: Path, edge_caps_by_file: dict[str, dict[str, Any]]) -> None:
    """Write or remove AUTO_DATASET_ERRATA.json beside the trimmed gold RTTM."""
    out_path = trimmed_rttm_path.parent / AUTO_ERRATA_FILENAME
    payload: dict[str, Any] = {}
    for fid, caps in edge_caps_by_file.items():
        rec = _auto_errata_record_from_edge_caps(caps)
        if rec is not None:
            payload[fid] = rec
    if not payload:
        if out_path.is_file():
            out_path.unlink()
        return
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote auto errata ({len(payload)} file(s)): {out_path}")


def trimmed_rttm_path(output_path: Path) -> Path:
    """foo.rttm -> foo_trimmed.rttm"""
    output_path = Path(output_path)
    if output_path.suffix.lower() == ".rttm":
        return output_path.with_name(output_path.stem + "_trimmed" + output_path.suffix)
    return output_path.parent / f"{output_path.name}_trimmed.rttm"


def _try_load_trimmer() -> tuple[dict[str, Any] | None, str | None]:
    """
    Import numpy + parselmouth + trim_gold_silences_rttm API.
    Returns (bundle, None) on success, or (None, error_message) on failure.
    """
    try:
        import numpy  # noqa: F401
        import parselmouth  # noqa: F401
        from parselmouth.praat import call  # noqa: F401
    except ImportError as e:
        name = getattr(e, "name", None) or str(e).split()[-1] if str(e) else "unknown"
        msg = (
            f"Silence trimming skipped: import failed ({e!r}; module={name!r}). "
            "Install with: pip install numpy praat-parselmouth — or use uv: "
            "see docs/data_preparation.md#python-environment-uv"
        )
        return None, msg
    try:
        from trim_gold_silences_rttm import (
            TrimParams,
            TrimStats,
            merge_stats,
            print_stats_summary,
            trim_file_segments,
            write_rttm_lines,
        )
    except ImportError as e:
        msg = (
            f"Silence trimming skipped: could not import trim_gold_silences_rttm ({e!r}). "
            "Ensure repo dependencies are installed."
        )
        return None, msg

    # Same defaults as convert_trs_to_trim_rttm.py TRIM_PARAMS
    default_trim = TrimParams(
        pitch_floor=75.0,
        pitch_ceiling=500.0,
        intensity_drop_db=15.0,
        guard_ms=30.0,
        max_trim_s=1.5,
        min_duration=0.1,
        pad_s=0.5,
        time_step=0.01,
        method="pitch_or_intensity",
        trim_silence_within=True,
        min_silence_dur=0.5,
        verbose=True,
    )
    bundle = {
        "TrimParams": TrimParams,
        "TrimStats": TrimStats,
        "merge_stats": merge_stats,
        "print_stats_summary": print_stats_summary,
        "trim_file_segments": trim_file_segments,
        "write_rttm_lines": write_rttm_lines,
        "default_trim_params": default_trim,
    }
    return bundle, None


def _prepare_noninteractive() -> bool:
    return os.environ.get("DIABENCH_PREPARE_NONINTERACTIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def merge_segments_linear(segments: list[dict], gap_threshold: float) -> list[dict]:
    """Merge adjacent segments of the same speaker if the gap is <= gap_threshold (seconds)."""
    if not segments:
        return []
    segs = sorted((dict(s) for s in segments), key=lambda x: x["start"])
    merged: list[dict] = []
    current = segs[0].copy()
    for nxt in segs[1:]:
        if nxt["speaker"] == current["speaker"] and nxt["start"] - current["end"] <= gap_threshold:
            current["end"] = max(current["end"], nxt["end"])
            continue
        merged.append(current)
        current = nxt.copy()
    merged.append(current)
    return merged


def parse_trs_to_segments(
    trs_path: Path,
    merge_threshold: float,
    min_duration: float,
) -> tuple[str, list[dict], TrsRttmParseResult]:
    """
    Parse TRS -> merged segments as dicts with start, end, duration, speaker (trim-ready).
    Drops <Turn> speaker refs not present in <Speaker>.
    """
    try:
        tree = ET.parse(trs_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Warning: failed to parse {trs_path}: {e}")
        return "", [], TrsRttmParseResult(0, 0, 0.0)

    file_id = trs_path.stem.replace("-std", "").replace("-pog", "")

    speaker_map: dict[str, str] = {}
    for spk in root.findall(".//Speaker"):
        spk_id = spk.get("id")
        spk_name = spk.get("name")
        if spk_id and spk_name:
            speaker_map[spk_id] = spk_name

    all_raw_segments: list[dict] = []
    dropped_unknown = 0
    for turn in root.findall(".//Turn"):
        start_time = float(turn.get("startTime", 0))
        end_time = float(turn.get("endTime", 0))
        spk_refs = turn.get("speaker")
        if not spk_refs:
            continue
        for spk_ref in spk_refs.split():
            if spk_ref not in speaker_map:
                dropped_unknown += 1
                continue
            real_name = speaker_map[spk_ref]
            all_raw_segments.append({"start": start_time, "end": end_time, "speaker": real_name})

    smooth_segments = merge_segments_linear(all_raw_segments, merge_threshold)
    out_segments: list[dict] = []
    speech_seconds = 0.0
    for seg in smooth_segments:
        duration = seg["end"] - seg["start"]
        if duration < min_duration:
            continue
        out_segments.append(
            {
                "start": seg["start"],
                "end": seg["end"],
                "duration": duration,
                "speaker": seg["speaker"],
            }
        )
        speech_seconds += duration

    return file_id, out_segments, TrsRttmParseResult(len(out_segments), dropped_unknown, speech_seconds)


def _write_rttm_segments(out_f: TextIO, file_id: str, segments: list[dict]) -> None:
    for seg in segments:
        out_f.write(
            f"SPEAKER {file_id} 1 {seg['start']:.3f} {seg['duration']:.3f} <NA> <NA> "
            f"{seg['speaker']} <NA> <NA>\n"
        )


def parse_trs_to_rttm(
    trs_path: Path,
    output_file: TextIO,
    merge_threshold: float,
    min_duration: float,
) -> TrsRttmParseResult:
    """Parse one TRS file and append RTTM lines (untrimmed)."""
    file_id, segments, res = parse_trs_to_segments(trs_path, merge_threshold, min_duration)
    if not file_id:
        return res
    _write_rttm_segments(output_file, file_id, segments)
    return res


def generate_gold_rttm_from_trs(
    trs_dir: Path,
    output_path: Path,
    merge_threshold: float,
    min_duration: float,
    prioritize_pog: bool,
    *,
    pipeline: str,
    audio_dir: Path | None = None,
    enable_trimming: bool = False,
) -> None:
    trs_dir = Path(trs_dir)
    output_path = Path(output_path)
    if not trs_dir.is_dir():
        print(f"TRS directory not found: {trs_dir}")
        return

    all_trs = sorted(trs_dir.glob("*.trs"))
    if not all_trs:
        print(f"No .trs files under {trs_dir}")
        return

    file_groups: dict[str, list[Path]] = {}
    for f in all_trs:
        base = f.stem.replace("-std", "").replace("-pog", "")
        file_groups.setdefault(base, []).append(f)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_name = output_path.name
    header = format_gold_rttm_header(
        pipeline=pipeline,
        source="trs",
        merge_threshold=merge_threshold,
        min_duration=min_duration,
        prioritize_pog=prioritize_pog,
        output_name=final_name,
        trs_dir=_metadata_rel_path(trs_dir),
        audio_dir=_metadata_rel_path(audio_dir) if audio_dir and Path(audio_dir).is_dir() else None,
    )

    total_segments = 0
    total_dropped_unknown = 0
    total_speech_seconds = 0.0
    segments_by_file: dict[str, list[dict]] = {}

    with output_path.open("w", encoding="utf-8") as out_f:
        out_f.write(header)
        for base_id, files in sorted(file_groups.items()):
            std_files = [f for f in files if "-std" in f.name]
            pog_files = [f for f in files if "-pog" in f.name]
            if prioritize_pog:
                selected = pog_files[0] if pog_files else (std_files[0] if std_files else files[0])
            else:
                selected = std_files[0] if std_files else (pog_files[0] if pog_files else files[0])
            print(f"Processing {base_id} -> {selected.name}")
            fid, segments, res = parse_trs_to_segments(selected, merge_threshold, min_duration)
            segments_by_file[fid] = segments
            _write_rttm_segments(out_f, fid, segments)
            total_segments += res.lines_written
            total_dropped_unknown += res.dropped_unknown_speaker_refs
            total_speech_seconds += res.speech_seconds
            if res.dropped_unknown_speaker_refs:
                print(
                    f"  dropped {res.dropped_unknown_speaker_refs} raw <Turn> speaker ref(s) "
                    "not in <Speaker> map"
                )

    print(f"Gold RTTM written: {output_path} ({total_segments} segments)")
    print(
        f"Linear merge threshold={merge_threshold}s, source priority: "
        f"{'POG' if prioritize_pog else 'STD'}"
    )
    if total_dropped_unknown:
        print(
            f"Total dropped raw speaker refs (unmapped in <Speaker>): {total_dropped_unknown} "
            "(excluded from gold RTTM)"
        )
    else:
        print("Total dropped raw speaker refs (unmapped in <Speaker>): 0")
    print(
        f"Total speech duration in gold RTTM: {total_speech_seconds:.3f} s "
        f"({total_speech_seconds / 60.0:.3f} min)"
    )

    if enable_trimming:
        bundle, err = _try_load_trimmer()
        if bundle is None:
            print(err)
            if _prepare_noninteractive():
                raise SystemExit(1)
            return
        audio_path = Path(audio_dir) if audio_dir is not None else None
        if audio_path is None or not audio_path.is_dir():
            print(
                "Silence trimming skipped: audio_dir is missing or not a directory "
                "(pass dataset audio_dir when using enable_trimming)."
            )
            if _prepare_noninteractive():
                raise SystemExit(1)
            return

        trim_params = bundle["default_trim_params"]
        trim_file_segments = bundle["trim_file_segments"]
        merge_stats = bundle["merge_stats"]
        print_stats_summary = bundle["print_stats_summary"]
        write_rttm_lines = bundle["write_rttm_lines"]
        TrimStats = bundle["TrimStats"]

        trimmed_path = trimmed_rttm_path(output_path)
        trimmed_name = trimmed_path.name
        header_trim = format_gold_rttm_header(
            pipeline=pipeline,
            source="trs",
            merge_threshold=merge_threshold,
            min_duration=min_duration,
            prioritize_pog=prioritize_pog,
            output_name=trimmed_name,
            trs_dir=_metadata_rel_path(trs_dir),
            audio_dir=_metadata_rel_path(audio_path),
        )
        trim_line = format_trim_provenance_line(trim_params)

        master_stats = TrimStats()
        files_trimmed = 0
        edge_caps_by_file: dict[str, dict[str, Any]] = {}
        with trimmed_path.open("w", encoding="utf-8") as t_out:
            t_out.write(header_trim)
            t_out.write(trim_line)
            for base_id in sorted(segments_by_file.keys()):
                segs = segments_by_file[base_id]
                wav = audio_path / f"{base_id}.wav"
                trimmed, fstats, f_caps = trim_file_segments(segs, wav, trim_params)
                merge_stats(master_stats, fstats)
                edge_caps_by_file[base_id] = f_caps
                write_rttm_lines(t_out, base_id, trimmed)
                files_trimmed += 1

        write_auto_dataset_errata_json(trimmed_path, edge_caps_by_file)

        trimmed_speech_sec = 0.0
        with trimmed_path.open("r", encoding="utf-8") as rf:
            for line in rf:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "SPEAKER":
                    trimmed_speech_sec += float(parts[4])

        print(f"Gold RTTM (trimmed) written: {trimmed_path}")
        print(
            f"Silence trimming summary: edge-trimmed_segments={master_stats.trimmed}, "
            f"edge_silence_removed_s={master_stats.trim_start_total + master_stats.trim_end_total:.3f}, "
            f"internal_silence_removed_s={master_stats.silence_removed_total:.3f}, "
            f"output_segments={master_stats.output_segments}"
        )
        print(
            f"Total speech duration in trimmed gold RTTM: {trimmed_speech_sec:.3f} s "
            f"({trimmed_speech_sec / 60.0:.3f} min)"
        )
        print_stats_summary(master_stats, files_trimmed, trim_params.trim_silence_within)


def collect_wav_stems(audio_dir: Path) -> set[str]:
    audio_path = Path(audio_dir)
    if not audio_path.is_dir():
        return set()
    stems: set[str] = set()
    for wav_path in audio_path.rglob("*"):
        if wav_path.is_file() and wav_path.suffix.lower() == ".wav":
            stems.add(wav_path.stem)
    return stems


def parse_cha_file(cha_path: Path) -> list[dict]:
    segments: list[dict] = []
    speaker_pattern = re.compile(r"^\*(?P<speaker>[^:]+):.*?(?P<times>\d+_\d+)")
    with cha_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("*"):
                continue
            m = speaker_pattern.search(line)
            if not m:
                continue
            speaker = m.group("speaker").strip().replace(" ", "_")
            times = m.group("times")
            try:
                start_ms, end_ms = map(int, times.split("_"))
            except ValueError:
                continue
            start = start_ms / 1000.0
            end = end_ms / 1000.0
            if end <= start:
                continue
            segments.append({"start": start, "end": end, "speaker": speaker})
    return segments


def generate_gold_rttm_from_cha(
    cha_dir: Path,
    audio_dir: Path,
    output_path: Path,
    merge_threshold: float,
    min_duration: float,
    *,
    pipeline: str = "CHILDES-CCPCL",
    enable_trimming: bool = False,
) -> None:
    cha_dir = Path(cha_dir)
    if not cha_dir.is_dir():
        alt_cha_dir = cha_dir / "CCPCL"
        if alt_cha_dir.is_dir():
            cha_dir = alt_cha_dir
        else:
            raise SystemExit(f"CHA directory not found: {cha_dir}")

    all_files = sorted(cha_dir.glob("*.cha"))
    if not all_files:
        raise SystemExit(f"No .cha files in {cha_dir}")

    audio_dir = Path(audio_dir)
    wav_stems = collect_wav_stems(audio_dir)
    selected_files = all_files
    if wav_stems:
        matched = [cha_file for cha_file in all_files if cha_file.stem in wav_stems]
        if matched:
            selected_files = matched
            skipped = len(all_files) - len(selected_files)
            print(
                f"Filtering CHA files by WAV stems from {audio_dir}: "
                f"{len(selected_files)} matched, {skipped} skipped"
            )
        else:
            print(
                f"Warning: found {len(wav_stems)} WAV stems in {audio_dir}, "
                "but none match .cha filenames. Processing all .cha files."
            )
    else:
        print(f"Warning: no WAV files found in {audio_dir}. Processing all .cha files.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_name = output_path.name
    header = format_gold_rttm_header(
        pipeline=pipeline,
        source="cha",
        merge_threshold=merge_threshold,
        min_duration=min_duration,
        prioritize_pog="N/A",
        output_name=final_name,
        cha_dir=_metadata_rel_path(cha_dir),
        audio_dir=_metadata_rel_path(audio_dir),
    )

    segments_by_file: dict[str, list[dict]] = {}
    total_segments = 0
    total_speech_seconds = 0.0

    for cha_file in selected_files:
        base_id = cha_file.stem
        raw_segments = parse_cha_file(cha_file)
        smooth = merge_segments_linear(raw_segments, merge_threshold)
        segs: list[dict] = []
        for seg in smooth:
            duration = seg["end"] - seg["start"]
            if duration < min_duration:
                continue
            segs.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "duration": duration,
                    "speaker": seg["speaker"],
                }
            )
        segments_by_file[base_id] = segs
        total_segments += len(segs)
        total_speech_seconds += sum(s["duration"] for s in segs)

    with output_path.open("w", encoding="utf-8") as out:
        out.write(header)
        for base_id in sorted(segments_by_file.keys()):
            _write_rttm_segments(out, base_id, segments_by_file[base_id])

    print(f"Wrote RTTM to {output_path} with {total_segments} segments")
    print(
        f"Total speech duration in gold RTTM: {total_speech_seconds:.3f} s "
        f"({total_speech_seconds / 60.0:.3f} min)"
    )

    if enable_trimming:
        bundle, err = _try_load_trimmer()
        if bundle is None:
            print(err)
            if _prepare_noninteractive():
                raise SystemExit(1)
            return
        if not audio_dir.is_dir():
            print("Silence trimming skipped: audio_dir is not a directory.")
            if _prepare_noninteractive():
                raise SystemExit(1)
            return

        trim_params = bundle["default_trim_params"]
        trim_file_segments = bundle["trim_file_segments"]
        merge_stats = bundle["merge_stats"]
        print_stats_summary = bundle["print_stats_summary"]
        write_rttm_lines = bundle["write_rttm_lines"]
        TrimStats = bundle["TrimStats"]

        trimmed_path = trimmed_rttm_path(output_path)
        trimmed_name = trimmed_path.name
        header_trim = format_gold_rttm_header(
            pipeline=pipeline,
            source="cha",
            merge_threshold=merge_threshold,
            min_duration=min_duration,
            prioritize_pog="N/A",
            output_name=trimmed_name,
            cha_dir=_metadata_rel_path(cha_dir),
            audio_dir=_metadata_rel_path(audio_dir),
        )
        trim_line = format_trim_provenance_line(trim_params)

        master_stats = TrimStats()
        files_trimmed = 0
        edge_caps_by_file: dict[str, dict[str, Any]] = {}
        with trimmed_path.open("w", encoding="utf-8") as t_out:
            t_out.write(header_trim)
            t_out.write(trim_line)
            for base_id in sorted(segments_by_file.keys()):
                segs = segments_by_file[base_id]
                wav = audio_dir / f"{base_id}.wav"
                trimmed, fstats, f_caps = trim_file_segments(segs, wav, trim_params)
                merge_stats(master_stats, fstats)
                edge_caps_by_file[base_id] = f_caps
                write_rttm_lines(t_out, base_id, trimmed)
                files_trimmed += 1

        write_auto_dataset_errata_json(trimmed_path, edge_caps_by_file)

        trimmed_speech_sec = 0.0
        with trimmed_path.open("r", encoding="utf-8") as rf:
            for line in rf:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "SPEAKER":
                    trimmed_speech_sec += float(parts[4])

        print(f"Gold RTTM (trimmed) written: {trimmed_path}")
        print(
            f"Silence trimming summary: edge-trimmed_segments={master_stats.trimmed}, "
            f"edge_silence_removed_s={master_stats.trim_start_total + master_stats.trim_end_total:.3f}, "
            f"internal_silence_removed_s={master_stats.silence_removed_total:.3f}, "
            f"output_segments={master_stats.output_segments}"
        )
        print(
            f"Total speech duration in trimmed gold RTTM: {trimmed_speech_sec:.3f} s "
            f"({trimmed_speech_sec / 60.0:.3f} min)"
        )
        print_stats_summary(master_stats, files_trimmed, trim_params.trim_silence_within)
