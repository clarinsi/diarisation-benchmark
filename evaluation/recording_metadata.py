"""
Normalized recording metadata for benchmark reports.

Maps heterogeneous sources into the same dict shape expected by the report
pipeline (keys: Domain, Type, Quality, Device, Title, Keywords) keyed by
gold RTTM file id (recording stem).

CCPCL `0demo.xlsx` (TalkBank CCPCL.zip): sheet ``Sheet1`` with columns
  - Participant ID → join key (matches ``.cha`` / WAV stem, e.g. ``1-00606``)
  - Chronological age → CHILDES format ``years;months`` in the sheet (e.g. ``3;11``);
    for reports, ``Domain`` uses **whole years only** (e.g. ``Age 3 / M``) so category plots
    are not fragmented by month. Raw age is copied into ``Keywords`` when month detail exists.
  - Gender → ``M`` / ``F``
  - Audio, Transcript_CLAN → reference filenames (``*-i.mp3`` / ``*-i.cha``)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd


def _s(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _ccpcl_age_years_label(age_raw: Any) -> str:
    """
    Map CCPCL chronological age to a whole-year label for stratification (Domain).

    TalkBank / CHILDES often encodes age as ``years;months`` (e.g. ``3;11``). We keep only
    the year part so boxplots group ``3;01`` … ``3;11`` together as ``3``.
    """
    if age_raw is None or (isinstance(age_raw, float) and pd.isna(age_raw)):
        return ""
    if isinstance(age_raw, (int,)) and not isinstance(age_raw, bool):
        return str(int(age_raw))
    if isinstance(age_raw, float):
        try:
            return str(int(age_raw))
        except (TypeError, ValueError):
            pass
    s = _s(age_raw)
    if not s:
        return ""
    if ";" in s:
        y_part = s.split(";", 1)[0].strip().replace(",", ".")
        try:
            yf = float(y_part)
            if yf < 0:
                return s
            return str(int(yf))
        except (TypeError, ValueError):
            return s
    try:
        yf = float(s.replace(",", "."))
        return str(int(yf))
    except (TypeError, ValueError):
        return s


def load_rog_speeches_tsv(path: str | os.PathLike[str]) -> dict[str, dict[str, str]]:
    """
    Load ROG-style metadata TSV (ROG-Dialog ``ROG-Dia-meta-speeches.tsv`` or
    ROG-Art ``ROG-speeches.tsv``). Detects ``RECORDING-ID`` vs ``TEXT-ID`` as id.
    """
    path = Path(path)
    if not path.is_file():
        print(f"WARNING: metadata TSV not found: {path}", flush=True)
        return {}
    try:
        df = pd.read_csv(path, sep="\t")
    except Exception as e:
        print(f"WARNING: could not read metadata TSV {path}: {e}", flush=True)
        return {}

    df.columns = df.columns.str.strip()
    col_by_upper = {c.upper(): c for c in df.columns}

    def resolve(*candidates: str) -> str | None:
        for cand in candidates:
            key = cand.upper()
            if key in col_by_upper:
                return col_by_upper[key]
        return None

    c_rec = resolve("RECORDING-ID")
    c_text = resolve("TEXT-ID")
    if not c_rec and not c_text:
        print(
            "WARNING: TSV has neither RECORDING-ID nor TEXT-ID; no metadata loaded.",
            flush=True,
        )
        return {}

    # ROG-Dialog: RECORDING-ID matches RTTM stems (e.g. ROG-Dia-GSO-P0005). ROG-Art uses TEXT-ID
    # (Rog-Art-...) while RECORDING-ID holds *.wav names — prefer TEXT-ID when media-like ids appear.
    media_suffixes = (".wav", ".mp3", ".WAV", ".MP3")
    recording_is_media = False
    if c_rec:
        for _, row in df.iterrows():
            rv = _s(row.get(c_rec))
            if rv.endswith(media_suffixes):
                recording_is_media = True
                break
    if c_text and recording_is_media:
        id_key = c_text
    elif c_rec:
        id_key = c_rec
    else:
        id_key = c_text

    c_domain = resolve("DOMAIN")
    c_type = resolve("TYPE")
    c_qual = resolve("RECORDING QUALITY", "QUALITY")
    c_dev = resolve("RECORDING DEVICE", "DEVICE")
    c_title = resolve("TITLE")
    c_kw = resolve("KEYWORDS")

    def field(row: pd.Series, cname: str | None, default: str = "Unknown") -> str:
        if not cname:
            return default
        v = row.get(cname)
        t = _s(v)
        return t if t else default

    meta: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec_id = _s(row.get(id_key))
        if not rec_id:
            continue
        meta[rec_id] = {
            "Domain": field(row, c_domain),
            "Type": field(row, c_type),
            "Quality": field(row, c_qual),
            "Device": field(row, c_dev),
            "Title": field(row, c_title, default=""),
            "Keywords": field(row, c_kw, default=""),
        }
    return meta


def load_ccpcl_0demo_xlsx(path: str | os.PathLike[str]) -> dict[str, dict[str, str]]:
    """
    Load CCPCL participant table from ``0demo.xlsx`` (or a copy under docs/).

    ``primary_category`` is stored as ``Domain``: ``Age {years} / {Gender}`` where
    ``years`` is the integer year from chronological age (``years;months`` → ``years``).
    """
    path = Path(path)
    if not path.is_file():
        print(f"WARNING: CCPCL metadata xlsx not found: {path}", flush=True)
        return {}
    try:
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        print(f"WARNING: could not read CCPCL xlsx {path}: {e}", flush=True)
        return {}

    df.columns = df.columns.str.strip()
    # Expected TalkBank demo layout (see module docstring).
    id_candidates = ("Participant ID", "participant id", "ID", "Session ID")
    age_candidates = ("Chronological age", "Age", "Chronological Age")
    gender_candidates = ("Gender", "gender")

    def pick(*names: str) -> str | None:
        for n in names:
            if n in df.columns:
                return n
        return None

    c_id = pick(*id_candidates)
    if not c_id:
        print("WARNING: CCPCL xlsx: no participant id column found.", flush=True)
        return {}

    c_age = pick(*age_candidates)
    c_gender = pick(*gender_candidates)
    c_audio = pick("Audio")
    c_cha = pick("Transcript_CLAN", "Transcript", "CHA")

    meta: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec_id = _s(row.get(c_id))
        if not rec_id:
            continue
        raw_age = _s(row.get(c_age)) if c_age else ""
        age_years = _ccpcl_age_years_label(row.get(c_age)) if c_age else ""
        gender = _s(row.get(c_gender)) if c_gender else ""
        if age_years and gender:
            domain = f"Age {age_years} / {gender}"
        elif age_years:
            domain = f"Age {age_years}"
        elif gender:
            domain = gender
        else:
            domain = "N/A"
        bits = []
        if raw_age and ";" in raw_age:
            bits.append(f"chronological_age={raw_age}")
        if c_audio:
            bits.append(f"audio={_s(row.get(c_audio))}")
        if c_cha:
            bits.append(f"cha={_s(row.get(c_cha))}")
        meta[rec_id] = {
            "Domain": domain,
            "Type": "CHILDES-CCPCL",
            "Quality": "N/A",
            "Device": "N/A",
            "Title": "",
            "Keywords": "; ".join(bits),
        }
    return meta


def load_metadata_for_dataset(dataset: str, metadata_path: str | None) -> dict[str, dict[str, str]]:
    """Dispatch loader by ``--dataset`` value."""
    if not metadata_path:
        return {}
    ds = dataset.strip().lower().replace("-", "_")
    if ds in ("rog_dialog", "rog_art"):
        return load_rog_speeches_tsv(metadata_path)
    if ds in ("childes_ccpcl", "ccpcl"):
        return load_ccpcl_0demo_xlsx(metadata_path)
    print(f"WARNING: unknown dataset {dataset!r}; no metadata loaded.", flush=True)
    return {}


def default_report_artifacts(dataset: str) -> tuple[str, str]:
    """Returns (markdown_filename, report_title)."""
    ds = dataset.strip().lower().replace("-", "_")
    if ds == "rog_dialog":
        return "ROG_Dialog_Benchmark_Report.md", "ROG-Dialog Benchmark Report"
    if ds == "rog_art":
        return "ROG_Art_Benchmark_Report.md", "ROG-Art Benchmark Report"
    if ds in ("childes_ccpcl", "ccpcl"):
        return "CHILDES_CCPCL_Benchmark_Report.md", "CHILDES-CCPCL Benchmark Report"
    return "Diarization_Benchmark_Report.md", "Diarization Benchmark Report"
