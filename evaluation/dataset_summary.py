from __future__ import annotations

import datetime as _dt
import os
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from pyannote.core import Annotation

from gold_rttm_provenance import parse_semicolon_kv_line, read_leading_rttm_comments


@dataclass(frozen=True)
class AudioProbe:
    path: str
    format: str | None
    subtype: str | None
    sample_rate_hz: int | None
    channels: int | None
    duration_s: float | None
    bitrate_bps: int | None
    error: str | None = None


def _annotation_extent_s(ann: Annotation) -> float:
    if ann is None:
        return 0.0
    tl = ann.get_timeline()
    if len(tl) == 0:
        return 0.0
    ext = tl.extent()
    try:
        return float(ext.end - ext.start)
    except Exception:
        return 0.0


def _annotation_rttm_speech_s(ann: Annotation) -> float:
    """
    Sum of all RTTM segment durations.

    Note: this sums per-track segments (so overlapping speakers add up).
    """
    if ann is None:
        return 0.0
    total = 0.0
    for seg, _track, _label in ann.itertracks(yield_label=True):
        try:
            total += float(seg.duration)
        except Exception:
            continue
    return total


def _histogram(
    items: Iterable[dict[str, str]],
    key: str,
    *,
    exclude: set[str] | None = None,
) -> dict[str, int]:
    ex = exclude or set()
    c: Counter[str] = Counter()
    for it in items:
        v = (it.get(key) or "").strip()
        if not v or v in ex:
            continue
        c[v] += 1
    return dict(c.most_common())


def _guess_audio_file_paths(audio_dir: str, file_id: str) -> list[str]:
    stems = [file_id]
    exts = [".wav", ".WAV", ".mp3", ".MP3", ".flac", ".FLAC", ".ogg", ".OGG", ".m4a", ".M4A"]
    out: list[str] = []
    for st in stems:
        for ext in exts:
            out.append(os.path.join(audio_dir, st + ext))
    return out


def _pcm_bitrate_bps_from_subtype(
    format_name: str | None, subtype: str | None, sample_rate_hz: int | None, channels: int | None
) -> int | None:
    """Nominal linear PCM bitrate when subtype implies a fixed bit depth."""
    if not sample_rate_hz or not channels or not subtype:
        return None
    st = str(subtype).upper().replace(" ", "_")
    bits: int | None = None
    if "PCM_32" in st or "32-BIT" in st:
        bits = 32
    elif "PCM_24" in st or "24-BIT" in st:
        bits = 24
    elif "PCM_16" in st or "16-BIT" in st:
        bits = 16
    elif "PCM_U8" in st or "PCM_S8" in st or "_8" in st:
        bits = 8
    elif "FLOAT" in st or "IEEE_FLOAT" in st:
        bits = 32
    elif "24" in st:
        bits = 24
    elif "16" in st:
        bits = 16
    if bits is None:
        return None
    fn = (format_name or "").upper()
    if fn == "WAV" or fn == "AIFF":
        return int(sample_rate_hz) * int(channels) * int(bits)
    return None


def _probe_audio_with_soundfile(path: str) -> AudioProbe:
    try:
        import soundfile as sf  # type: ignore

        with sf.SoundFile(path) as f:
            duration = (float(f.frames) / float(f.samplerate)) if f.samplerate else None
            fmt = getattr(f, "format", None)
            sub = getattr(f, "subtype", None)
            sr = int(f.samplerate) if f.samplerate else None
            ch = int(f.channels) if f.channels else None
            br = _pcm_bitrate_bps_from_subtype(fmt, sub, sr, ch)
            return AudioProbe(
                path=path,
                format=fmt,
                subtype=sub,
                sample_rate_hz=sr,
                channels=ch,
                duration_s=duration,
                bitrate_bps=br,
                error=None,
            )
    except Exception as e:
        return AudioProbe(
            path=path,
            format=None,
            subtype=None,
            sample_rate_hz=None,
            channels=None,
            duration_s=None,
            bitrate_bps=None,
            error=f"soundfile probe failed: {e!r}",
        )


