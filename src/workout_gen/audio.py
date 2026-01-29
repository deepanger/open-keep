"""Audio processing using pydub."""

import os
import random
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

# Voice boost gain in dB (positive = louder)
VOICE_BOOST_DB = 6


def load_audio(file_path: str | Path) -> AudioSegment:
    """Load an audio file."""
    return AudioSegment.from_file(file_path)


def load_or_download_audio(url: str, cache_dir: str | Path) -> str:
    """Load audio from URL or local path."""
    import hashlib
    import requests

    # Check if it's a local file (relative or absolute path)
    local_path = Path(url)
    if local_path.exists():
        return str(local_path.resolve())

    # Check for relative path from current directory
    cwd_path = Path.cwd() / url
    if cwd_path.exists():
        return str(cwd_path.resolve())

    # Otherwise, download from URL
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create filename from URL hash
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    ext = ".mp3" if url.endswith(".mp3") else ".audio"
    cached_path = cache_dir / f"{url_hash}{ext}"

    if cached_path.exists():
        return str(cached_path)

    # Download
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with open(cached_path, "wb") as f:
        f.write(response.content)

    return str(cached_path)


def apply_fade(audio: AudioSegment, fade_in_ms: int = 0, fade_out_ms: int = 0) -> AudioSegment:
    """Apply fade in/out to audio."""
    if fade_in_ms > 0:
        audio = audio.fade_in(fade_in_ms)
    if fade_out_ms > 0:
        audio = audio.fade_out(fade_out_ms)
    return audio


def overlay_audio(
    base: AudioSegment,
    overlay: AudioSegment,
    position_ms: int = 0,
    voice_boost_db: float = VOICE_BOOST_DB,
) -> AudioSegment:
    """Overlay audio on base, optionally boosting the overlay (foreground) volume."""
    # Ensure base is long enough
    required_length = position_ms + len(overlay)
    if len(base) < required_length:
        base = base + AudioSegment.silent(duration=required_length - len(base))

    # Boost the overlay (foreground) audio if specified
    if voice_boost_db != 0:
        overlay = overlay.apply_gain(voice_boost_db)

    # Overlay the audio
    return base.overlay(overlay, position=position_ms)


def extend_to_duration(audio: AudioSegment, duration_ms: int) -> AudioSegment:
    """Extend audio to specified duration by looping or adding silence."""
    if len(audio) >= duration_ms:
        return audio[:duration_ms]

    # Loop to fill
    result = AudioSegment.silent(duration=duration_ms)
    loop_count = 0
    current_pos = 0

    while current_pos < duration_ms:
        loop_audio = audio if loop_count == 0 else audio
        remaining = duration_ms - current_pos

        if len(loop_audio) <= remaining:
            result = result.overlay(loop_audio, position=current_pos)
            current_pos += len(loop_audio)
        else:
            result = result.overlay(loop_audio[:remaining], position=current_pos)
            current_pos = duration_ms

        loop_count += 1

    return result


def random_weighted_select(items: list, weights: list[int]) -> tuple:
    """Select an item based on weights."""
    total_weight = sum(weights)
    if total_weight == 0:
        return items[0], 0

    random_value = random.randint(1, total_weight)
    cumulative = 0

    for i, (item, weight) in enumerate(zip(items, weights)):
        cumulative += weight
        if random_value <= cumulative:
            return item, i

    return items[-1], len(items) - 1


def concatenate_segments(segments: list[AudioSegment]) -> AudioSegment:
    """Concatenate multiple audio segments in sequence."""
    if not segments:
        return AudioSegment.silent(duration=0)

    result = segments[0]
    for segment in segments[1:]:
        result = result + segment

    return result


def save_audio(
    audio: AudioSegment,
    output_path: str | Path,
    format: str = "mp3",
    loudnorm: bool = False,
    target_loudness: float = -16.0,
) -> None:
    """Save audio to file, optionally applying loudness normalization."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = output_path.with_suffix(".temp.mp3")

    try:
        # First export to temp file
        audio.export(str(temp_path), format=format)

        if loudnorm:
            import subprocess

            # Apply ffmpeg loudnorm filter
            # I: input integrated loudness (-23 is default, we'll measure)
            # TP: true peak (-1.5 is default)
            # LRA: loudness range (7 is default)
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-i", str(temp_path),
                "-af", f"loudnorm=I={target_loudness}:TP=-1.5:LRA=7",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: loudnorm failed ({result.stderr[:100]}), using original")
                temp_path.replace(output_path)
            else:
                temp_path.unlink()
        else:
            temp_path.replace(output_path)

    except Exception as e:
        # Fallback: just move the temp file
        if temp_path.exists():
            temp_path.replace(output_path)
        raise
