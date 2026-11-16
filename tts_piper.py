import io
import asyncio
import uuid
import wave

from livekit.agents import tts
from livekit.agents.types import APIConnectOptions


class LocalTTS(tts.TTS):
    def __init__(self, sample_rate: int = 24000) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._sample_rate = sample_rate

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> tts.ChunkedStream:
        return LocalChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class LocalChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: LocalTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        text = self._input_text

        loop = asyncio.get_running_loop()
        raw_audio, default_rate, default_ch = await loop.run_in_executor(None, self._generate_audio_bytes, text)

        if not raw_audio:
            return

        if raw_audio.startswith(b"RIFF"):
            try:
                with wave.open(io.BytesIO(raw_audio), "rb") as wf:
                    framerate = wf.getframerate()
                    n_channels = wf.getnchannels()
                    pcm_data = wf.readframes(wf.getnframes())
            except Exception as e:
                print("Error parsing WAV header, treating as PCM:", e)
                framerate = default_rate
                n_channels = default_ch
                pcm_data = raw_audio
        else:
            framerate = default_rate
            n_channels = default_ch
            pcm_data = raw_audio

        request_id = str(uuid.uuid4())
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=framerate,
            num_channels=n_channels,
            mime_type="audio/pcm",
        )

        if pcm_data:
            output_emitter.push(pcm_data)
        output_emitter.end_input()

    def _generate_audio_bytes(self, text: str) -> tuple[bytes, int, int]:
        """Generate audio bytes (PCM or WAV) from text using native in-memory SAPI5 on Windows or fallbacks.
        Returns (audio_bytes, sample_rate, num_channels).
        """
        import re

        clean_text = text.replace("₹", "Rupees ").replace("Rs.", "Rupees ").replace("rs.", "Rupees ").replace("INR", "Rupees ")
        clean_text = re.sub(r'[\*\#\_`]', '', clean_text)
        clean_text = clean_text.strip()
        if not clean_text:
            return b"", 24000, 1

        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            
            try:
                for v in voice.GetVoices():
                    if "zira" in v.GetDescription().lower():
                        voice.Voice = v
                        break
            except Exception:
                pass

            voice.Rate = 1
            stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            
            try:
                fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
                fmt.Type = 22
                stream.Format = fmt
            except Exception as fmt_err:
                print("SAPI5 audio format configuration warning:", fmt_err)

            voice.AudioOutputStream = stream
            voice.Speak(clean_text)
            
            data = stream.GetData()
            if data:
                raw_bytes = bytes(data)
                if len(raw_bytes) > 44:
                    return raw_bytes, 24000, 1
        except Exception as sapi_err:
            print("Direct SAPI5 in-memory synthesis warning:", sapi_err)

        try:
            import pythoncom
            pythoncom.CoInitialize()
            import pyttsx3
            import tempfile
            import os

            engine = pyttsx3.init()
            engine.setProperty("rate", 185)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                temp_filename = tf.name

            engine.save_to_file(clean_text, temp_filename)
            engine.runAndWait()

            with open(temp_filename, "rb") as f:
                data = f.read()
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            
            if data and len(data) > 44:
                return data, 22050, 1
        except Exception as local_err:
            print("Local pyttsx3 synthesis warning:", local_err)

        try:
            from gtts import gTTS
            import io as _io

            tts_obj = gTTS(text=clean_text, lang="en", slow=False)
            fp = _io.BytesIO()
            tts_obj.write_to_fp(fp)
            fp.seek(0)

            try:
                from pydub import AudioSegment

                sound = AudioSegment.from_file(fp, format="mp3")
                wav_fp = _io.BytesIO()
                sound.export(wav_fp, format="wav")
                return wav_fp.getvalue(), 24000, 1
            except Exception:
                pass
        except Exception as gtts_err:
            print("gTTS fallback error:", gtts_err)

        return b"", 24000, 1


