# Reference RTTM generation for diarisation benchmark

This document describes the methodology, design decisions, and parameters used to generate gold-standard RTTM files for the diarisation benchmark (ROG-Dialog, ROG-Art, and CHILDES-CCPCL).

## 1. Source data

The reference annotations are derived primarily from **Transcriber (.trs)** files provided by CLARIN.SI (ROG-Dialog / ROG-Art). CCPCL uses **CHAT (.cha)** transcripts from the TalkBank CCPCL corpus.

* **ROG-Dialog / ROG-Art:** XML-based `.trs` files.
  * Metadata: `*.trs` with `*Speaker` and `*Turn` segments.
  * Selection: `.std` is preferred over `.pog` when both exist (configurable via `prioritize_pog` in the Python entry points).
* **CCPCL:** CHAT `.cha` files with time-coded line annotations in the form `*SPEAKER: text start_end` (ms).
  * Conversion: extract speaker segments and convert to RTTM with linear merge and minimum-duration heuristics in [`gold_rttm_from_annotations.py`](../gold_rttm_from_annotations.py), invoked from [`ccpcl_data_process.py`](../ccpcl_data_process.py).

## 2. The smoothing problem

Raw manual transcriptions often contain tiny gaps (for example breath pauses) or strict turn-taking segmentation that splits a single phrase into multiple entries when a short backchannel occurs.

Directly converting those raw segments to RTTM inflates segment count and can penalise diarisation models that output smoother segments. **Linear merging** addresses this.

### Design decision: linear merging vs per-speaker merging

1. **Per-speaker merging (rejected):** merge same-speaker segments when the gap is small, even if another speaker spoke in between. That can create overlaps not present in the manual ground truth.
2. **Linear merging (selected):** merge adjacent segments of the same speaker **only if** no other speaker intervenes. This keeps turn-taking structure while smoothing micro-pauses within a turn.

## 3. Tunable parameters (merge and minimum duration)

These defaults are defined as `DEFAULT_MERGE_THRESHOLD` and `DEFAULT_MIN_DURATION` in [`gold_rttm_from_annotations.py`](../gold_rttm_from_annotations.py) and used by [`rog_dialog_data_process.py`](../rog_dialog_data_process.py), [`rog_art_data_process.py`](../rog_art_data_process.py), [`ccpcl_data_process.py`](../ccpcl_data_process.py), and the configurable path in [`convert_trs_to_trim_rttm.py`](../convert_trs_to_trim_rttm.py).

### `merge_threshold` = 1.0 s

Maximum silence between two segments of the **same** speaker (with no other speaker between) that will still be merged into one segment.

### `min_duration` = 0.1 s

Segments shorter than this are dropped after merging, to suppress ultra-short noise clicks and breath marks that dominate false-alarm style errors.

## 4. Output format (RTTM)

Output follows the NIST RTTM convention:

```
SPEAKER <file_id> 1 <onset> <duration> <NA> <NA> <speaker_id> <NA> <NA>
```

* **File ID:** normalised recording id (for example `-std` / `-pog` stripped from TRS names).
* **Channel:** fixed to `1` (mono).
* **Speaker ID:** as in the source annotation (TRS / CHAT).

## 5. Reproducibility (dataset scripts and basenames)

Shell wrappers under the repo root download or extract data and call the matching `*_data_process.py`. Optional **first positional argument** on `prepare_data_rog_dialog.sh`, `prepare_data_rog_art.sh`, and `prepare_data_ccpcl.sh`: gold RTTM **basename** under `data/<dataset>/ref_rttm/` (`.rttm` is appended if missing).

| Dataset | Default basename | Example |
| --- | --- | --- |
| ROG-Dialog / ROG-Art | `default_gold_standard` | `./prepare_data_rog_dialog.sh my_run` → `ref_rttm/my_run.rttm` |
| CHILDES-CCPCL | `ccpcl_gold_standard` | `./prepare_data_ccpcl.sh my_ccpcl` → `ref_rttm/my_ccpcl.rttm` |

Direct Python invocation (after directories are populated):

```bash
python3 rog_dialog_data_process.py --output_filename gold_standard
python3 rog_art_data_process.py --output_filename gold_standard
python3 ccpcl_data_process.py \
  --cha_dir data/raw/CCPCL/CCPCL \
  --audio_dir data/CHILDES-CCPCL/audio \
  --output_file data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm
```

With trimming enabled inside the gold generators, add `--enable_trimming` where supported; a companion `*_trimmed.rttm` is written next to the primary output (see `trimmed_rttm_path` in `gold_rttm_from_annotations.py`).

Operator-oriented steps: [Data preparation](data_preparation.md).

## 6. Standalone CLI: `trim_gold_silences_rttm.py`

[`trim_gold_silences_rttm.py`](../trim_gold_silences_rttm.py) trims existing gold RTTM segment boundaries using WAV evidence (Praat / Parselmouth pipeline). Defaults below match `parse_args()` in that file (run `python3 trim_gold_silences_rttm.py --help` for the live list).

| Option | Default | Meaning |
| --- | --- | --- |
| `--rttm` | `data/ROG-Dialog/ref_rttm/gold_standard.rttm` | Input RTTM |
| `--audio-dir` | `data/ROG-Dialog/audio` | Directory containing `<file_id>.wav` for each RTTM file id |
| `--output` | `data/ROG-Dialog/ref_rttm/gold_trimmed.rttm` | Output RTTM path |
| `--pitch-floor` | `75.0` | Hz |
| `--pitch-ceiling` | `500.0` | Hz |
| `--intensity-drop-db` | `15.0` | dB drop for intensity-based boundary |
| `--guard-ms` | `30.0` | ms guard from each boundary |
| `--max-trim` | `1.5` | max seconds removed per segment edge |
| `--min-duration` | `0.1` | minimum kept segment duration (s) |
| `--pad` | `0.5` | pad (s) |
| `--time-step` | `0.01` | analysis step (s) |
| `--method` | `pitch_or_intensity` | One of `pitch_or_intensity`, `pitch_only`, `intensity_only` |
| `--trim-silence-within` | off | If set, trim / split internal silence using `--min-silence-dur` |
| `--min-silence-dur` | `0.5` | Minimum silence duration (s) for internal cuts |
| `--test-run` | off | Process only the first file id in the RTTM |
| `--verbose` | off | Verbose per-segment logging |

The tool also writes metadata beside the output: `<output_basename>_metadata.txt` (same directory, stem derived from `--output`).

**Example (CCPCL):**

```bash
python3 trim_gold_silences_rttm.py \
  --rttm data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm \
  --audio-dir data/CHILDES-CCPCL/audio \
  --output data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_trimmed.rttm \
  --trim-silence-within
```

**Example (ROG-Dialog, defaults only):**

```bash
python3 trim_gold_silences_rttm.py
```
