import argparse
import os
from collections import defaultdict
from pathlib import Path


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

def parse_rttm(file_path: str):
    """
    Parses RTTM file into a structured dictionary.
    Structure: data[file_id] = {
        'total_duration': float,
        'segment_count': int,
        'speakers': set(),
        'segments': list of dicts
    }
    """
    stats = defaultdict(lambda: {
        'total_duration': 0.0, 
        'segment_count': 0, 
        'speakers': set(),
        'segments': []
    })
    
    global_speakers = set()
    
    parse_info = {
        "skipped_comment_or_blank": 0,
        "skipped_non_speaker": 0,
        "skipped_too_short": 0,
        "skipped_parse_error": 0,
    }

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                parse_info["skipped_comment_or_blank"] += 1
                continue

            parts = stripped.split()
            if not parts:
                parse_info["skipped_comment_or_blank"] += 1
                continue
            if parts[0] != "SPEAKER":
                parse_info["skipped_non_speaker"] += 1
                continue
            if len(parts) < 8:
                parse_info["skipped_too_short"] += 1
                continue

            # Format: SPEAKER file_id 1 start duration <NA> <NA> spk_id <NA> <NA>
            file_id = parts[1]
            try:
                start = float(parts[3])
                duration = float(parts[4])
            except ValueError:
                parse_info["skipped_parse_error"] += 1
                continue
            spk_id = parts[7]
            
            stats[file_id]['total_duration'] += duration
            stats[file_id]['segment_count'] += 1
            stats[file_id]['speakers'].add(spk_id)
            stats[file_id]['segments'].append({
                'start': start, 
                'end': start + duration, 
                'speaker': spk_id
            })
            global_speakers.add(spk_id)
            
    return stats, global_speakers, parse_info

def print_diff(label, val1, val2, is_float=False):
    diff = val1 - val2
    if is_float:
        return f"{val1:>10.2f} | {val2:>10.2f} | {diff:>+10.2f}"
    else:
        return f"{val1:>10} | {val2:>10} | {diff:>+10}"


def _kv_dict_from_comment_line(line: str) -> dict[str, str]:
    d: dict[str, str] = {}
    for k, v in parse_semicolon_kv_line(line):
        d[k] = v
    return d


def print_kv_diff(title: str, a: dict[str, str], b: dict[str, str]):
    print(f"\n--- {title} ---")
    keys = sorted(set(a.keys()) | set(b.keys()))
    if not keys:
        print("(no metadata found)")
        return
    for k in keys:
        in_a = k in a
        in_b = k in b
        if in_a and in_b:
            if a[k] == b[k]:
                print(f"  {k}={a[k]}")
            else:
                print(f"- {k}={a[k]}")
                print(f"+ {k}={b[k]}")
        elif in_a:
            print(f"- {k}={a[k]}")
        else:
            print(f"+ {k}={b[k]}")

def analyze_gaps(segments, threshold=0.5):
    """Counts gaps smaller than threshold for the same speaker."""
    # Group by speaker
    spk_segs = defaultdict(list)
    for s in segments:
        spk_segs[s['speaker']].append(s)
    
    short_gaps = 0
    for spk, items in spk_segs.items():
        items.sort(key=lambda x: x['start'])
        for i in range(len(items) - 1):
            gap = items[i+1]['start'] - items[i]['end']
            if 0 < gap < threshold:
                short_gaps += 1
    return short_gaps

