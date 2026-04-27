"""
Diarisation Benchmark - Evaluation Scorer
==========================================
Project: diarisation-benchmark
Description: Quick CLI tool for evaluating speaker diarization model outputs
             against gold standard RTTM annotations. Calculates Diarization
             Error Rate (DER) and other metrics for the ROG-Dialog dataset.
             Supports dataset-specific errata rules via UEM.

Author: Tomaž Savodnik
Date: March 2026
"""
import argparse
import sys
import glob
import os
import pandas as pd
from pathlib import Path
from pyannote.core import Segment, Annotation, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate
from tabulate import tabulate
import warnings

from errata_merge import load_merged_errata

warnings.filterwarnings("ignore", category=UserWarning, module="pyannote.metrics.utils")

def load_rttm(file_path):
    annotations = {}
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            if parts[0].upper() != "SPEAKER":
                continue
            try:
                file_id = parts[1]
                start = float(parts[3])
                duration = float(parts[4])
            except (ValueError, IndexError):
                continue
            label = parts[7]

            if file_id not in annotations:
                annotations[file_id] = Annotation(uri=file_id)

            annotations[file_id][Segment(start, start + duration)] = label
    return annotations

def load_system_rttms(folder_path):
    all_files = glob.glob(os.path.join(folder_path, "*.rttm"))
    annotations = {}
    print(f"Loading {len(all_files)} system hypothesis files...")
    for file_path in all_files:
        annotations.update(load_rttm(file_path))
    return annotations