def _probe_audio_with_wave(path: str) -> AudioProbe:
    try:
        import wave

        with wave.open(path, "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            frames = wf.getnframes()
            sampwidth = wf.getsampwidth()  # bytes per sample
            duration = (float(frames) / float(sr)) if sr else None
            bits = int(sampwidth) * 8 if sampwidth else None
            bitrate = int(sr) * int(ch) * int(bits) if sr and ch and bits else None
            return AudioProbe(
                path=path,
                format="WAV",
                subtype=f"PCM_{bits}bit" if bits else "PCM",
                sample_rate_hz=int(sr) if sr else None,
                channels=int(ch) if ch else None,
                duration_s=duration,
                bitrate_bps=bitrate,
                error=None,
            )
    except Exception as e:
        return AudioProbe(
            path=path,
            format=None,
            subtype=None,
            sample_rate_hz=None,
            channels=None,
            duration_s=None,
            bitrate_bps=None,
            error=f"wave probe failed: {e!r}",
        )


def probe_audio_for_file(audio_dir: str, file_id: str) -> AudioProbe | None:
    if not audio_dir or not os.path.isdir(audio_dir):
        return None
    for cand in _guess_audio_file_paths(audio_dir, file_id):
        if not os.path.isfile(cand):
            continue
        sf_probe = _probe_audio_with_soundfile(cand)
        if sf_probe.error is None:
            return sf_probe
        if cand.lower().endswith(".wav"):
            wav_probe = _probe_audio_with_wave(cand)
            return wav_probe if wav_probe.error is None else sf_probe
        return sf_probe
    return None


def parse_gold_provenance(gold_rttm_path: str) -> dict[str, Any]:
    comments = read_leading_rttm_comments(gold_rttm_path, max_lines=2)
    gold_kv: dict[str, str] = {}
    trim_kv: dict[str, str] = {}
    if comments:
        if "gold_rttm" in comments[0]:
            gold_kv = dict(parse_semicolon_kv_line(comments[0]))
        if len(comments) > 1 and "trim_params" in comments[1]:
            trim_kv = dict(parse_semicolon_kv_line(comments[1]))
    return {
        "comments": comments,
        "gold_rttm": gold_kv,
        "trim_params": trim_kv,
    }


def build_dataset_overview_dict(
    *,
    gold_rttm_path: str,
    gold_annots: dict[str, Annotation],
    meta_dict: dict[str, dict[str, str]] | None,
    errata_dict: dict[str, Any] | None,
    audio_dir_override: str | None = None,
) -> dict[str, Any]:
    provenance = parse_gold_provenance(gold_rttm_path)
    audio_dir = (audio_dir_override or provenance.get("gold_rttm", {}).get("audio_dir") or "").strip()
    if audio_dir:
        audio_dir = os.path.abspath(os.path.normpath(audio_dir))

    per_file: dict[str, Any] = {}
    extent_vals: list[float] = []
    speech_vals: list[float] = []
    audio_formats: Counter[str] = Counter()
    audio_sample_rates: Counter[int] = Counter()

    meta_dict = meta_dict or {}
    errata_dict = errata_dict or {}

    for fid, ann in gold_annots.items():
        extent_s = _annotation_extent_s(ann)
        speech_s = _annotation_rttm_speech_s(ann)
        extent_vals.append(extent_s)
        speech_vals.append(speech_s)

        audio_probe = probe_audio_for_file(audio_dir, fid) if audio_dir else None
        if audio_probe and audio_probe.format:
            audio_formats[audio_probe.format] += 1
        if audio_probe and audio_probe.sample_rate_hz:
            audio_sample_rates[int(audio_probe.sample_rate_hz)] += 1

        per_file[fid] = {
            "file_id": fid,
            "gold_timeline_span_s": extent_s,
            "gold_speech_s": speech_s,
            "metadata": meta_dict.get(fid, {}),
            "errata": errata_dict.get(fid, {}),
            "audio_probe": asdict(audio_probe) if audio_probe else None,
        }

    def _agg(vals: list[float]) -> dict[str, float]:
        if not vals:
            return {"total_s": 0.0, "min_s": 0.0, "mean_s": 0.0, "max_s": 0.0}
        total = float(sum(vals))
        return {
            "total_s": total,
            "min_s": float(min(vals)),
            "mean_s": float(total / float(len(vals))),
            "max_s": float(max(vals)),
        }

    meta_items = list(meta_dict.values())
    aggregate = {
        "file_count": int(len(gold_annots)),
        "gold_timeline_span_s": _agg(extent_vals),
        "gold_speech_s": _agg(speech_vals),
        "categories": {
            "Domain": _histogram(meta_items, "Domain", exclude={"Unknown", "N/A"}),
            "Type": _histogram(meta_items, "Type", exclude={"Unknown", "N/A"}),
            "Quality": _histogram(meta_items, "Quality", exclude={"Unknown", "N/A"}),
            "Device": _histogram(meta_items, "Device", exclude={"Unknown", "N/A"}),
        },
        "audio_summary": {
            "audio_dir": audio_dir or None,
            "formats": dict(audio_formats.most_common()) if audio_formats else {},
            "sample_rates_hz": dict(audio_sample_rates.most_common()) if audio_sample_rates else {},
        },
    }

    return {
        "provenance": provenance,
        "files": per_file,
        "aggregate": aggregate,
    }


def _fmt_s(x: float) -> str:
    if x >= 3600:
        return f"{x / 3600.0:.2f} h"
    if x >= 60:
        return f"{x / 60.0:.2f} min"
    return f"{x:.1f} s"


def _fmt_hist(h: dict[str, int], limit: int = 6) -> str:
    if not h:
        return "N/A"
    items = list(h.items())[:limit]
    s = ", ".join(f"{k} ({v})" for k, v in items)
    more = len(h) - len(items)
    return f"{s}{', …' if more > 0 else ''}"


def build_dataset_overview_markdown(overview: dict[str, Any], category_label: str) -> str:
    agg = overview.get("aggregate", {}) or {}
    spans = agg.get("gold_timeline_span_s", {}) or {}
    speech = agg.get("gold_speech_s", {}) or {}
    cats = (agg.get("categories", {}) or {}).copy()
    audio = agg.get("audio_summary", {}) or {}

    lines: list[str] = []
    lines.append("### Dataset overview\n")
    lines.append(f"- **Files:** {agg.get('file_count', 0)}")
    lines.append(
        "- **Gold timeline span (extent):** "
        f"total {_fmt_s(float(spans.get('total_s', 0.0)))}; "
        f"min {_fmt_s(float(spans.get('min_s', 0.0)))}, "
        f"mean {_fmt_s(float(spans.get('mean_s', 0.0)))}, "
        f"max {_fmt_s(float(spans.get('max_s', 0.0)))}"
    )
    lines.append(
        "- **Gold RTTM speech time (sum of RTTM segments; overlaps add up):** "
        f"total {_fmt_s(float(speech.get('total_s', 0.0)))}; "
        f"min {_fmt_s(float(speech.get('min_s', 0.0)))}, "
        f"mean {_fmt_s(float(speech.get('mean_s', 0.0)))}, "
        f"max {_fmt_s(float(speech.get('max_s', 0.0)))}"
    )

    dom = cats.get("Domain", {}) or {}
    if dom:
        lines.append(f"- **{category_label}:** {_fmt_hist(dom)}")
    for k in ("Type", "Quality", "Device"):
        h = cats.get(k, {}) or {}
        if h:
            lines.append(f"- **{k}:** {_fmt_hist(h)}")

    if audio.get("audio_dir") and (audio.get("formats") or audio.get("sample_rates_hz")):
        sr_map = audio.get("sample_rates_hz", {}) or {}
        try:
            sr_items = sorted(sr_map.items(), key=lambda kv: int(kv[0]))
        except Exception:
            sr_items = list(sr_map.items())
        sr_str = ", ".join(f"{k} Hz ({v})" for k, v in sr_items[:6])
        if len(sr_items) > 6:
            sr_str += ", …"
        lines.append(
            "- **Audio technicals (best effort):** "
            f"formats {_fmt_hist(audio.get('formats', {}), limit=6)}; "
            f"sample rates {sr_str if sr_str else 'N/A'}"
        )
    elif audio.get("audio_dir"):
        lines.append("- **Audio technicals (best effort):** audio directory was found but no files were probed.")
    else:
        lines.append("- **Audio technicals (best effort):** not available (no `audio_dir` in gold provenance and no override).")

    return "\n".join(lines) + "\n\n"


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat()

