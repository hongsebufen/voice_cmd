from __future__ import annotations

import os
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import torch
import whisper
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field


ASR_MODEL_NAME = os.getenv("ASR_MODEL", "base")
ASR_DEVICE = os.getenv("ASR_DEVICE", "cuda")
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "zh")
PIPER_MODEL = Path(os.getenv("PIPER_MODEL", "/models/zh_CN-huayan-medium.onnx"))
whisper_model = None
active_device = ASR_DEVICE


@asynccontextmanager
async def lifespan(_: FastAPI):
    global whisper_model, active_device

    if ASR_DEVICE == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "ASR_DEVICE=cuda was requested, but CUDA is unavailable in the container. "
            "Check the NVIDIA container runtime and the base image."
        )

    active_device = ASR_DEVICE
    whisper_model = whisper.load_model(
        ASR_MODEL_NAME,
        device=active_device,
        download_root=os.getenv("WHISPER_CACHE_DIR", "/root/.cache/whisper"),
    )
    yield
    whisper_model = None


app = FastAPI(
    title="Jetson ASR + TTS",
    description="Local Whisper speech recognition and Piper speech synthesis.",
    version="0.1.0",
    lifespan=lifespan,
)


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1, max_length=5000)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok" if whisper_model is not None else "starting",
        "asr_model": ASR_MODEL_NAME,
        "asr_device": active_device,
        "tts_model_ready": PIPER_MODEL.is_file(),
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
):
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="ASR model is still loading")

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    try:
        with tempfile.TemporaryDirectory(prefix="asr-") as temp_dir:
            audio_path = Path(temp_dir) / f"input{suffix}"
            audio_path.write_bytes(await file.read())
            result = whisper_model.transcribe(
                str(audio_path),
                language=language or ASR_LANGUAGE,
                initial_prompt=prompt,
                fp16=active_device == "cuda",
            )
            return {"text": result["text"].strip()}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not transcribe audio: {exc}") from exc


@app.post("/v1/audio/speech")
def synthesize(request: SpeechRequest):
    if not PIPER_MODEL.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"TTS voice model is missing: {PIPER_MODEL}",
        )

    with tempfile.TemporaryDirectory(prefix="tts-") as temp_dir:
        output_path = Path(temp_dir) / "speech.wav"
        try:
            subprocess.run(
                [
                    "piper",
                    "--model",
                    str(PIPER_MODEL),
                    "--output_file",
                    str(output_path),
                ],
                input=request.input,
                text=True,
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="TTS generation timed out") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip()[-1000:] if exc.stderr else "Piper failed"
            raise HTTPException(status_code=500, detail=detail) from exc

        if not output_path.is_file():
            raise HTTPException(status_code=500, detail="Piper did not produce an audio file")
        audio = output_path.read_bytes()

    return Response(content=audio, media_type="audio/wav")