def main():
    parser = argparse.ArgumentParser(description="Calculate DER metrics.")
    parser.add_argument("--gold", required=True, help="Path to Gold Standard RTTM file")
    parser.add_argument("--system", required=True, help="Path to folder containing System RTTM files")
    parser.add_argument("--errata", default="DATASET_ERRATA.json", help="Path to manual errata JSON")
    parser.add_argument(
        "--no-auto-errata",
        action="store_true",
        help="Do not load AUTO_DATASET_ERRATA.json beside the gold RTTM (default: merge with manual).",
    )
    parser.add_argument("--collar", type=float, default=0.0, help="Collar (forgiveness) in seconds")
    parser.add_argument("--skip_overlap", action="store_true", help="Ignore overlapping speech")
    args = parser.parse_args()

    print("--- DIARIZATION BENCHMARK SCORING ---")
    
    manual_errata_path = args.errata if os.path.isfile(args.errata) else None
    errata_dict, errata_meta = load_merged_errata(
        args.gold, manual_errata_path, merge_auto=not args.no_auto_errata
    )
    if manual_errata_path:
        print(f"Loaded manual errata from {manual_errata_path}")
    ap = errata_meta.get("auto_path")
    if ap and os.path.isfile(ap) and not args.no_auto_errata:
        print(f"Merged auto errata from {ap}")
    elif not args.no_auto_errata and ap:
        print(f"(No auto errata file at {ap})")

    refs = load_rttm(args.gold)
    hyps = load_system_rttms(args.system)
    
    common_files = sorted(list(set(refs.keys()) & set(hyps.keys())))
    if not common_files:
        print("ERROR: No matching files found!")
        sys.exit(1)
        
    print(f"Evaluated Files: {len(common_files)}")

    metric = DiarizationErrorRate(collar=args.collar, skip_overlap=args.skip_overlap)
    
    global_total_ref = 0.0
    global_false_alarm = 0.0
    global_missed = 0.0
    global_conf = 0.0
    
    file_results = []
    
    print("\nCalculating DER...")
    for file_id in common_files:
        ref = refs[file_id]
        hyp = hyps[file_id]
        
        # UEM / merged errata (trim_start, trim_end); audio extent approximated by reference RTTM
        ref_tl = ref.get_timeline()
        ref_end = ref_tl.extent().end if not ref_tl.empty() else 0.0
        ed = errata_dict.get(file_id, {}) if isinstance(errata_dict.get(file_id), dict) else {}
        eval_start = 0.0
        ts = ed.get("trim_start")
        if ts is not None:
            try:
                eval_start = max(0.0, float(ts))
            except (TypeError, ValueError):
                eval_start = 0.0
        eval_end = float(ref_end)
        te = ed.get("trim_end")
        if te is not None:
            try:
                eval_end = min(eval_end, float(te))
            except (TypeError, ValueError):
                pass
        eval_start = max(0.0, min(eval_start, eval_end))

        uem = None
        full_window = eval_start <= 0 and eval_end >= ref_end - 1e-6
        if file_id in errata_dict and not full_window:
            uem = Timeline([Segment(eval_start, eval_end)])
            print(
                f"  -> Applied UEM to {file_id}: [{eval_start:.3f}s, {eval_end:.3f}s] "
                f"(ref extent end {ref_end:.3f}s)"
            )
        
        stats = metric(ref, hyp, detailed=True, uem=uem)
        
        total_speech = stats.get('total', 0.0)
        fa = stats.get('false alarm', 0.0)
        miss = stats.get('missed detection', 0.0)
        conf = stats.get('confusion', 0.0)
        
        global_total_ref += total_speech
        global_false_alarm += fa
        global_missed += miss
        global_conf += conf
        
        der_proc = (abs(stats.get('diarization error rate', 0.0)) * 100) if total_speech > 0 else 0.0
        
        errors = {"False Alarm": fa, "Missed": miss, "Confusion": conf}
        dominant_error = max(errors, key=errors.get)
        
        file_results.append({
            "File ID": file_id,
            "DER (%)": der_proc,
            "Confusion (%)": (conf / total_speech * 100) if total_speech > 0 else 0,
            "Missed (%)": (miss / total_speech * 100) if total_speech > 0 else 0,
            "False Alarm (%)": (fa / total_speech * 100) if total_speech > 0 else 0,
            "Total Speech (s)": total_speech,
            "Dominant Error": dominant_error
        })

    if global_total_ref > 0:
        global_der_val = (global_false_alarm + global_missed + global_conf) / global_total_ref
        global_der_proc = global_der_val * 100
        
        g_miss_proc = (global_missed / global_total_ref) * 100
        g_fa_proc = (global_false_alarm / global_total_ref) * 100
        g_conf_proc = (global_conf / global_total_ref) * 100
    else:
        global_der_proc = g_miss_proc = g_fa_proc = g_conf_proc = 0.0

    df = pd.DataFrame(file_results)
    
    print("\n" + "="*100)
    print(f"GLOBAL DER: {global_der_proc:.2f}% (Collar: {args.collar}s)")
    print("="*100)
    
    print("\nPer-File Results (Worst to Best):")
    print(tabulate(df.sort_values("DER (%)", ascending=False), headers="keys", tablefmt="simple", floatfmt=".2f", showindex=False))

    summary = [
        ["Total Duration (Reference)", f"{global_total_ref:.1f} s"],
        ["--------------------------", "-------"],
        ["Missed Detection", f"{g_miss_proc:.2f} %"],
        ["False Alarm", f"{g_fa_proc:.2f} %"],
        ["Speaker Confusion", f"{g_conf_proc:.2f} %"],
        ["--------------------------", "-------"],
        ["TOTAL DER", f"{global_der_proc:.2f} %"],
        ["--------------------------", "-------"],
        ["Parameter: Collar", f"{args.collar} s"],
        ["Parameter: Skip Overlap", str(args.skip_overlap)]
    ]
    print("\nGlobal Summary:")
    print(tabulate(summary, tablefmt="plain"))
    
    overlap_suffix = "_nooverlap" if args.skip_overlap else ""
    output_csv = f"evaluation_results_collar{args.collar}{overlap_suffix}.csv"
    df.to_csv(output_csv, index=False)
    print(f"\nFull results saved to {output_csv}")

if __name__ == "__main__":
    main()