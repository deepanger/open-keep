"""Text-to-Speech using Edge-TTS."""

import asyncio
import os
import tempfile
from pathlib import Path

import edge_tts


# Chinese voices for workout prompts
VOICE_MAP = {
    "warmup": "zh-CN-XiaoxiaoNeural",
    "exercise": "zh-CN-YunxiNeural",
    "rest": "zh-CN-XiaoyiNeural",
    "default": "zh-CN-XiaoxiaoNeural",
}


async def text_to_speech(
    text: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+10%",
    pitch: str = "+0Hz",
) -> bytes:
    """Convert text to speech and return audio bytes."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


async def text_to_file(
    text: str,
    output_path: str | Path,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+10%",
    pitch: str = "+0Hz",
) -> None:
    """Convert text to speech and save to file."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


def get_voice_for_type(step_type: str) -> str:
    """Get appropriate voice for workout step type."""
    return VOICE_MAP.get(step_type, VOICE_MAP["default"])


def generate_prompt_for_step(
    step_type: str,
    step_name: str,
    duration_seconds: int,
    custom_prompt: str | None,
    type_prompts: dict,
) -> str:
    """Generate prompt text for a workout step."""
    if custom_prompt:
        return custom_prompt

    if step_type not in type_prompts:
        return f"开始{step_name}，持续{duration_seconds}秒"

    template = type_prompts[step_type].intro
    return template.format(name=step_name, duration=duration_seconds)


async def synthesize_prompts(
    prompts: list[tuple[str, str]],
    temp_dir: str | Path,
) -> list[tuple[str, str]]:
    """Synthesize multiple prompts to temp files. Returns list of (text, file_path)."""
    results = []

    for i, (text, step_type) in enumerate(prompts):
        voice = get_voice_for_type(step_type)
        output_path = Path(temp_dir) / f"prompt_{i}.mp3"

        # Adjust rate based on step type
        rate = "+15%" if step_type == "exercise" else "+5%"

        await text_to_file(text, output_path, voice=voice, rate=rate)

        # Add delay between requests to avoid rate limiting
        if i < len(prompts) - 1:
            await asyncio.sleep(0.5)

        results.append((text, str(output_path)))

    return results
