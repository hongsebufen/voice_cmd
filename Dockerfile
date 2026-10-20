ARG BASE_IMAGE=thor-pytorch:2.9.1-cu130-r38.2
FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WHISPER_CACHE_DIR=/root/.cache/whisper

COPY requirements.txt /app/requirements.txt
COPY pyproject.toml uv.lock /app/
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libespeak-ng1 && \
    rm -rf /var/lib/apt/lists/* && \
    printf 'setuptools<82\n' > /tmp/build-constraints.txt && \
    python -m pip install --no-cache-dir --build-constraint /tmp/build-constraints.txt -r /app/requirements.txt uv && \
    uv export --locked --no-dev --format requirements-txt --output-file /tmp/llm-requirements.txt && \
    uv pip install --system --no-cache -r /tmp/llm-requirements.txt

COPY app /app/app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
