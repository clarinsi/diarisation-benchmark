"""
Diarisation Benchmark - DiariZen Inference Runner
=================================================

Runs inference for the DiariZen HuggingFace models and exports RTTM files
plus benchmark metadata in the same style as the existing Nemo and PyAnnote
benchmarking modules.
"""

import argparse
import glob
import json
import os
import platform
import time
import datetime
from pathlib import Path

import soundfile as sf
import sys
import types
import torch
import torchaudio

# --- 1. KORAK: Popravek za torchaudio (TA MORA BITI ABSOLUTNO PRVI!) ---
# Da se pyannote sploh lahko uvozi, moramo najprej zakrpati zvočne module.
class AudioMetaData:
    sample_rate: int
    num_frames: int
    num_channels: int
    bits_per_sample: int
    encoding: str

torchaudio.AudioMetaData = AudioMetaData

dummy_backend = types.ModuleType("torchaudio.backend")
dummy_common = types.ModuleType("torchaudio.backend.common")

dummy_common.AudioMetaData = AudioMetaData
dummy_backend.common = dummy_common

sys.modules["torchaudio.backend"] = dummy_backend
sys.modules["torchaudio.backend.common"] = dummy_common


# --- 2. KORAK: Varnostni "whitelist" za PyTorch 2.6+ ---
# Zdaj, ko je torchaudio popravljen, lahko varno uvozimo Specifications
from pyannote.audio.core.task import Specifications,Problem,Resolution

# Dodamo oba problematična objekta na seznam varnih
if hasattr(torch.serialization, 'add_safe_globals'):
    torch.serialization.add_safe_globals([
        torch.torch_version.TorchVersion,
        Specifications,
        Problem,
        Resolution
    ])

# Za vsak slučaj obdržimo še "surovi" monkey patch
_original_load = torch.serialization.load

def _forgiving_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)

torch.load = _forgiving_load
torch.serialization.load = _forgiving_load
# --- 5. KORAK: Popolni prevzem zvočnega zaledja s 'soundfile' ---
import soundfile as sf
import numpy as np

def _custom_info(filepath, *args, **kwargs):
    # Preberemo metapodatke s soundfile brez nalaganja celotnega zvoka v pomnilnik
    sf_info = sf.info(filepath)
    
    # Uporabimo naš lažni razred AudioMetaData iz 2. koraka
    meta = AudioMetaData()
    meta.sample_rate = sf_info.samplerate
    meta.num_frames = sf_info.frames
    meta.num_channels = sf_info.channels
    meta.bits_per_sample = 16  # standardna vrednost, če ni določeno
    meta.encoding = sf_info.subtype
    return meta

def _custom_load(filepath, *args, **kwargs):
    # Preberemo dejanski zvok (soundfile vrne obliko [okvirji, kanali])
    data, samplerate = sf.read(filepath, dtype='float32')
    
    # torchaudio strogo pričakuje obliko tenzorja [kanali, okvirji]
    if data.ndim == 1:
        # Mono zvok: dodamo dimenzijo za kanal na začetek
        data = data[np.newaxis, :]
    else:
        # Stereo zvok: transponiramo matriko
        data = data.T
        
    return torch.from_numpy(data), samplerate

# Brezkompromisno vsilimo naši funkciji na modul torchaudio
torchaudio.info = _custom_info
torchaudio.load = _custom_load

# --- 4. KORAK: Sedaj varno uvozimo in zaženemo DiariZen ---
    
from diarizen.pipelines.inference import DiariZenPipeline


def log(msg):
    print(msg, flush=True)


def fix_permissions(path, uid, gid):
    try:
        os.chown(path, uid, gid)
        if os.path.isfile(path):
            return
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    except Exception:
        pass


