#!/usr/bin/env python3
import argparse
from pathlib import Path

from gold_rttm_from_annotations import (
    DEFAULT_MERGE_THRESHOLD,
    DEFAULT_MIN_DURATION,
    generate_gold_rttm_from_cha,
)


def main():
    parser = argparse.ArgumentParser(
        description="CCPCL CHA -> gold RTTM converter",
        epilog="Example: python3 ccpcl_data_process.py --cha_dir data/raw/CCPCL "
        "--audio_dir data/CHILDES-CCPCL/audio --output_file data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm "
        "--merge_threshold 1.0 --min_duration 0.1",
    )
    parser.add_argument(
        "--cha_dir",
        type=str,
        default="data/raw/CCPCL",
        help="Directory with .cha files (or parent containing CCPCL/). Default: %(default)s.",
    )
    parser.add_argument(
        "--audio_dir",
        type=str,
        default="data/CHILDES-CCPCL/audio",
        help="Directory with .wav files (used to filter .cha by matching stems). Default: %(default)s.",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm",
        help="Output RTTM path. Default: %(default)s.",
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
        "--enable_trimming",
        action="store_true",
        default=False,
        help="Also write <name>_trimmed.rttm using Parselmouth (requires numpy, praat-parselmouth; "
        "optional uv setup: docs/data_preparation.md#python-environment-uv).",
    )
    args = parser.parse_args()

    generate_gold_rttm_from_cha(
        Path(args.cha_dir),
        Path(args.audio_dir),
        Path(args.output_file),
        args.merge_threshold,
        args.min_duration,
        pipeline="CHILDES-CCPCL",
        enable_trimming=args.enable_trimming,
    )


if __name__ == "__main__":
    main()
