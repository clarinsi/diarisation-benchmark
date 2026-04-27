"""
Diarisation Benchmark - Report Generator
=========================================
Project: diarisation-benchmark
Description: Generates comprehensive benchmark reports with visualizations for
             speaker diarization model evaluations. Calculates DER, Purity, and
             Coverage metrics across all models in the results directory. Supports
             dataset-specific errata rules via UEM (Universal Evaluation Maps) to
             handle transcription errors in the ROG-Dialog gold standard.

Author: Tomaž Savodnik
Date: March 2026
"""
import argparse
import os
import glob
import json
import re
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
from pyannote.core import Segment, Annotation, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate, DiarizationPurity, DiarizationCoverage, JaccardErrorRate
from pyannote.metrics.segmentation import SegmentationPrecision, SegmentationRecall
from tabulate import tabulate
import warnings

from errata_merge import load_merged_errata
from gold_rttm_provenance import format_gold_rttm_report_section

# Utišamo opozorila
warnings.filterwarnings("ignore")

# --- KONFIGURACIJA ---
COLLAR_SETTINGS = [0.0, 0.25]
SKIP_OVERLAP = False 

def fix_permissions(path, uid, gid):
    print(f"Fixing permissions for {path} -> {uid}:{gid}...", flush=True)
    try:
        if os.path.isfile(path):
            os.chown(path, uid, gid)
            return
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for d in dirs: os.chown(os.path.join(root, d), uid, gid)
            for f in files: os.chown(os.path.join(root, f), uid, gid)
    except Exception: pass

def normalize_speaker_label(label):
    """Združi SPEAKER_00 in speaker_0 v 'Speaker 0'."""
    m = re.match(r'(?i)^speaker[_\s]*(\d+)$', label)
    if m:
        return f"Speaker {int(m.group(1))}"
    return label

def load_rttm(file_path):
    annotations = {}
    if not os.path.exists(file_path): return {}
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 8 or parts[0].upper() != 'SPEAKER':
                continue
            try:
                file_id = parts[1]
                start = float(parts[3])
                duration = float(parts[4])
            except (ValueError, IndexError):
                continue
            label = normalize_speaker_label(parts[7])

            if file_id not in annotations:
                annotations[file_id] = Annotation(uri=file_id)
            annotations[file_id][Segment(start, start + duration)] = label
    return annotations

def load_metadata(speeches_path):
    try:
        df = pd.read_csv(speeches_path, sep='\t')
        df.columns = df.columns.str.strip()
        meta = {}
        for _, row in df.iterrows():
            rec_id = str(row['RECORDING-ID'])
            meta[rec_id] = {
                'Domain': row.get('DOMAIN', 'Unknown'),
                'Type': row.get('TYPE', 'Unknown'),
                'Quality': row.get('RECORDING QUALITY', 'Unknown'),
                'Device': row.get('RECORDING DEVICE', 'Unknown'),
                'Title': row.get('TITLE', ''),
                'Keywords': row.get('KEYWORDS', '')
            }
        return meta
    except Exception as e:
        print(f"WARNING: Could not load metadata TSV: {e}", flush=True)
        return {}

def get_hardware_stats(model_dir):
    json_path = os.path.join(model_dir, "benchmark_metadata.json")
    if not os.path.exists(json_path): return None, {}
    try:
        with open(json_path, 'r') as f: data = json.load(f)
        
        global_stats = {
            'model_name': data.get('model_name', os.path.basename(model_dir)),
            'gpu_name': data.get('run_info', {}).get('gpu_name', 'Unknown'),
            'overall_rtf': data.get('timings', {}).get('overall_rtf', 0.0),
            'max_vram': data.get('timings', {}).get('max_vram_peak_mb', 0.0),
            'files_processed': len(data.get('files', []))
        }
        file_stats = {}
        for f_data in data.get('files', []):
            fname = f_data.get('filename')
            if fname:
                file_stats[fname] = {
                    'rtf': f_data.get('rtf', 0.0),
                    'vram': f_data.get('peak_vram_mb', 0.0),
                    'duration': f_data.get('audio_duration_s', 0.0),
                    'error': f_data.get('error', None)
                }
        return global_stats, file_stats
    except: return None, {}