def get_system_info(device):
    info = {
        "timestamp": datetime.datetime.now().isoformat(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "system": platform.system(),
        "processor": platform.processor(),
        "device_type": device,
    }
    if device == "cuda":
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_total_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
            info["cuda_version"] = torch.version.cuda
        except Exception as e:
            info["gpu_error"] = str(e)
    else:
        info["gpu_name"] = "N/A"
    return info


def get_peak_memory_mb():
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return 0.0


def get_audio_duration(file_path):
    try:
        with sf.SoundFile(file_path) as f:
            return f.frames / f.samplerate
    except Exception as e:
        log(f"WARNING: Could not read duration for {file_path}: {e}")
        return 0.0

def save_metadata(output_dir, stats):
    json_path = os.path.join(output_dir, "benchmark_metadata.json")
    try:
        with open(json_path, "w") as f:
            json.dump(stats, f, indent=4)
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0:
            fix_permissions(json_path, uid, gid)
    except Exception as e:
        log(f"WARNING: Failed to save metadata: {e}")


def run_inference(input_dir, output_dir, model_name, hf_token=None):
    if hf_token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
        os.environ["HF_TOKEN"] = hf_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        log(f"CUDA is available: {torch.cuda.device_count()} device(s) detected.")
    else:
        log("CUDA not available. Falling back to CPU.")

    log(f"Model: {model_name}")
    log(f"Input directory: {input_dir}")
    log(f"Output directory: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    audio_files = sorted(glob.glob(os.path.join(input_dir, "*.wav")))
    log(f"Found {len(audio_files)} WAV files.")

    benchmark_stats = {
        "model_name": model_name,
        "run_info": get_system_info(device),
        "timings": {
            "model_load_time_s": 0.0,
            "total_processing_time_s": 0.0,
            "total_audio_duration_s": 0.0,
            "overall_rtf": 0.0,
            "max_vram_peak_mb": 0.0,
        },
        "files": []
    }

    torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    load_start = time.time()

    try:
        pipeline = DiariZenPipeline.from_pretrained(
            model_name,
            rttm_out_dir=output_dir,
        )
    except Exception as e:
        log(f"ERROR loading DiariZen pipeline: {e}")
        return

    load_time = time.time() - load_start
    model_vram_mb = get_peak_memory_mb()
    benchmark_stats["timings"]["model_load_time_s"] = load_time
    benchmark_stats["timings"]["max_vram_peak_mb"] = model_vram_mb

    log(f"Model loaded in {load_time:.2f}s (Base VRAM usage: {model_vram_mb:.1f} MB)")

    total_proc = 0.0
    total_audio = 0.0
    max_vram = model_vram_mb

    for idx, audio_path in enumerate(audio_files, start=1):
        filename = Path(audio_path).stem
        output_rttm = os.path.join(output_dir, f"{filename}.rttm")

        if os.path.exists(output_rttm):
            log(f"[{idx}/{len(audio_files)}] Skipping {filename}: RTTM already exists.")
            continue

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

        log(f"[{idx}/{len(audio_files)}] Processing {filename}...")
        audio_dur = get_audio_duration(audio_path)
        start = time.time()

        try:
            result = pipeline(audio_path, sess_name=filename)
            proc_time = time.time() - start
            rtf = proc_time / audio_dur if audio_dur > 0 else 0.0
            peak_vram = get_peak_memory_mb()
            max_vram = max(max_vram, peak_vram)

            if not os.path.exists(output_rttm):
                try:
                    with open(output_rttm, "w") as f:
                        f.write(result.to_rttm())
                except Exception as exc:
                    log(f"WARNING: Failed to write RTTM for {filename}: {exc}")

            log(f"   -> {audio_dur:.1f}s audio in {proc_time:.1f}s (RTF={rtf:.3f}, Peak VRAM={peak_vram:.1f} MB)")

            benchmark_stats["files"].append({
                "filename": filename,
                "audio_duration_s": audio_dur,
                "processing_time_s": proc_time,
                "rtf": rtf,
                "peak_vram_mb": peak_vram,
            })

            total_proc += proc_time
            total_audio += audio_dur
        except Exception as e:
            log(f"ERROR processing {filename}: {e}")
            benchmark_stats["files"].append({
                "filename": filename,
                "error": str(e),
            })

        benchmark_stats["timings"]["total_processing_time_s"] = total_proc
        benchmark_stats["timings"]["total_audio_duration_s"] = total_audio
        benchmark_stats["timings"]["overall_rtf"] = total_proc / total_audio if total_audio > 0 else 0.0
        benchmark_stats["timings"]["max_vram_peak_mb"] = max_vram
        save_metadata(output_dir, benchmark_stats)

    if total_audio > 0:
        benchmark_stats["timings"]["overall_rtf"] = total_proc / total_audio
    benchmark_stats["timings"]["max_vram_peak_mb"] = max_vram
    save_metadata(output_dir, benchmark_stats)

    try:
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0:
            fix_permissions(output_dir, uid, gid)
    except Exception:
        pass

    log("Done!")
    log(f"Overall RTF: {benchmark_stats['timings']['overall_rtf']:.3f}")
    log(f"Max VRAM Usage: {max_vram:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="BUT-FIT/diarizen-wavlm-large-s80-md-v2")
    parser.add_argument("--token", help="HuggingFace token for private/non-commercial model download")
    args = parser.parse_args()

    run_inference(args.input, args.output, args.model, hf_token=args.token)
