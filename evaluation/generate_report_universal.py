#!/usr/bin/env python3
"""
Universal diarization benchmark report generator.

Same metrics and plots as ``generate_report.py``, with dataset-specific
recording metadata loaders (see ``recording_metadata.py``) and neutral
wording for stratification (primary category instead of ROG-only "domain").
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pyannote.core import Annotation
from tabulate import tabulate

import generate_report as gr
from dataset_summary import (
    build_dataset_overview_dict,
    build_dataset_overview_markdown,
    utc_now_iso,
)
from errata_merge import load_merged_errata
from gold_rttm_provenance import format_gold_rttm_report_section
from recording_metadata import default_report_artifacts, load_metadata_for_dataset

MACHINE_REPORT_SCHEMA_VERSION = "1.0"


def _json_sanitize(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, dict):
        return {str(k): _json_sanitize(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_sanitize(v) for v in x]
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else x
    if isinstance(x, str):
        return x
    if isinstance(x, (np.floating,)):
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, dt.datetime):
        return x.isoformat()
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return str(x)


def _resolve_machine_json_path(output_dir: str, report_filename: str, json_output: str | None) -> str:
    if json_output:
        p = json_output.strip()
        return p if os.path.isabs(p) else os.path.join(output_dir, p)
    stem = os.path.splitext(report_filename)[0]
    return os.path.join(output_dir, f"{stem}.machine.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate benchmark report with normalized recording metadata.",
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument("--results_dir", required=True)
    parser.add_argument(
        "--dataset",
        required=True,
        choices=("rog_dialog", "rog_art", "childes_ccpcl"),
        help="Selects metadata loader and default report title / filename.",
    )
    parser.add_argument(
        "--metadata",
        help="Path to metadata: ROG .tsv (speeches) or CCPCL 0demo.xlsx",
    )
    parser.add_argument("--errata", default="DATASET_ERRATA.json")
    parser.add_argument(
        "--no_auto_errata",
        action="store_true",
        help="Do not load AUTO_DATASET_ERRATA.json beside the gold RTTM (default: merge auto + manual).",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--boundary_tolerance",
        type=float,
        default=0.250,
        help="Boundary tolerance (seconds) for segmentation P/R/F1 (default: 0.250)",
    )
    parser.add_argument(
        "--analysis_collar",
        type=float,
        default=0.25,
        help="Collar (s) for category-level boxplots and tables; snapped to COLLAR_SETTINGS.",
    )
    parser.add_argument(
        "--report_title",
        help="Markdown H1 title (default: from --dataset)",
    )
    parser.add_argument(
        "--report_filename",
        help="Output .md filename inside --output (default: from --dataset)",
    )
    parser.add_argument(
        "--category_axis_label",
        default="Primary category",
        help="Human-readable label for stratification axis (default: Primary category)",
    )
    parser.add_argument(
        "--audio_dir",
        help="Override audio directory for dataset technical probing (default: audio_dir from gold RTTM header).",
    )
    parser.add_argument(
        "--json_output",
        help="Machine-readable JSON path (default: <report_filename>.machine.json in --output).",
    )
    parser.add_argument(
        "--no_json",
        action="store_true",
        help="Do not write the machine-readable JSON report.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.gold):
        print(f"ERROR: gold RTTM not found: {args.gold}", flush=True)
        sys.exit(1)
    if not os.path.isdir(args.results_dir):
        print(f"ERROR: --results_dir is not a directory: {args.results_dir}", flush=True)
        sys.exit(1)
    if args.metadata and not os.path.isfile(args.metadata):
        print(f"ERROR: --metadata file not found inside the container: {args.metadata}", flush=True)
        print(
            "  Check Docker -v host paths. Paths like $(pwd)/data/... assume the shell's current "
            "directory is the repository root (the folder that contains data/ and results/), "
            "not evaluation/ or another subfolder.",
            flush=True,
        )
        sys.exit(1)

    audio_override = (args.audio_dir or "").strip() or None
    if audio_override and not os.path.isdir(audio_override):
        print(f"ERROR: --audio_dir is not a directory: {audio_override!r}", flush=True)
        sys.exit(1)

    category_label = args.category_axis_label.strip() or "Primary category"
    default_fn, default_title = default_report_artifacts(args.dataset)
    report_filename = args.report_filename or default_fn
    report_title = args.report_title or default_title

    domain_collar = gr.snap_to_collar_settings(args.analysis_collar)

    os.makedirs(args.output, exist_ok=True)

    gold_annots = gr.load_rttm(args.gold)
    meta_dict = load_metadata_for_dataset(args.dataset, args.metadata)

    manual_errata_path = args.errata if os.path.isfile(args.errata) else None
    errata_dict, errata_meta = load_merged_errata(
        args.gold, manual_errata_path, merge_auto=not args.no_auto_errata
    )

    model_dirs = [f.path for f in os.scandir(args.results_dir) if f.is_dir()]
    if not model_dirs:
        print(
            f"ERROR: No subdirectories under --results_dir: {args.results_dir}",
            flush=True,
        )
        if os.path.isdir(args.results_dir):
            names = sorted(os.listdir(args.results_dir))
            print(f"  Directory exists but is empty or has only files: {names!r}", flush=True)
        print(
            "  Mount the folder that contains one directory per model run (each with "
            "benchmark_metadata.json and *.rttm), e.g. -v \"$(pwd)/results/ROG-Art:/data/results\" "
            "from the repository root.",
            flush=True,
        )
        sys.exit(1)

    summary_data = []
    deep_dive_data = {fid: {c: {} for c in gr.COLLAR_SETTINGS} for fid in gold_annots.keys()}
    model_links: dict[str, str] = {}

    print(f"Processing {len(model_dirs)} models...", flush=True)

    for model_dir in model_dirs:
        hw_global, hw_per_file = gr.get_hardware_stats(model_dir)
        if not hw_global:
            continue

        short_name = os.path.basename(model_dir)
        display_name = short_name.replace("_", " ").replace("-", " ")
        model_links[display_name] = hw_global["model_name"]

        for collar in gr.COLLAR_SETTINGS:
            res = gr.evaluate_model_comprehensive(
                model_dir,
                gold_annots,
                collar,
                hw_per_file,
                errata_dict,
                boundary_tolerance=args.boundary_tolerance,
            )

            ok_count = sum(1 for f in res["files"] if f["Status"] == "OK")
            summary_data.append(
                {
                    "Model": display_name,
                    "Collar": collar,
                    "DER": res["der"],
                    "JER": res["jer"],
                    "B-P": res["b_p"],
                    "B-R": res["b_r"],
                    "B-F1": res["b_f1"],
                    "Purity": res["purity"],
                    "Cover": res["coverage"],
                    "Miss": sum(f.get("Miss", 0) for f in res["files"] if f["Status"] == "OK")
                    / ok_count
                    if ok_count
                    else 0,
                    "FA": sum(f.get("FA", 0) for f in res["files"] if f["Status"] == "OK")
                    / ok_count
                    if ok_count
                    else 0,
                    "Conf": sum(f.get("Conf", 0) for f in res["files"] if f["Status"] == "OK")
                    / ok_count
                    if ok_count
                    else 0,
                    "RTF": hw_global["overall_rtf"],
                    "VRAM": hw_global["max_vram"],
                    "Completed": f"{ok_count}/{len(gold_annots)}",
                }
            )

            for fstat in res["files"]:
                deep_dive_data[fstat["File ID"]][collar][display_name] = fstat

    df_sum = pd.DataFrame(summary_data)
    if df_sum.empty:
        print(
            "ERROR: No usable model runs (each subdirectory needs benchmark_metadata.json).",
            flush=True,
        )
        print(f"  Scanned {len(model_dirs)} subdirectories under {args.results_dir!r}.", flush=True)
        for p in model_dirs[:8]:
            has_meta = os.path.isfile(os.path.join(p, "benchmark_metadata.json"))
            print(f"    - {os.path.basename(p)!r}: benchmark_metadata.json={has_meta}", flush=True)
        if len(model_dirs) > 8:
            print("    - ...", flush=True)
        sys.exit(1)

    print("Generating plots...", flush=True)
    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="DER", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on DER")
    plt.ylabel("DER (%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_der_comparison.png"))
    plt.close()

    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="JER", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on JER")
    plt.ylabel("JER (%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_jer_comparison.png"))
    plt.close()

    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="B-F1", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on Boundary F1")
    plt.ylabel("Boundary F1 (%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_boundary_f1_comparison.png"))
    plt.close()

    m_names = gr.collect_models_with_ok_status(deep_dive_data, domain_collar)
    col_map = {m: chr(65 + i) for i, m in enumerate(m_names)}
    letter_cols = [col_map[m] for m in m_names]
    domain_legend_lines = [f"* **{col_map[m]}**: {m}" for m in m_names]
    domain_legend_md = "\n".join(domain_legend_lines) if domain_legend_lines else ""

    domain_tables = {"DER": "", "JER": "", "B-F1": ""}
    domain_plot_files: dict[str, str] = {}
    domain_metric_specs = [
        ("DER", "DER", "plot_domain_analysis.png", False),
        ("JER", "JER", "plot_domain_analysis_jer.png", False),
        ("B-F1", "Boundary F1", "plot_domain_analysis_bf1.png", True),
    ]

    if m_names:
        for metric_col, plot_label, plot_fname, maximize in domain_metric_specs:
            rows = gr.build_domain_metric_rows(
                deep_dive_data, meta_dict, domain_collar, metric_col
            )
            if not rows:
                continue
            domain_plot_files[metric_col] = plot_fname
            df_m = pd.DataFrame(rows)
            df_m = df_m.rename(columns={"Domain": category_label})

            plt.figure(figsize=(14, 6))
            sns.boxplot(data=df_m, x=category_label, y=metric_col, hue="Model")
            plt.title(
                f"{plot_label} distribution by {category_label.lower()} "
                f"(collar {domain_collar}s)"
            )
            plt.ylabel(f"{metric_col} (%)" if metric_col != "B-F1" else "Boundary F1 (%)")
            plt.xticks(rotation=45, ha="right")
            plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0.0)
            plt.tight_layout()
            plt.savefig(os.path.join(args.output, plot_fname), bbox_inches="tight")
            plt.close()

            pivot_dom = df_m.pivot_table(
                index=category_label, columns="Model", values=metric_col, aggfunc="mean"
            )
            pivot_dom = pivot_dom.reindex(columns=m_names)
            pivot_dom["AVG"] = pivot_dom.mean(axis=1, skipna=True)
            pivot_named = pivot_dom.rename(columns=col_map).reset_index()
            domain_tables[metric_col] = gr.format_domain_pivot_table(
                pivot_named, letter_cols, maximize=maximize
            )

    dataset_overview = build_dataset_overview_dict(
        gold_rttm_path=args.gold,
        gold_annots=gold_annots,
        meta_dict=meta_dict,
        errata_dict=errata_dict,
        audio_dir_override=audio_override,
    )

    print("Writing report...", flush=True)
    formatters = {
        "RTF": gr.fmt_rtf,
        "VRAM": gr.fmt_vram,
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

    report_path = os.path.join(args.output, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# {report_title}\n\n**Date:** {pd.Timestamp.now().date()}\n\n")
        f.write(format_gold_rttm_report_section(args.gold, errata_meta))

        f.write("## 1. Evaluated Models\n")
        for disp_name, full_name in sorted(model_links.items()):
            f.write(
                f"* **{disp_name}** (`{full_name}`) - "
                f"[HuggingFace](https://huggingface.co/{full_name})\n"
            )
        f.write("\n")

        f.write("## 2. Executive Summary\n\n")
        f.write(build_dataset_overview_markdown(dataset_overview, category_label))
        df_lead = df_sum[df_sum["Collar"] == 0.25].copy()
        df_lead = df_lead.rename(columns={"VRAM": "VRAM (GB)"})
        formatters["VRAM (GB)"] = gr.fmt_vram

        df_lead = df_lead.sort_values("DER")
        df_lead = gr.highlight_best(
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
        f.write("\n### Terminology & Methodology\n")
        f.write(
            "* **DER (Diarization Error Rate):** Primary metric. Lower is better. "
            "Sum of Missed, False Alarm, and Confusion rates.\n"
        )
        f.write("* **JER (Jaccard Error Rate):** Speaker-balanced diarization error. Lower is better.\n")
        f.write("* **Miss (%):** Speech present in Gold Standard but missed by the model.\n")
        f.write("* **FA (False Alarm %):** Model predicted speech where Gold Standard is silent.\n")
        f.write("* **Conf (Confusion %):** Speech correctly detected but assigned to the wrong speaker.\n")
        f.write(
            f"* **Boundary P/R/F1 (%):** Segmentation boundary precision/recall/F1 "
            f"using tolerance {args.boundary_tolerance:.3f}s.\n"
        )
        f.write(
            "* **Purity (%):** Evaluates cluster purity. High purity = when a model "
            "identifies a speaker, it is consistently the same person.\n"
        )
        f.write(
            "* **Cover (Coverage %):** Evaluates how much of the original speaker's speech "
            "was captured under a single hypothesis cluster.\n"
        )
        f.write(
            "* **RTF (Real Time Factor):** Processing time divided by audio length. "
            "e.g., `< 0.01` means exceptionally fast processing.\n"
        )
        f.write(
            "* **VRAM (GB):** Peak GPU memory utilized. `0.0 GB` indicates an API/Cloud-based model.\n\n"
        )

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

        f.write("## 4. Visual & Category Analysis\n")
        f.write(
            "Bar charts compare models across **all** configured collars; "
            f"boxplots and comparison tables use one evaluation collar and group files "
            f"by **{category_label}** (from recording metadata).\n\n"
        )
        if float(domain_collar) != float(args.analysis_collar):
            f.write(
                f"* **Category analysis collar:** `{domain_collar}`s "
                f"(requested `--analysis_collar {args.analysis_collar}`; snapped to nearest value "
                f"in `{list(gr.COLLAR_SETTINGS)}`).\n\n"
            )
        else:
            f.write(f"* **Category analysis collar:** `{domain_collar}`s.\n\n")

        f.write("![DER comparison by collar](plot_der_comparison.png)\n\n")
        f.write("![JER comparison by collar](plot_jer_comparison.png)\n\n")
        f.write("![Boundary F1 comparison by collar](plot_boundary_f1_comparison.png)\n\n")

        if m_names:
            if "DER" in domain_plot_files:
                f.write(
                    f"![DER by {category_label.lower()} "
                    f"(collar {domain_collar}s)]({domain_plot_files['DER']})\n\n"
                )
            if "JER" in domain_plot_files:
                f.write(
                    f"![JER by {category_label.lower()} "
                    f"(collar {domain_collar}s)]({domain_plot_files['JER']})\n\n"
                )
            if "B-F1" in domain_plot_files:
                f.write(
                    f"![Boundary F1 by {category_label.lower()} "
                    f"(collar {domain_collar}s)]({domain_plot_files['B-F1']})\n\n"
                )

            if domain_tables.get("DER"):
                f.write(f"### Category comparison (DER %)\n")
                f.write(
                    f"Average DER per {category_label.lower()} at collar `{domain_collar}`s. "
                    "**Bold** highlights the best (lowest) model per row.\n\n"
                )
                f.write(domain_tables["DER"])
                f.write("\n\n")
            if domain_tables.get("JER"):
                f.write(f"### Category comparison (JER %)\n")
                f.write(
                    f"Average JER per {category_label.lower()} at collar `{domain_collar}`s. "
                    "**Bold** highlights the best (lowest) model per row.\n\n"
                )
                f.write(domain_tables["JER"])
                f.write("\n\n")
            if domain_tables.get("B-F1"):
                f.write(f"### Category comparison (Boundary F1 %)\n")
                f.write(
                    f"Average boundary F1 per {category_label.lower()} at collar `{domain_collar}`s "
                    f"(boundary tolerance {args.boundary_tolerance:.3f}s). "
                    "**Bold** highlights the best (highest) model per row.\n\n"
                )
                f.write(domain_tables["B-F1"])
                f.write("\n\n")

            if domain_legend_md:
                f.write("### Category comparison model legend (shared)\n")
                f.write(domain_legend_md)
                f.write("\n\n")
        else:
            f.write(
                "*Category distribution plots and comparison tables are omitted: no models had "
                "OK per-file outputs at the selected analysis collar.*\n\n"
            )

        f.write("## 5. Deep Dive: File-by-File Analysis\n")
        f.write("Detailed breakdown for every file. *For metric definitions, see Executive Summary.*\n\n")

        for fid in sorted(deep_dive_data.keys()):
            meta = meta_dict.get(fid, {})
            f.write(f"### File: {fid}\n\n")
            f.write(
                f"**{category_label}:** {meta.get('Domain', '-')} | "
                f"**Quality:** {meta.get('Quality', '-')} | **Device:** {meta.get('Device', '-')}\n\n"
            )
            if meta.get("Title"):
                f.write(f"> *{meta.get('Title')}*\n\n")
            if meta.get("Keywords"):
                f.write(f"> *Keywords:* {meta.get('Keywords')}\n\n")

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

            file_annots: dict[str, Annotation] = {}
            for m_dir in model_dirs:
                short = os.path.basename(m_dir)
                disp_n = short.replace("_", " ").replace("-", " ")
                rttm = os.path.join(m_dir, f"{fid}.rttm")
                if os.path.exists(rttm):
                    file_annots[disp_n] = gr.load_rttm(rttm).get(fid, Annotation())

            edn = errata_dict.get(fid, {}) if fid in errata_dict else {}
            eval_bound = edn.get("trim_end", None)
            eval_start = edn.get("trim_start", None)

            if fid in gold_annots:
                gr.plot_timeline(
                    gold_annots[fid],
                    file_annots,
                    fid,
                    args.output,
                    eval_boundary=eval_bound,
                    eval_start=eval_start,
                    suffix="_full",
                )
                f.write(f"![Full Timeline {fid}](timeline_{fid}_full.png)\n\n")

                best_seg, worst_seg = gr.find_extreme_segments(
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
                    f.write(
                        "Below are 60-second zoomed-in windows showing where the models performed "
                        "best and worst (based on average DER).\n\n"
                    )

                    gr.plot_timeline(
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

                    gr.plot_timeline(
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

            for collar in gr.COLLAR_SETTINGS:
                collar_data = deep_dive_data[fid].get(collar, {})
                if not collar_data:
                    continue
                f.write(f"#### Metrics (Collar: {collar:.2f}s)\n\n")

                rows = []
                for m_name, stats in collar_data.items():
                    row = {"Model": m_name}
                    if stats.get("Status") == "OK":
                        row.update(
                            {
                                "DER": stats.get("DER", np.nan),
                                "JER": stats.get("JER", np.nan),
                                "Miss": stats.get("Miss", np.nan),
                                "FA": stats.get("FA", np.nan),
                                "Conf": stats.get("Conf", np.nan),
                                "B-P": stats.get("B-P", np.nan),
                                "B-R": stats.get("B-R", np.nan),
                                "B-F1": stats.get("B-F1", np.nan),
                                "Pur": stats.get("Purity", np.nan),
                                "Cov": stats.get("Cover", np.nan),
                                "VRAM (GB)": stats.get("VRAM", np.nan),
                            }
                        )
                    else:
                        row.update({"Status": stats.get("Status", "FAIL"), "DER": np.nan})
                    rows.append(row)

                if rows:
                    df_f = pd.DataFrame(rows)
                    if "DER" in df_f.columns:
                        df_f = df_f.sort_values("DER")
                    df_f = gr.highlight_best(
                        df_f,
                        min_cols=["DER", "JER", "Miss", "FA", "Conf", "VRAM (GB)"],
                        max_cols=["B-P", "B-R", "B-F1", "Pur", "Cov"],
                        formatters=formatters,
                    )
                    f.write(tabulate(df_f, headers="keys", tablefmt="github", showindex=False))
                    f.write("\n\n")
            f.write("\n\n---\n\n")

    json_path: str | None = None
    if not args.no_json:
        json_path = _resolve_machine_json_path(args.output, report_filename, args.json_output)
        files_payload: dict[str, Any] = {}
        for fid in sorted(deep_dive_data.keys()):
            by_collar: dict[str, Any] = {}
            for collar, models in deep_dive_data[fid].items():
                if not models:
                    continue
                ck = str(float(collar))
                by_collar[ck] = {m: st for m, st in models.items()}
            files_payload[fid] = by_collar

        payload: dict[str, Any] = {
            "schema_version": MACHINE_REPORT_SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "report": {
                "title": report_title,
                "dataset": args.dataset,
                "gold_rttm": os.path.abspath(os.path.normpath(args.gold)),
                "results_dir": os.path.abspath(os.path.normpath(args.results_dir)),
                "metadata": os.path.abspath(os.path.normpath(args.metadata))
                if args.metadata
                else None,
                "boundary_tolerance": float(args.boundary_tolerance),
                "analysis_collar_requested": float(args.analysis_collar),
                "domain_collar": float(domain_collar),
                "category_axis_label": category_label,
                "markdown_report_filename": report_filename,
                "audio_dir_override": audio_override,
            },
            "gold_provenance": {
                "comments": list(dataset_overview["provenance"]["comments"]),
                "gold_rttm": dict(dataset_overview["provenance"]["gold_rttm"]),
                "trim_params": dict(dataset_overview["provenance"]["trim_params"]),
            },
            "dataset": {
                "files": [
                    dataset_overview["files"][fid]
                    for fid in sorted(dataset_overview["files"].keys())
                ],
            },
            "dataset_aggregate": dataset_overview["aggregate"],
            "models": {
                "huggingface_links": dict(model_links),
                "summary_rows": df_sum.to_dict(orient="records"),
            },
            "files": files_payload,
            "errata": {
                "merged_per_file": errata_dict,
                "merge_meta": errata_meta,
            },
        }
        safe_payload = _json_sanitize(payload)
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(safe_payload, jf, indent=2, ensure_ascii=False, allow_nan=False)

    try:
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0:
            gr.fix_permissions(args.output, uid, gid)
    except Exception:
        pass
    done_msg = f"Done. Report at {args.output} ({report_path})"
    if json_path:
        done_msg += f" | Machine JSON: {json_path}"
    print(done_msg, flush=True)


if __name__ == "__main__":
    main()