def main():
    parser = argparse.ArgumentParser(description="Compare two RTTM files (Reference vs Hypothesis/Other Ref).")
    parser.add_argument("ref", help="Path to reference RTTM (File A)")
    parser.add_argument("hyp", help="Path to hypothesis/comparison RTTM (File B)")
    args = parser.parse_args()

    if not os.path.exists(args.ref) or not os.path.exists(args.hyp):
        print("Error: One or both files do not exist.")
        return

    print(f"--- RTTM COMPARISON TOOL ---")
    print(f"File A (Ref): {args.ref}")
    print(f"File B (Hyp): {args.hyp}")
    print("="*60)

    # 0. Optional metadata / provenance headers (leading comment lines)
    comments_a = read_leading_rttm_comments(args.ref, max_lines=2)
    comments_b = read_leading_rttm_comments(args.hyp, max_lines=2)

    meta_a = _kv_dict_from_comment_line(comments_a[0]) if len(comments_a) >= 1 else {}
    meta_b = _kv_dict_from_comment_line(comments_b[0]) if len(comments_b) >= 1 else {}

    trim_a = (
        _kv_dict_from_comment_line(comments_a[1])
        if len(comments_a) >= 2 and "trim_params" in comments_a[1]
        else {}
    )
    trim_b = (
        _kv_dict_from_comment_line(comments_b[1])
        if len(comments_b) >= 2 and "trim_params" in comments_b[1]
        else {}
    )

    print_kv_diff("METADATA (header line 1)", meta_a, meta_b)
    print_kv_diff("METADATA (trim_params line 2)", trim_a, trim_b)

    # 1. Load Data
    data_a, spk_a, parse_a = parse_rttm(args.ref)
    data_b, spk_b, parse_b = parse_rttm(args.hyp)

    if parse_a.get("skipped_parse_error", 0) or parse_b.get("skipped_parse_error", 0):
        print(
            "Warning: Some RTTM rows could not be parsed and were skipped "
            f"(A: {parse_a.get('skipped_parse_error', 0)}, "
            f"B: {parse_b.get('skipped_parse_error', 0)})."
        )

    def metric_line(name: str, a, b, is_float: bool = False) -> str:
        if is_float:
            da = float(a)
            db = float(b)
            dd = da - db
            return f"{name}: {da:.3f} -> {db:.3f} ({dd:+.3f})"
        ia = int(a)
        ib = int(b)
        return f"{name}: {ia} -> {ib} ({ia-ib:+d})"

    # 2. Global stats (diff-like)
    total_dur_a = sum(d["total_duration"] for d in data_a.values())
    total_dur_b = sum(d["total_duration"] for d in data_b.values())
    total_seg_a = sum(d["segment_count"] for d in data_a.values())
    total_seg_b = sum(d["segment_count"] for d in data_b.values())
    gaps_a = sum(analyze_gaps(d["segments"]) for d in data_a.values())
    gaps_b = sum(analyze_gaps(d["segments"]) for d in data_b.values())

    print("\n--- RTTM STATS (GLOBAL) ---")
    print(metric_line("TotalFiles", len(data_a), len(data_b)))
    print(metric_line("TotalSpeakers", len(spk_a), len(spk_b)))
    print(metric_line("TotalSegments", total_seg_a, total_seg_b))
    print(metric_line("TotalDuration_s", total_dur_a, total_dur_b, is_float=True))
    print(metric_line("ShortGaps_lt0.5s", gaps_a, gaps_b))

    # 3. Per-file stats hunks (only print diffs)
    all_files = set(data_a.keys()) | set(data_b.keys())
    print("\n--- RTTM STATS (PER-FILE DIFFS) ---")
    any_hunks = False
    for fid in sorted(all_files):
        in_a = fid in data_a
        in_b = fid in data_b
        if not in_a:
            any_hunks = True
            dur_b = data_b[fid]["total_duration"]
            seg_b = data_b[fid]["segment_count"]
            spk_b_cnt = len(data_b[fid]["speakers"])
            print(f"@@ {fid}")
            print("- (missing)")
            print(f"+ dur_s={dur_b:.3f} seg={seg_b} spk={spk_b_cnt}")
            continue
        if not in_b:
            any_hunks = True
            dur_a = data_a[fid]["total_duration"]
            seg_a = data_a[fid]["segment_count"]
            spk_a_cnt = len(data_a[fid]["speakers"])
            print(f"@@ {fid}")
            print(f"- dur_s={dur_a:.3f} seg={seg_a} spk={spk_a_cnt}")
            print("+ (missing)")
            continue

        dur_a = data_a[fid]["total_duration"]
        dur_b = data_b[fid]["total_duration"]
        seg_a = data_a[fid]["segment_count"]
        seg_b = data_b[fid]["segment_count"]
        spk_a_cnt = len(data_a[fid]["speakers"])
        spk_b_cnt = len(data_b[fid]["speakers"])

        if (abs(dur_a - dur_b) < 1e-9) and (seg_a == seg_b) and (spk_a_cnt == spk_b_cnt):
            continue

        any_hunks = True
        print(f"@@ {fid}")
        print(f"- dur_s={dur_a:.3f} seg={seg_a} spk={spk_a_cnt}")
        print(f"+ dur_s={dur_b:.3f} seg={seg_b} spk={spk_b_cnt}")

    if not any_hunks:
        print("(no per-file differences in duration/segments/speakers)")

if __name__ == "__main__":
    main()