def evaluate_model_comprehensive(model_dir, gold_annotations, collar, hw_file_stats, errata_dict, boundary_tolerance=0.250):
    rttm_files = glob.glob(os.path.join(model_dir, "*.rttm"))
    system_annotations = {}
    for f in rttm_files:
        fname = Path(f).stem
        system_annotations[fname] = load_rttm(f).get(fname, Annotation(uri=fname))

    metric_der = DiarizationErrorRate(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_jer = JaccardErrorRate(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_purity = DiarizationPurity(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_coverage = DiarizationCoverage(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_b_prec = SegmentationPrecision(tolerance=boundary_tolerance)
    metric_b_rec = SegmentationRecall(tolerance=boundary_tolerance)
    
    file_results = []
    acc = {
        'total': 0, 'error': 0,
        'p_num': 0, 'p_den': 0,
        'c_num': 0, 'c_den': 0,
        'jer_num': 0, 'jer_den': 0,
        'bp_num': 0, 'br_num': 0, 'b_den': 0,
    }
    acc_ok = {
        'total': 0, 'error': 0,
        'p_num': 0, 'p_den': 0,
        'c_num': 0, 'c_den': 0,
        'jer_num': 0, 'jer_den': 0,
        'bp_num': 0, 'br_num': 0, 'b_den': 0,
    }
    
    for fid, ref in gold_annotations.items():
        hw = hw_file_stats.get(fid, {})
        res_entry = {
            'File ID': fid, 'Status': 'OK', 
            'RTF': hw.get('rtf', None), 'VRAM': hw.get('vram', None)
        }

        ref_tl = ref.get_timeline()
        ref_end = ref_tl.extent().end if not ref_tl.empty() else 0.0
        audio_dur = hw.get('duration') or ref_end

        ed = errata_dict.get(fid, {}) if isinstance(errata_dict.get(fid), dict) else {}
        eval_start = 0.0
        ts = ed.get("trim_start")
        if ts is not None:
            try:
                eval_start = max(0.0, float(ts))
            except (TypeError, ValueError):
                eval_start = 0.0
        eval_end = float(audio_dur)
        te = ed.get("trim_end")
        if te is not None:
            try:
                eval_end = min(eval_end, float(te))
            except (TypeError, ValueError):
                pass
        eval_start = max(0.0, min(eval_start, eval_end))
        uem = Timeline([Segment(eval_start, eval_end)])

        has_output = fid in system_annotations and len(system_annotations[fid]) > 0
        if hw.get('error'): has_output = False

        if has_output:
            hyp = system_annotations[fid]
            stats = metric_der(ref, hyp, detailed=True, uem=uem)
            jer = metric_jer(ref, hyp, uem=uem)
            purity = metric_purity(ref, hyp, uem=uem)
            coverage = metric_coverage(ref, hyp, uem=uem)

            b_p = metric_b_prec(ref, hyp, uem=uem)
            b_r = metric_b_rec(ref, hyp, uem=uem)
            b_f1 = (2 * b_p * b_r / (b_p + b_r)) if (b_p + b_r) > 0 else 0.0
            
            total = stats.get('total', 0.0)
            miss = stats.get('missed detection', 0.0)
            fa = stats.get('false alarm', 0.0)
            conf = stats.get('confusion', 0.0)
            
            acc['total'] += total
            acc['error'] += (miss + fa + conf)
            acc['jer_num'] += jer * total
            acc['jer_den'] += total

            acc['bp_num'] += b_p * total
            acc['br_num'] += b_r * total
            acc['b_den'] += total

            acc_ok['total'] += total
            acc_ok['error'] += (miss + fa + conf)
            acc_ok['jer_num'] += jer * total
            acc_ok['jer_den'] += total
            acc_ok['bp_num'] += b_p * total
            acc_ok['br_num'] += b_r * total
            acc_ok['b_den'] += total
            
            hyp_eval = hyp.crop(uem)
            ref_eval = ref.crop(uem)
            
            hyp_dur = hyp_eval.get_timeline().duration()
            ref_dur = ref_eval.get_timeline().duration()
            
            acc['p_num'] += purity * hyp_dur; acc['p_den'] += hyp_dur
            acc['c_num'] += coverage * ref_dur; acc['c_den'] += ref_dur

            acc_ok['p_num'] += purity * hyp_dur; acc_ok['p_den'] += hyp_dur
            acc_ok['c_num'] += coverage * ref_dur; acc_ok['c_den'] += ref_dur

            res_entry.update({
                'DER': (stats.get('diarization error rate', 0.0)) * 100 if total > 0 else 0.0,
                'JER': jer * 100,
                'Miss': (miss / total * 100) if total > 0 else 0.0,
                'FA': (fa / total * 100) if total > 0 else 0.0,
                'Conf': (conf / total * 100) if total > 0 else 0.0,
                'B-P': b_p * 100,
                'B-R': b_r * 100,
                'B-F1': b_f1 * 100,
                'Purity': purity * 100,
                'Cover': coverage * 100,
                'Total Speech': total
            })
        else:
            ref_eval = ref.crop(uem)
            ref_speech_duration = sum(s.duration for s, _ in ref_eval.itertracks(yield_label=False))
            
            acc['total'] += ref_speech_duration
            acc['error'] += ref_speech_duration 
            acc['c_den'] += ref_speech_duration
            acc['jer_num'] += 1.0 * ref_speech_duration
            acc['jer_den'] += ref_speech_duration
            
            res_entry.update({
                'Status': 'FAIL', 'DER': 100.0, 'Miss': 100.0, 'FA': 0.0, 'Conf': 0.0,
                'JER': 100.0, 'B-P': 0.0, 'B-R': 0.0, 'B-F1': 0.0,
                'Purity': 0.0, 'Cover': 0.0, 'Total Speech': ref_speech_duration
            })
            if hw.get('error'): res_entry['Status'] = "OOM/ERR"

        file_results.append(res_entry)

    g_der = (acc_ok['error'] / acc_ok['total'] * 100) if acc_ok['total'] > 0 else float("nan")
    g_pur = (acc_ok['p_num'] / acc_ok['p_den'] * 100) if acc_ok['p_den'] > 0 else float("nan")
    g_cov = (acc_ok['c_num'] / acc_ok['c_den'] * 100) if acc_ok['c_den'] > 0 else float("nan")
    g_jer = (acc_ok['jer_num'] / acc_ok['jer_den'] * 100) if acc_ok['jer_den'] > 0 else float("nan")
    g_bp = (acc_ok['bp_num'] / acc_ok['b_den'] * 100) if acc_ok['b_den'] > 0 else float("nan")
    g_br = (acc_ok['br_num'] / acc_ok['b_den'] * 100) if acc_ok['b_den'] > 0 else float("nan")
    g_bf1 = (
        (2 * g_bp * g_br / (g_bp + g_br))
        if (g_bp + g_br) > 0
        else float("nan")
    )
    
    return {
        'der': g_der,
        'jer': g_jer,
        'b_p': g_bp,
        'b_r': g_br,
        'b_f1': g_bf1,
        'purity': g_pur,
        'coverage': g_cov,
        'files': file_results
    }

def find_extreme_segments(
    ref,
    systems_dict,
    window_duration=60.0,
    step=30.0,
    min_speech=15.0,
    eval_boundary=None,
    eval_start=0.0,
):
    """
    Skenira posnetek z drsečim oknom in poišče 60s izsek z najboljšim in najslabšim povprečnim DER.
    """
    t0 = float(eval_start or 0.0)
    max_time = ref.get_timeline().extent().end if not ref.get_timeline().empty() else 0.0
    if eval_boundary and eval_boundary < max_time:
        max_time = eval_boundary

    max_start = max_time - window_duration
    if max_start <= t0:
        return None, None
        
    best_seg = None
    worst_seg = None
    min_der = float('inf')
    max_der = -1.0
    
    # Validiramo sisteme
    val_sys = [hyp for hyp in systems_dict.values() if hyp and not hyp.get_timeline().empty()]
    if not val_sys: return None, None
    
    for start in np.arange(t0, max_start + 1, step):
        seg = Segment(start, start + window_duration)
        uem = Timeline([seg])
        
        # Preverimo, če je v tem oknu sploh dovolj govora
        ref_crop = ref.crop(uem)
        speech_dur = sum(s.duration for s, _ in ref_crop.itertracks(yield_label=False))
        
        if speech_dur < min_speech:
            continue
            
        total_der = 0.0
        for hyp in val_sys:
            # Izračun on-the-fly (hitra instanciacija)
            metric = DiarizationErrorRate(skip_overlap=SKIP_OVERLAP)
            stats = metric(ref, hyp, detailed=True, uem=uem)
            if stats.get('total', 0) > 0:
                der = stats['diarization error rate'] * 100
            else:
                der = 0.0
            total_der += der
        
        avg_der = total_der / len(val_sys)
        
        if avg_der < min_der:
            min_der = avg_der
            best_seg = seg
        if avg_der > max_der:
            max_der = avg_der
            worst_seg = seg
            
    return best_seg, worst_seg

def plot_timeline(
    gold_annot,
    system_annots_dict,
    file_id,
    output_dir,
    eval_boundary=None,
    eval_start=None,
    crop_segment=None,
    title_prefix="Timeline Analysis",
    suffix="",
):
    """
    Risanje gantograma. Zna izrisati celoto ali 'zoomiran' izsek (crop_segment).
    Barve ostanejo dosledne ne glede na crop, ker se izračunajo na celotni datoteki.
    """
    valid_systems = {k: v for k, v in system_annots_dict.items() if v}
    if not valid_systems: return
    
    # 1. OPTIMAL MAPPING NA CELOTNI DATOTEKI (Za dosledne barve)
    metric = DiarizationErrorRate(skip_overlap=SKIP_OVERLAP)
    ref_end_full = gold_annot.get_timeline().extent().end if not gold_annot.get_timeline().empty() else 0.0
    es = float(eval_start) if eval_start is not None else 0.0
    eb = float(eval_boundary) if eval_boundary is not None else ref_end_full
    eb = max(es, eb)
    uem_full = Timeline([Segment(es, eb)]) if (eval_boundary is not None or eval_start is not None) else None
    
    mapped_systems = {}
    all_speakers = set(gold_annot.labels())
    
    for model_name, hyp in valid_systems.items():
        mapping = metric.optimal_mapping(gold_annot, hyp, uem=uem_full)
        mapped_hyp = Annotation(uri=hyp.uri)
        for seg, trk, lbl in hyp.itertracks(yield_label=True):
            new_lbl = mapping.get(lbl, f"{lbl} (unmapped)")
            mapped_hyp[seg, trk] = new_lbl
            all_speakers.add(new_lbl)
        mapped_systems[model_name] = mapped_hyp

    all_speakers = sorted(list(all_speakers))
    
    # 2. DEFINICIJA BARV
    if len(all_speakers) <= 9:
        palette = sns.color_palette("Set1", n_colors=len(all_speakers))
    else:
        palette = sns.color_palette("tab20", n_colors=max(20, len(all_speakers)))
    spk_color_map = dict(zip(all_speakers, palette))
    
    # 3. CROPPING (Če želimo prikazati le izsek)
    if crop_segment:
        gold_to_plot = gold_annot.crop(crop_segment)
        sys_to_plot = {k: v.crop(crop_segment) for k, v in mapped_systems.items()}
        min_x = crop_segment.start
        max_x = crop_segment.end
    else:
        gold_to_plot = gold_annot
        sys_to_plot = mapped_systems
        min_x = 0
        max_x = gold_annot.get_timeline().extent().end if not gold_annot.get_timeline().empty() else 0
        for hyp in mapped_systems.values():
            if not hyp.get_timeline().empty():
                max_x = max(max_x, hyp.get_timeline().extent().end)
                
    # 4. IZRIS
    plt.figure(figsize=(14, max(4, len(valid_systems)*0.8 + 2)))
    y_pos = 0
    y_ticks, y_tick_labels = [], []
    
    # Gold Standard
    for seg, _, lbl in gold_to_plot.itertracks(yield_label=True):
        plt.broken_barh([(seg.start, seg.duration)], (y_pos, 0.6), facecolors=spk_color_map.get(lbl, 'gray'))
    y_ticks.append(y_pos + 0.3); y_tick_labels.append("GOLD")
    y_pos -= 1.0
    
    # Modeli
    for model_name in sorted(sys_to_plot.keys()):
        hyp = sys_to_plot[model_name]
        for seg, _, lbl in hyp.itertracks(yield_label=True):
            color = spk_color_map.get(lbl, 'gray')
            plt.broken_barh([(seg.start, seg.duration)], (y_pos, 0.6), facecolors=color)
        y_ticks.append(y_pos + 0.3); y_tick_labels.append(model_name)
        y_pos -= 1.0
        
    # Ignored leading / trailing regions (UEM outside [eval_start, eval_boundary])
    if es > 0 and not crop_segment:
        if min_x <= es <= max_x:
            plt.axvline(x=es, color='red', linestyle='--', linewidth=2)
            plt.axvspan(min_x, es, color='gray', alpha=0.2)
            plt.text(es - (max_x - min_x) * 0.02, 0.5, "IGNORED", color='red', weight='bold', rotation=90, ha='right')

    # Narišemo mejo evalvacije, če je vidna v trenutnem oknu
    if eval_boundary and min_x <= eval_boundary <= max_x and not crop_segment:
        plt.axvline(x=eval_boundary, color='red', linestyle='--', linewidth=2, label='Eval Boundary')
        plt.axvspan(eval_boundary, max_x + 10, color='gray', alpha=0.2)
        plt.text(eval_boundary + 5, 0.5, "IGNORED IN EVAL", color='red', weight='bold', rotation=90)
        
    # Dinamične meje X osi
    if crop_segment:
        plt.xlim(min_x, max_x)
    else:
        plt.xlim(0, max(max_x, eval_boundary if eval_boundary else 0) + 10)
        
    plt.xlabel("Time (s)")
    plt.yticks(y_ticks, y_tick_labels)
    
    time_str = f" [{min_x:.1f}s - {max_x:.1f}s]" if crop_segment else ""
    plt.title(f"{title_prefix}: {file_id}{time_str}")
    plt.grid(True, axis='x', linestyle='--', alpha=0.5)
    
    # Zmanjšamo legendo samo na tiste, ki so DEJANSKO vidni v tem oknu
    visible_speakers = set(gold_to_plot.labels())
    for hyp in sys_to_plot.values():
        visible_speakers.update(hyp.labels())
        
    patches = [mpatches.Patch(color=spk_color_map[s], label=s) for s in sorted(list(visible_speakers))[:20]]
    if (es > 0 and min_x <= es <= max_x and not crop_segment) or (
        eval_boundary and min_x <= eval_boundary <= max_x and not crop_segment
    ):
        patches.append(mpatches.Patch(color='gray', alpha=0.2, label='Ignored region (UEM)'))
        
    plt.legend(handles=patches, bbox_to_anchor=(1.01, 1), loc='upper left')
    plt.tight_layout(rect=[0, 0, 0.9, 1])
    plt.savefig(os.path.join(output_dir, f"timeline_{file_id}{suffix}.png"), dpi=150, bbox_inches='tight')
    plt.close()

def fmt_rtf(r):
    try:
        val = float(r)
        if 0 < val < 0.01: return "< 0.01"
        return f"{val:.2f}"
    except: return r

def fmt_vram(v):
    try:
        val = float(v)
        if val == 0: return "0.0"
        return f"{val/1024:.1f}"
    except: return v

def highlight_best(df, min_cols=[], max_cols=[], formatters={}):
    """Formats table with bold best values based on formatters."""
    df_out = df.copy()
    for col in df.columns:
        if col not in min_cols and col not in max_cols:
            if col in formatters:
                df_out[col] = df[col].apply(lambda x: formatters[col](x) if pd.notna(x) else x)
            continue
            
        vals = pd.to_numeric(df[col], errors='coerce')
        best = vals.min() if col in min_cols else vals.max()
        formatter = formatters.get(col, lambda x: f"{float(x):.2f}")
        
        def apply_fmt(x):
            try:
                val = float(x)
                fmt_val = formatter(val)
                return f"**{fmt_val}**" if val == best else fmt_val
            except: return x
        df_out[col] = df[col].apply(apply_fmt)
    return df_out

def snap_to_collar_settings(requested, settings=COLLAR_SETTINGS):
    """Pick nearest collar from settings (float-safe)."""
    return min(settings, key=lambda c: abs(float(c) - float(requested)))

def collect_models_with_ok_status(deep_dive_data, domain_collar):
    names = set()
    for _, per in deep_dive_data.items():
        md = per.get(domain_collar, {})
        for m_name, st in md.items():
            if st.get('Status') == 'OK':
                names.add(m_name)
    return sorted(names)

def build_domain_metric_rows(deep_dive_data, meta_dict, domain_collar, metric_col):
    rows = []
    for fid, per in deep_dive_data.items():
        md = per.get(domain_collar, {})
        domain = meta_dict.get(fid, {}).get('Domain', 'N/A')
        for m_name, stats in md.items():
            if stats.get('Status') == 'OK' and metric_col in stats:
                rows.append({'Domain': domain, 'Model': m_name, metric_col: stats[metric_col]})
    return rows

def format_domain_pivot_table(pivot_renamed, letter_cols, maximize=False):
    """Bold best model per domain row. `pivot_renamed` has Domain + letter columns + AVG."""
    out = pivot_renamed.copy()
    for idx, row in out.iterrows():
        vals = pd.to_numeric(row[letter_cols], errors='coerce')
        finite = vals[np.isfinite(vals)]
        if finite.empty:
            continue
        best = float(finite.max() if maximize else finite.min())
        for c in letter_cols:
            try:
                v = float(row[c])
                if np.isfinite(v) and v == best:
                    out.at[idx, c] = f"**{v:.2f}**"
                elif np.isfinite(v):
                    out.at[idx, c] = f"{v:.2f}"
            except (TypeError, ValueError):
                pass
        try:
            out.at[idx, "AVG"] = f"{float(row['AVG']):.2f}"
        except (TypeError, ValueError):
            pass
    return tabulate(out, headers="keys", tablefmt="github", showindex=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--metadata", help="Path to TSV")
    parser.add_argument("--errata", default="DATASET_ERRATA.json")
    parser.add_argument(
        "--no_auto_errata",
        action="store_true",
        help="Do not load AUTO_DATASET_ERRATA.json beside the gold RTTM (default: merge auto + manual).",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--boundary_tolerance", type=float, default=0.250, help="Boundary tolerance (seconds) for segmentation precision/recall (default: 0.250)")
    parser.add_argument(
        "--analysis_collar",
        type=float,
        default=0.25,
        help="Collar (seconds) used for domain-level boxplots and domain comparison tables; snapped to nearest value in COLLAR_SETTINGS (default: 0.25)",
    )
    args = parser.parse_args()

    domain_collar = snap_to_collar_settings(args.analysis_collar)

    os.makedirs(args.output, exist_ok=True)
    gold_annots = load_rttm(args.gold)
    meta_dict = load_metadata(args.metadata) if args.metadata else {}

    manual_errata_path = args.errata if os.path.isfile(args.errata) else None
    errata_dict, errata_meta = load_merged_errata(
        args.gold, manual_errata_path, merge_auto=not args.no_auto_errata
    )

    model_dirs = [f.path for f in os.scandir(args.results_dir) if f.is_dir()]

    summary_data = []
    deep_dive_data = {fid: {c: {} for c in COLLAR_SETTINGS} for fid in gold_annots.keys()}
    model_links = {}

    print(f"Processing {len(model_dirs)} models...", flush=True)

    for model_dir in model_dirs:
        hw_global, hw_per_file = get_hardware_stats(model_dir)
        if not hw_global: continue
        
        short_name = os.path.basename(model_dir)
        display_name = short_name.replace('_', ' ').replace('-', ' ')
        model_links[display_name] = hw_global['model_name']

        for collar in COLLAR_SETTINGS:
            res = evaluate_model_comprehensive(
                model_dir,
                gold_annots,
                collar,
                hw_per_file,
                errata_dict,
                boundary_tolerance=args.boundary_tolerance,
            )
            
            ok_count = sum(1 for f in res['files'] if f['Status'] == 'OK')
            summary_data.append({
                "Model": display_name, "Collar": collar,
                "DER": res['der'], "JER": res['jer'],
                "B-P": res['b_p'], "B-R": res['b_r'], "B-F1": res['b_f1'],
                "Purity": res['purity'], "Cover": res['coverage'],
                "Miss": sum(f.get('Miss', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "FA": sum(f.get('FA', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "Conf": sum(f.get('Conf', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "RTF": hw_global['overall_rtf'], "VRAM": hw_global['max_vram'],
                "Completed": f"{ok_count}/{len(gold_annots)}"
            })

            for fstat in res['files']:
                deep_dive_data[fstat['File ID']][collar][display_name] = fstat

    df_sum = pd.DataFrame(summary_data)

    print("Generating plots...", flush=True)
    sns.set_theme(style="whitegrid")
    
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="DER", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on DER")
    plt.ylabel("DER (%)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_der_comparison.png"))
    plt.close()

    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="JER", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on JER")
    plt.ylabel("JER (%)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_jer_comparison.png"))
    plt.close()

    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="B-F1", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on Boundary F1")
    plt.ylabel("Boundary F1 (%)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_boundary_f1_comparison.png"))
    plt.close()

    m_names = collect_models_with_ok_status(deep_dive_data, domain_collar)
    col_map = {m: chr(65 + i) for i, m in enumerate(m_names)}
    letter_cols = [col_map[m] for m in m_names]
    domain_legend_lines = [f"* **{col_map[m]}**: {m}" for m in m_names]
    domain_legend_md = "\n".join(domain_legend_lines) if domain_legend_lines else ""

    domain_tables = {"DER": "", "JER": "", "B-F1": ""}
    domain_plot_files = {}
    domain_metric_specs = [
        ("DER", "DER", "plot_domain_analysis.png", False),
        ("JER", "JER", "plot_domain_analysis_jer.png", False),
        ("B-F1", "Boundary F1", "plot_domain_analysis_bf1.png", True),
    ]

    if m_names:
        for metric_col, plot_label, plot_fname, maximize in domain_metric_specs:
            rows = build_domain_metric_rows(deep_dive_data, meta_dict, domain_collar, metric_col)
            if not rows:
                continue
            domain_plot_files[metric_col] = plot_fname
            df_m = pd.DataFrame(rows)
            plt.figure(figsize=(14, 6))
            sns.boxplot(data=df_m, x="Domain", y=metric_col, hue="Model")
            plt.title(f"{plot_label} distribution by domain (collar {domain_collar}s)")
            plt.ylabel(f"{metric_col} (%)" if metric_col != "B-F1" else "Boundary F1 (%)")
            plt.xticks(rotation=45, ha='right')
            plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', borderaxespad=0.)
            plt.tight_layout()
            plt.savefig(os.path.join(args.output, plot_fname), bbox_inches='tight')
            plt.close()

            pivot_dom = df_m.pivot_table(index="Domain", columns="Model", values=metric_col, aggfunc="mean")
            pivot_dom = pivot_dom.reindex(columns=m_names)
            pivot_dom["AVG"] = pivot_dom.mean(axis=1, skipna=True)
            pivot_named = pivot_dom.rename(columns=col_map).reset_index()
            domain_tables[metric_col] = format_domain_pivot_table(
                pivot_named, letter_cols, maximize=maximize
            )

    print("Writing report...", flush=True)
    formatters = {
        "RTF": fmt_rtf,
        "VRAM": fmt_vram,
        "DER": lambda x: f"{x:.2f}",
        "JER": lambda x: f"{x:.2f}",
        "Miss": lambda x: f"{x:.2f}",
        "FA": lambda x: f"{x:.2f}",
        "Conf": lambda x: f"{x:.2f}",
        "B-P": lambda x: f"{x:.2f}",
        "B-R": lambda x: f"{x:.2f}",
        "B-F1": lambda x: f"{x:.2f}",
        "Purity": lambda x: f"{x:.2f}",
        "Cover": lambda x: f"{x:.2f}",
        "Pur": lambda x: f"{x:.2f}",
        "Cov": lambda x: f"{x:.2f}",
    }

    with open(os.path.join(args.output, "ROG_Dia_Benchmark_Report.md"), "w") as f:
        f.write(f"# ROG-Dia Benchmark Report\n\n**Date:** {pd.Timestamp.now().date()}\n\n")
        f.write(format_gold_rttm_report_section(args.gold, errata_meta))

        f.write("## 1. Evaluated Models\n")
        for disp_name, full_name in sorted(model_links.items()):
            f.write(f"* **{disp_name}** (`{full_name}`) - [HuggingFace](https://huggingface.co/{full_name})\n")
        f.write("\n")

        f.write("## 2. Executive Summary\n\n")
        df_lead = df_sum[df_sum["Collar"] == 0.25].copy()
        df_lead = df_lead.rename(columns={"VRAM": "VRAM (GB)"})
        formatters["VRAM (GB)"] = fmt_vram
        
        df_lead = df_lead.sort_values("DER")
        df_lead = highlight_best(
            df_lead,
            min_cols=["DER", "JER", "Miss", "FA", "Conf", "RTF", "VRAM (GB)"],
            max_cols=["B-P", "B-R", "B-F1", "Purity", "Cover"],
            formatters=formatters,
        )
        
        f.write(tabulate(df_lead, headers="keys", tablefmt="github", showindex=False))
        f.write(
            "\n\n> **Note on aggregation:** Headline DER/JER/Boundary/Purity/Coverage are pooled "
            "only over recordings with per-file `Status == OK` (the numerator in the `Completed` column). "
            "Miss/FA/Conf are also averaged over the same completed recordings. Recordings with missing/failed "
            "outputs are shown in the deep dive tables but are not included in these headline aggregates.\n\n"
        )
        f.write("### Terminology & Methodology\n")
        f.write("* **DER (Diarization Error Rate):** Primary metric. Lower is better. Sum of Missed, False Alarm, and Confusion rates.\n")
        f.write("* **JER (Jaccard Error Rate):** Speaker-balanced diarization error. Lower is better.\n")
        f.write("* **Miss (%):** Speech present in Gold Standard but missed by the model.\n")
        f.write("* **FA (False Alarm %):** Model predicted speech where Gold Standard is silent.\n")
        f.write("* **Conf (Confusion %):** Speech correctly detected but assigned to the wrong speaker.\n")
        f.write(f"* **Boundary P/R/F1 (%):** Segmentation boundary precision/recall/F1 using tolerance {args.boundary_tolerance:.3f}s.\n")
        f.write("* **Purity (%):** Evaluates cluster purity. High purity = when a model identifies a speaker, it is consistently the same person.\n")
        f.write("* **Cover (Coverage %):** Evaluates how much of the original speaker's speech was captured under a single hypothesis cluster.\n")
        f.write("* **RTF (Real Time Factor):** Processing time divided by audio length. e.g., `< 0.01` means exceptionally fast processing.\n")
        f.write("* **VRAM (GB):** Peak GPU memory utilized. `0.0 GB` indicates an API/Cloud-based model.\n\n")

        if errata_dict:
            f.write("## 3. Dataset Errata (Corrections Applied)\n")
            f.write(
                "Corrections applied via Universal Evaluation Maps (UEM). See **§0** for full "
                "manual vs auto errata tables and merged bounds.\n\n"
            )
            for fid, err in errata_dict.items():
                ts = err.get("trim_start")
                te = err.get("trim_end")
                win = []
                if ts is not None:
                    win.append(f"from **{ts}**s")
                if te is not None:
                    win.append(f"to **{te}**s")
                w = " ".join(win) if win else "(no window change)"
                f.write(f"* **`{fid}`**: {w}. *{err.get('reason', 'N/A')}*\n")
            f.write("\n")

        f.write("## 4. Visual & Domain Analysis\n")
        f.write(
            "Bar charts compare models across **all** configured collars; domain boxplots and domain tables use a single evaluation collar.\n\n"
        )
        if float(domain_collar) != float(args.analysis_collar):
            f.write(
                f"* **Domain analysis collar:** `{domain_collar}`s (requested `--analysis_collar {args.analysis_collar}`; snapped to nearest value in `{list(COLLAR_SETTINGS)}`).\n\n"
            )
        else:
            f.write(f"* **Domain analysis collar:** `{domain_collar}`s.\n\n")

        f.write("![DER comparison by collar](plot_der_comparison.png)\n\n")
        f.write("![JER comparison by collar](plot_jer_comparison.png)\n\n")
        f.write("![Boundary F1 comparison by collar](plot_boundary_f1_comparison.png)\n\n")

        if m_names:
            if "DER" in domain_plot_files:
                f.write(
                    f"![DER distribution by domain (collar {domain_collar}s)]({domain_plot_files['DER']})\n\n"
                )
            if "JER" in domain_plot_files:
                f.write(
                    f"![JER distribution by domain (collar {domain_collar}s)]({domain_plot_files['JER']})\n\n"
                )
            if "B-F1" in domain_plot_files:
                f.write(
                    f"![Boundary F1 distribution by domain (collar {domain_collar}s)]({domain_plot_files['B-F1']})\n\n"
                )

            if domain_tables.get("DER"):
                f.write("### Domain Comparison (DER %)\n")
                f.write(
                    f"Average DER per domain at collar `{domain_collar}`s. **Bold** highlights the best (lowest) model per domain.\n\n"
                )
                f.write(domain_tables["DER"])
                f.write("\n\n")
            if domain_tables.get("JER"):
                f.write("### Domain Comparison (JER %)\n")
                f.write(
                    f"Average JER per domain at collar `{domain_collar}`s. **Bold** highlights the best (lowest) model per domain.\n\n"
                )
                f.write(domain_tables["JER"])
                f.write("\n\n")
            if domain_tables.get("B-F1"):
                f.write("### Domain Comparison (Boundary F1 %)\n")
                f.write(
                    f"Average boundary F1 per domain at collar `{domain_collar}`s (boundary tolerance {args.boundary_tolerance:.3f}s). **Bold** highlights the best (highest) model per domain.\n\n"
                )
                f.write(domain_tables["B-F1"])
                f.write("\n\n")

            if domain_legend_md:
                f.write("### Domain comparison model legend (shared)\n")
                f.write(domain_legend_md)
                f.write("\n\n")
        else:
            f.write(
                "*Domain distribution plots and domain comparison tables are omitted: no models had OK per-file outputs at the selected domain-analysis collar.*\n\n"
            )

        f.write("## 5. Deep Dive: File-by-File Analysis\n")
        f.write("Detailed breakdown for every file. *For metric definitions, see Executive Summary.*\n\n")
        
        for fid in sorted(deep_dive_data.keys()):
            meta = meta_dict.get(fid, {})
            f.write(f"### File: {fid}\n\n")
            f.write(f"**Domain:** {meta.get('Domain', '-')} | **Quality:** {meta.get('Quality', '-')} | **Device:** {meta.get('Device', '-')}\n\n")
            if meta.get('Title'): f.write(f"> *{meta.get('Title')}*\n\n")
            
            if fid in errata_dict:
                edn = errata_dict[fid]
                ts = edn.get("trim_start")
                te = edn.get("trim_end")
                bits = []
                if ts is not None:
                    bits.append(f"start **{ts}**s")
                if te is not None:
                    bits.append(f"end **{te}**s")
                f.write(f"> **ERRATA (UEM):** " + ", ".join(bits) + "\n\n")

            # --- Full Timeline ---
            file_annots = {}
            for m_dir in model_dirs:
                short = os.path.basename(m_dir)
                disp_n = short.replace('_', ' ').replace('-', ' ')
                rttm = os.path.join(m_dir, f"{fid}.rttm")
                if os.path.exists(rttm): file_annots[disp_n] = load_rttm(rttm).get(fid, Annotation())

            edn = errata_dict.get(fid, {}) if fid in errata_dict else {}
            eval_bound = edn.get("trim_end", None)
            eval_start = edn.get("trim_start", None)

            if fid in gold_annots:
                plot_timeline(
                    gold_annots[fid],
                    file_annots,
                    fid,
                    args.output,
                    eval_boundary=eval_bound,
                    eval_start=eval_start,
                    suffix="_full",
                )
                f.write(f"![Full Timeline {fid}](timeline_{fid}_full.png)\n\n")

                # --- 60-Second Zoom Snippets ---
                best_seg, worst_seg = find_extreme_segments(
                    gold_annots[fid],
                    file_annots,
                    window_duration=60.0,
                    step=30.0,
                    min_speech=15.0,
                    eval_boundary=eval_bound,
                    eval_start=float(eval_start) if eval_start is not None else 0.0,
                )

                if best_seg and worst_seg:
                    f.write("#### 60-Second Snippets (Zoom-in)\n")
                    f.write("Below are 60-second zoomed-in windows showing where the models performed best and worst (based on average DER).\n\n")

                    # Risanje Best Snippet
                    plot_timeline(
                        gold_annots[fid],
                        file_annots,
                        fid,
                        args.output,
                        eval_boundary=eval_bound,
                        eval_start=eval_start,
                        crop_segment=best_seg,
                        title_prefix="BEST Segment (Lowest Avg DER)",
                        suffix="_best",
                    )
                    f.write(f"![Best Segment {fid}](timeline_{fid}_best.png)\n\n")

                    # Risanje Worst Snippet
                    plot_timeline(
                        gold_annots[fid],
                        file_annots,
                        fid,
                        args.output,
                        eval_boundary=eval_bound,
                        eval_start=eval_start,
                        crop_segment=worst_seg,
                        title_prefix="WORST Segment (Highest Avg DER)",
                        suffix="_worst",
                    )
                    f.write(f"![Worst Segment {fid}](timeline_{fid}_worst.png)\n\n")

            # --- Tabela Metrik ---
            for collar in COLLAR_SETTINGS:
                collar_data = deep_dive_data[fid].get(collar, {})
                if not collar_data:
                    continue
                f.write(f"#### Metrics (Collar: {collar:.2f}s)\n\n")

                rows = []
                for m_name, stats in collar_data.items():
                    row = {'Model': m_name}
                    if stats.get('Status') == 'OK':
                        row.update({
                            'DER': stats.get('DER', np.nan),
                            'JER': stats.get('JER', np.nan),
                            'Miss': stats.get('Miss', np.nan),
                            'FA': stats.get('FA', np.nan),
                            'Conf': stats.get('Conf', np.nan),
                            'B-P': stats.get('B-P', np.nan),
                            'B-R': stats.get('B-R', np.nan),
                            'B-F1': stats.get('B-F1', np.nan),
                            'Pur': stats.get('Purity', np.nan),
                            'Cov': stats.get('Cover', np.nan),
                            'VRAM (GB)': stats.get('VRAM', np.nan),
                        })
                    else:
                        row.update({'Status': stats.get('Status', 'FAIL'), 'DER': np.nan})
                    rows.append(row)

                if rows:
                    df_f = pd.DataFrame(rows)
                    if "DER" in df_f.columns:
                        df_f = df_f.sort_values("DER")
                    df_f = highlight_best(
                        df_f,
                        min_cols=["DER", "JER", "Miss", "FA", "Conf", "VRAM (GB)"],
                        max_cols=["B-P", "B-R", "B-F1", "Pur", "Cov"],
                        formatters=formatters,
                    )
                    f.write(tabulate(df_f, headers="keys", tablefmt="github", showindex=False))
                    f.write("\n\n")
            f.write("\n\n---\n\n")

    try:
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0: fix_permissions(args.output, uid, gid)
    except: pass
    print(f"Done. Report at {args.output}")

if __name__ == "__main__":
    main()