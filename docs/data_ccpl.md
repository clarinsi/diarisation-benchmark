# **Appendix: CCPL Dataset Description, Preparation, and Sampling Methodology**

This appendix details the CCPL data source used in the experiment, the procedures required to set up the computational environment, and the methodology applied to extract a representative stratified sample from the original corpus.

## **1. Data Source Description**

One of the datasets utilized in this study is the **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)**. This corpus is part of the broader TalkBank system and provides rich, transcribed interactions of Croatian preschool children, annotated in the CHAT format.

* **Corpus:** CCPCL (Croatian Corpus of Preschool Child Language)  
* **Language:** Croatian (Slavic)  
* **Source Archive:** [https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html](https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html)  
* **Data Types:** Audio recordings (.wav) and corresponding transcripts (.cha).

**Citation and Usage:** Use of this data must adhere to TalkBank's terms of service, which require appropriate citation of the original corpus creators and the CHILDES database system.
* MacWhinney, B. 2000. *The CHILDES Project: Tools for Analyzing Talk* 
* Hržica, G., Bošnjak Botica, T., Košutar, S. (2023). *Stem overgeneralizations in the acquisition of Croatian verbal morphology: Evidence from parental questionnaires.* Word Structure, 16:2-3, 176-205
* Hržica, G., Košutar, S., Botica, T. B. and Milin, P. (2024). *The role of entrenchment and schematisation in the acquisition of rich verbal morphology.* Cognitive Linguistics. https://doi.org/10.1515/cog-2023-0022.

Access to the raw data requires registration and a valid login via the TalkBank system.

## **2. Data Preparation and Environment Setup**

To ensure reproducibility, an automated bash script (prepare\_data\_ccpcl.sh) is provided to structure the directories and prepare the annotations. The following steps outline the procedure to replicate the data environment:

1. **Download the Transcripts:**  
   * Register and log in to TalkBank.  
   * Download the transcript archive (CCPCL.zip) manually from the corpus webpage.  
   * Place the downloaded archive into the project directory at: data/raw/CCPCL.zip.  
2. **Initialize the Environment:**  
   * Execute the setup script from the root directory: ./prepare\_data\_ccpcl.sh  
   * The script will automatically create the necessary directory structure (data/CHILDES-CCPCL/audio, data/CHILDES-CCPCL/annotations/trs, etc.) and safely extract the .cha transcripts to data/raw/CCPCL.  
3. **Acquire Audio Files:**  
   * The script validates the presence of .wav audio files. If none are found, it halts and prompts the user to download them.  
   * Audio files must be downloaded from the CCPCL media repository and placed inside data/CHILDES-CCPCL/audio. (Note: For the purpose of this experiment, only the stratified sample listed in Section 4 is required).  
4. **Generate the Reference RTTM:**  
   * Once the .wav files are in place, re-run ./prepare\_data\_ccpcl.sh.  
   * The script will detect the audio files and prompt to execute the Python processing script (ccpcl\_data\_process.py).  
   * Upon confirmation, the script parses the .cha files in data/raw/CCPCL/CCPCL/ and generates a gold-standard Diarization file (data/CHILDES-CCPCL/ref\_rttm/ccpcl\_gold\_standard.rttm), applying necessary threshold merging (--merge\_threshold 1.0) and minimum duration filtering (--min\_duration 0.1).

## **3. Stratified Sampling Methodology**

The original CCPCL dataset consists of exactly $N=60$ annotated sessions. To optimize computational resources while maintaining statistical representativeness, a sample size of $n=20$ (approximately $1/3$ of the entire dataset) was extracted.

To ensure that the subset accurately reflects the demographic distribution of the original corpus, **proportionate stratified random sampling** was employed.

1. **Stratification Variables:** The data was stratified along two primary dimensions:  
   * **Age (rounded):** 3, 4, 5, and 6 years.  
   * **Gender:** Male (M) and Female (F).  
2. **Allocation:** The total population was divided into 8 mutually exclusive strata based on the combination of Age and Gender.  
3. **Selection:** From each stratum, exactly $1/3$ of the subjects were randomly selected. Standard rounding techniques were applied to determine the exact number of instances per stratum, ensuring a total sample size of 20 while minimizing representation bias.

The resulting sample perfectly preserves the gender balance (10 Males, 10 Females) and the specific age-gender ratios present in the original dataset.

## **4. Selected Representative Sample**

The table below lists the specific sessions selected through the stratified sampling process. Direct download links to the corresponding .wav audio files from the TalkBank media server are provided for immediate replication of the experiment.

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

*(Note: Corresponding .cha transcript files are generated and processed via the procedure outlined in Section 2).*