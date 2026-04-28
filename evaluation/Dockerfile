FROM python:3.10-slim

WORKDIR /app

# Sistemske knjižnice za matplotlib
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# IZKLOP BUFFERINGA
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiramo kodo; dataset errata is mounted by the runner, not baked into the image.
COPY score.py .
COPY generate_report.py .
COPY gold_rttm_provenance.py .
COPY errata_merge.py .
COPY recording_metadata.py .
COPY dataset_summary.py .
COPY generate_report_universal.py .

ENTRYPOINT ["python", "generate_report.py"]