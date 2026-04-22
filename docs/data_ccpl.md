# Appendix: CCPCL dataset description, preparation, and sampling methodology

This appendix details the **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)** used in the benchmark, how to prepare it in this repository, and the stratified sampling methodology for the 20-session evaluation subset.

See also the operator-oriented guide: [Data preparation](data_preparation.md).

## 1. Data source description

The **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)** is part of TalkBank and provides transcribed interactions of Croatian preschool children in **CHAT (`.cha`)** format with associated **`.wav`** audio.

* **Corpus:** CCPCL (Croatian Corpus of Preschool Child Language)
* **Language:** Croatian (Slavic)
* **Source archive (registration required):** [https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html](https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html)
* **Data types:** Audio (`.wav`) and transcripts (`.cha`).

**Citation and usage:** Follow TalkBank terms of service and cite the corpus and CHILDES appropriately, for example:

* MacWhinney, B. 2000. *The CHILDES Project: Tools for Analyzing Talk*
* Hržica, G., Bošnjak Botica, T., Košutar, S. (2023). *Stem overgeneralizations in the acquisition of Croatian verbal morphology: Evidence from parental questionnaires.* Word Structure, 16:2-3, 176-205
* Hržica, G., Košutar, S., Botica, T. B. and Milin, P. (2024). *The role of entrenchment and schematisation in the acquisition of rich verbal morphology.* Cognitive Linguistics. [https://doi.org/10.1515/cog-2023-0022](https://doi.org/10.1515/cog-2023-0022)

## 2. Data preparation in this repository

Reproducible layout and gold RTTM generation are driven by [`prepare_data_ccpcl.sh`](../prepare_data_ccpcl.sh) (or `./prepare_data.sh ccpcl` from [`prepare_data.sh`](../prepare_data.sh)).

1. **Download transcripts (manual):** register and sign in at TalkBank, download **CCPCL.zip**, and place it at **`data/raw/CCPCL.zip`**.
2. **Run the preparation script** from the repository root, for example `./prepare_data_ccpcl.sh` or `./prepare_data.sh ccpcl`. An optional first argument sets the gold RTTM basename (default `ccpcl_gold_standard`, written to `data/CHILDES-CCPCL/ref_rttm/<basename>.rttm`; append `.rttm` automatically if omitted).
   * The script creates `data/CHILDES-CCPCL/` (including `audio/`, `annotations/trs/`, `docs/`) and extracts the archive under **`data/raw/CCPCL/`**. If the zip contains a nested `CCPCL/` directory, the Python step uses that path automatically (see shell script `CHA_DIR` logic).
3. **Add audio:** download `.wav` files (see Section 4 for the benchmark list and links) into **`data/CHILDES-CCPCL/audio/`**.
   * If **no** `.wav` files are present, the shell script prints download instructions and **does not** run `ccpcl_data_process.py`; it still prints a final “script finished” line. Re-run after adding audio.
4. **Gold RTTM:** when `.wav` files are present, the script compares their stems to the embedded 20-file benchmark list. Depending on the outcome, it may prompt whether to continue, then (if you confirm) runs:

   ```bash
   python3 ccpcl_data_process.py [--enable_trimming] \
     --cha_dir <resolved CHA directory> \
     --audio_dir data/CHILDES-CCPCL/audio \
     --output_file data/CHILDES-CCPCL/ref_rttm/<basename>.rttm
   ```

   The shell wrapper sets `--output_file` from the optional first positional argument (default basename `ccpcl_gold_standard`).

   Defaults for merge and minimum segment length match [`gold_rttm_from_annotations.py`](../gold_rttm_from_annotations.py): **`merge_threshold=1.0`** s, **`min_duration=0.1`** s (see `ccpcl_data_process.py` argparse defaults).

## 3. Stratified sampling methodology

The full CCPCL release contains **N = 60** annotated sessions. The benchmark uses **n = 20** sessions selected with **proportionate stratified random sampling** by rounded age (3–6 years) and gender, preserving approximate balance (10 male / 10 female in the published sample).

## 4. Selected representative sample (benchmark WAV stems)

The twenty session IDs below match the `EXPECTED_WAV_STEMS` list in [`prepare_data_ccpcl.sh`](../prepare_data_ccpcl.sh). File names are `<SessionID>.wav`.

| Age (Years) | Gender | Session ID | File Name | Download Link (.wav) |
| :---- | :---- | :---- | :---- | :---- |
| **3** | M | 1-01801 | 1-01801.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-01801.wav?f=save) |
| **3** | M | 1-02604 | 1-02604.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-02604.wav?f=save) |
| **3** | M | 1-10106 | 1-10106.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-10106.wav?f=save) |
| **3** | F | 1-011610 | 1-011610.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-011610.wav?f=save) |
| **3** | F | 1-03007 | 1-03007.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-03007.wav?f=save) |
| **3** | F | 1-13112 | 1-13112.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-13112.wav?f=save) |
| **4** | M | 1-00606 | 1-00606.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-00606.wav?f=save) |
| **4** | M | 1-02209 | 1-02209.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-02209.wav?f=save) |
| **4** | F | 1-01308 | 1-01308.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-01308.wav?f=save) |
| **4** | F | 1-02808 | 1-02808.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-02808.wav?f=save) |
| **5** | M | 3-00503 | 3-00503.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-00503.wav?f=save) |
| **5** | M | 3-01804 | 3-01804.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-01804.wav?f=save) |
| **5** | F | 1-0605 | 1-0605.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/1-0605.wav?f=save) |
| **5** | F | 3-02912 | 3-02912.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-02912.wav?f=save) |
| **5** | F | 3-12012 | 3-12012.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-12012.wav?f=save) |
| **6** | M | 3-0114 | 3-0114.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-0114.wav?f=save) |
| **6** | M | 3-01707 | 3-01707.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-01707.wav?f=save) |
| **6** | M | 3-02709 | 3-02709.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-02709.wav?f=save) |
| **6** | F | 3-00112 | 3-00112.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-00112.wav?f=save) |
| **6** | F | 3-01606 | 3-01606.wav | [Download](https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav/3-01606.wav?f=save) |

Corresponding `.cha` transcripts are included in **CCPCL.zip**; the preparation script filters them to stems present as `.wav` in `data/CHILDES-CCPCL/audio/` when generating the gold RTTM.
