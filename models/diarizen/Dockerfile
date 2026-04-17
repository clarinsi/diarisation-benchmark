# Ta verzija podpira Blackwell (GB10/GB200) arhitekturo.
# FROM nvcr.io/nvidia/pytorch:25.09-py3
FROM scitrera/dgx-spark-pytorch-runtime:2.10.0-v2-cu131
WORKDIR /app

# 1. Izklop bufferinga
ENV PYTHONUNBUFFERED=1

# 2. Sistemske knjižnice
# ffmpeg je dodan, ker ga novi torchcodec/torchaudio včasih potrebujeta za backend
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*
# 3. KLJUČEN FIX: Odstranimo pre-installed torchvision
# Novejši NGC ima torchvision, ki se kregajo s pip paketi.
RUN pip uninstall -y torchvision pynvml

# 4. Namestitev PyAnnote - no deps zaradi nadzora odvisnosti :/
# PyAnnote 4.x prinaša velike spremembe v API-ju (DiarizeOutput)
# RUN pip install --no-cache-dir --no-deps pyannote.audio==4.0.4

# Namestitev ustreznega torchaudio za CUDA 13.0 (ki je na GB10)
# RUN pip install "torchaudio==2.9.0" --index-url https://download.pytorch.org/whl/cu130
# "torchcodec==0.9"
RUN pip install torchcodec --index-url https://download.pytorch.org/whl/cu130
# Namestitev odvisnosti "na roke", da preprečimo konflikte
RUN pip install --no-input \
    asteroid-filterbanks>=0.4.0 \
    opentelemetry-api>=1.34.0 \
    opentelemetry-sdk>=1.34.0 \
    opentelemetry-exporter-otlp>=1.34.0 \
    pyannote-core>=6.0.1 \
    pyannote-database>=6.1.1 \
    pyannote-metrics>=4.0.0 \
    pyannote-pipeline>=4.0.0 \
    torch-audiomentations>=0.12.0 \
    lightning>=2.4 \
    huggingface-hub>=0.28.1 \
    pyannoteai-sdk>=0.3.0 \
    einops>=0.8.1 \
    soundfile>=0.12.1

RUN git clone https://github.com/BUTSpeechFIT/DiariZen.git
# RUN pip install -r ./DiariZen/requirements.txt 
RUN pip install -e ./DiariZen --no-deps
# install pyannote-audio
RUN pip install -e ./DiariZen/pyannote-audio[dev,testing]

RUN pip install toml accelerate "numpy<2.0" 

COPY run_inference.py .

ENTRYPOINT ["python3", "run_inference.py"]