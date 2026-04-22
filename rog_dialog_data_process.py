import argparse
from pathlib import Path

from gold_rttm_from_annotations import (
    DEFAULT_MERGE_THRESHOLD,
    DEFAULT_MIN_DURATION,
    DEFAULT_PRIORITIZE_POG,
    generate_gold_rttm_from_trs,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate ROG-Dialog gold RTTM",
        epilog="Example: python3 rog_dialog_data_process.py --merge_threshold 1.0 --min_duration 0.1 --prioritize_pog false --output_filename myconfig",
    )
    parser.add_argument(
        "--merge_threshold",
        type=float,
        default=DEFAULT_MERGE_THRESHOLD,
        help="(float) Threshold (seconds) for merging adjacent same-speaker segments. Default: %(default)s.",
    )
    parser.add_argument(
        "--min_duration",
        type=float,
        default=DEFAULT_MIN_DURATION,
        help="(float) Minimum segment duration (seconds) to keep in RTTM. Default: %(default)s.",
    )
    parser.add_argument(
        "--prioritize_pog",
        type=lambda x: x.lower() in ["1", "true", "yes"],
        default=DEFAULT_PRIORITIZE_POG,
        help="(bool) Use .pog transcripts first if available; otherwise use .std. Accepts true/false. Default: %(default)s.",
    )
    parser.add_argument(
        "--output_filename",
        type=str,
        required=True,
        help="(string) Output RTTM filename (with or without .rttm extension). Required.",
    )
    parser.add_argument(
        "--enable_trimming",
        action="store_true",
        default=False,
        help="Also write <name>_trimmed.rttm using Parselmouth (requires numpy, praat-parselmouth; "
        "optional uv setup: docs/data_preparation.md#python-environment-uv). "
        "Uses dataset audio under data/ROG-Dialog/audio.",
    )
    args = parser.parse_args()

    base_dir = Path("data/ROG-Dialog")
    trs_dir = base_dir / "annotations" / "trs"
    audio_dir = base_dir / "audio"
    ref_rttm_dir = base_dir / "ref_rttm"
    final_name = args.output_filename if args.output_filename.endswith(".rttm") else f"{args.output_filename}.rttm"
    output_path = ref_rttm_dir / final_name

    generate_gold_rttm_from_trs(
        trs_dir,
        output_path,
        args.merge_threshold,
        args.min_duration,
        args.prioritize_pog,
        pipeline="ROG-Dialog",
        audio_dir=audio_dir,
        enable_trimming=args.enable_trimming,
    )


if __name__ == "__main__":
    main()
