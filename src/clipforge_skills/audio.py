"""Optional offline system speech, with real duration and no silence fallback."""
from pathlib import Path
import json
import platform
import shutil

from .core import HOME, Fault, digest, fingerprint, load_json, run, write_json
from .media import probe


SYSTEM = platform.system()


def windows_command():
    executable = shutil.which('powershell.exe')
    if not executable:
        raise Fault('tts_unavailable', 'Windows PowerShell/System.Speech unavailable; provide recorded audio')
    return [executable, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', HOME / 'tools/audio/windows_speech.ps1']


def select_voice(voice, text):
    if SYSTEM == 'Windows':
        voices = json.loads(run([*windows_command(), '-ListVoices']))['voices']
        selected = [v for v in voices if v['name'] == voice] if voice else voices
        if not voice and any('\u4e00' <= c <= '\u9fff' for c in text):
            selected = [v for v in selected if v['culture'].startswith('zh')]
        if not selected:
            raise Fault('voice_unavailable', voice or 'No installed voice for this language; provide recorded audio')
        return 'windows_system_speech', selected[0]['name']
    if not shutil.which('say'):
        raise Fault('tts_unavailable', 'No local speech provider; provide a recorded audio file')
    voice = voice or 'Tingting'
    voices = run(['say', '-v', '?'])
    if not any(line.startswith(voice + ' ') for line in voices.splitlines()):
        raise Fault('voice_unavailable', voice)
    return 'macos_say', voice


def speech(root, text_file, voice=None):
    text = Path(text_file).read_text(encoding="utf-8").strip()
    if not text or len(text) > 3000:
        raise Fault("invalid_speech", "Speech requires 1-3000 characters")
    provider, voice = select_voice(voice, text)
    implementation = digest(Path(__file__))
    if provider == 'windows_system_speech':
        implementation += digest(HOME / 'tools/audio/windows_speech.ps1')
    key = fingerprint({"text": text, "voice": voice, "provider": provider, 'implementation': implementation})
    work = Path(root) / "audio" / key
    work.mkdir(parents=True, exist_ok=True)
    manifest = work / "audio.json"
    if manifest.exists() and (work / "voice.wav").exists() and load_json(manifest)["sha256"] == digest(work / "voice.wav"):
        return {"artifact": str(manifest), "audio": str(work / "voice.wav"), "cache_hit": True}
    (work / "text.txt").write_text(text, encoding="utf-8")
    if provider == 'windows_system_speech':
        raw = work / 'system.wav'
        run([*windows_command(), '-Voice', voice, '-TextFile', (work / 'text.txt').resolve(),
             '-OutputWave', raw.resolve()], timeout=600)
    else:
        raw = work / 'voice.aiff'
        run(['say', '-v', voice, '-f', work / 'text.txt', '-o', raw], timeout=600)
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ar", "48000", work / "voice.wav"])
    info = probe(work / "voice.wav")
    write_json(manifest, {"text": text, "voice": voice, "provider": provider, "duration": info["duration"],
                          "sha256": digest(work / "voice.wav"), "alignment": "not_computed", "external_api_cost": 0})
    return {"artifact": str(manifest), "audio": str(work / "voice.wav"), "cache_hit": False, "duration": info["duration"]}
