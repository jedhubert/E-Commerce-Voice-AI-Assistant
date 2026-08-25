import os
import asyncio
import logging
import numpy as np
from typing import Optional

from livekit import rtc
from livekit.agents import stt
from livekit.agents.utils.audio import AudioBuffer
from livekit.agents.types import NOT_GIVEN, NotGivenOr, APIConnectOptions
from faster_whisper import WhisperModel

logger = logging.getLogger("stt-whisper")



class WhisperSTT(stt.STT):
    def __init__(self, model_size: Optional[str] = None) -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        chosen_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "base.en")
        cpu_threads = min(4, os.cpu_count() or 4)
        # Load local Whisper model on CPU with int8 quantization and multi-threading for max speed & accuracy
        self._model = WhisperModel(
            chosen_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
        )

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        # Combine all audio frames into one and resample to 16kHz mono if needed
        try:
            if isinstance(buffer, rtc.AudioFrame):
                combined = buffer
            elif isinstance(buffer, (list, tuple)):
                frames = list(buffer)
                if not frames:
                    return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[])
                combined = rtc.combine_audio_frames(frames)
            else:
                combined = rtc.combine_audio_frames([buffer])
        except Exception as err:
            logger.warning(f"Audio buffer format handling warning in WhisperSTT: {err}")
            if isinstance(buffer, rtc.AudioFrame):
                combined = buffer
            else:
                return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[])

        if combined.sample_rate != 16000 or combined.num_channels != 1:
            resampler = rtc.AudioResampler(
                combined.sample_rate, 16000, num_channels=combined.num_channels
            )
            resampled_frames = resampler.push(combined) + resampler.flush()
            combined = rtc.combine_audio_frames(resampled_frames)

        # Convert int16 PCM bytes to float32 normalized numpy array
        raw_bytes = bytes(combined.data)
        if not raw_bytes:
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[])

        audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        if len(audio_np) < 1600:
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[])

        # Transcribe synchronously inside thread executor
        def _transcribe() -> str:
            segments, _ = self._model.transcribe(
                audio_np,
                beam_size=1,
                best_of=1,
                language="en",
                vad_filter=False,
            )
            raw_text = " ".join([seg.text for seg in segments]).strip()
            
            # Prune known Whisper silence/subtitle hallucinations
            clean_lower = raw_text.lower().strip(" .,!?")
            hallucinations = {
                "subtitles by", "thanks for watching",
                "thank you for watching", "amara.org", "mbc", "youtube"
            }
            if clean_lower in hallucinations:
                return ""
            return raw_text

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _transcribe)

        if not text:
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[])

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                stt.SpeechData(language="en", text=text, confidence=0.95)
            ],
        )

    def stream(self, *, language: Optional[str] = None) -> stt.SpeechStream:
        raise NotImplementedError("WhisperSTT is non-streaming")
