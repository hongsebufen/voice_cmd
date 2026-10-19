ARG BASE_IMAGE=thor-pytorch:2.9.1-cu130-r38.2
FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WHISPER_CACHE_DIR=/root/.cache/whisper

COPY requirements.txt /app/requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libespeak-ng1 && \
    rm -rf /var/lib/apt/lists/* && \
    python -m pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
