"""Main workout audio generation logic."""

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from .audio import (
    apply_fade,
    extend_to_duration,
    load_audio,
    load_or_download_audio,
    overlay_audio,
    save_audio,
)
from .config import (
    BackgroundMusic,
    Encouragement,
    EncouragementSchedule,
    TypePrompt,
    WorkoutConfig,
    WorkoutStep,
    parse_config,
)
from .tts import (
    generate_prompt_for_step,
    get_voice_for_type,
    synthesize_prompts,
)


# Minimum duration to play during prompt
DURING_MIN_DURATION_SECONDS = 15


@dataclass
class GenerationResult:
    """Result of audio generation."""
    success: bool
    output_path: Optional[str] = None
    total_duration_seconds: float = 0
    tts_duration_seconds: float = 0
    error: Optional[str] = None


@dataclass
class WorkoutStepInfo:
    """Information about a workout step including TTS timing."""
    step: WorkoutStep
    prompt_text: str
    start_time_seconds: float
    tts_duration_seconds: float = 0


class WorkoutAudioGenerator:
    """Generate workout audio with TTS prompts and background music."""

    def __init__(self, config: WorkoutConfig):
        self.config = config
        self.cache_dir = Path(tempfile.gettempdir()) / "workout_gen_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        output_path: str,
        loudnorm: bool = False,
        target_loudness: float = -16.0,
    ) -> GenerationResult:
        """Generate the workout audio file."""
        try:
            # Create temp directory for TTS outputs
            with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_dir:
                # Download background music
                print(f"Downloading background music...")
                bg_music_path = load_or_download_audio(
                    self.config.background_music.url,
                    self.cache_dir / "music"
                )
                bg_music = load_audio(bg_music_path)

                # Apply fade in/out to background
                fade_in_ms = self.config.background_music.fade_in_seconds * 1000
                fade_out_ms = self.config.background_music.fade_out_seconds * 1000
                bg_music = apply_fade(bg_music, fade_in_ms=fade_in_ms, fade_out_ms=fade_out_ms)

                # Calculate total duration
                total_duration_ms = sum(
                    step.duration_seconds * 1000 for step in self.config.workout
                )

                # Extend background music to cover entire workout
                bg_music = extend_to_duration(
                    bg_music,
                    total_duration_ms,
                    loop=self.config.background_music.loop,
                )

                # Generate prompts for workout steps
                prompts = []
                for step in self.config.workout:
                    prompt_text = generate_prompt_for_step(
                        step.type,
                        step.name,
                        step.duration_seconds,
                        step.prompt,
                        self.config.type_prompts,
                    )
                    prompts.append((prompt_text, step.type))

                print(f"Synthesizing {len(prompts)} prompts...")
                prompt_files = await synthesize_prompts(prompts, temp_dir)

                # Measure TTS durations
                tts_durations = []
                for i, (text, step_type) in enumerate(prompts):
                    if i < len(prompt_files):
                        _, prompt_path = prompt_files[i]
                        prompt_audio = load_audio(prompt_path)
                        tts_durations.append(len(prompt_audio) / 1000.0)  # ms to seconds
                    else:
                        tts_durations.append(0)

                # Build the final audio by overlaying prompts
                result_audio = bg_music
                current_position_ms = 0
                total_tts_ms = 0

                for i, step in enumerate(self.config.workout):
                    step_duration_ms = step.duration_seconds * 1000
                    step_type = step.type

                    # Load and overlay the intro prompt at the start of each step
                    if i < len(prompt_files):
                        _, prompt_path = prompt_files[i]
                        prompt_audio = load_audio(prompt_path)
                        tts_duration_ms = len(prompt_audio)
                        total_tts_ms += tts_duration_ms

                        # Apply voice boost (no ducking of background music)
                        result_audio = overlay_audio(
                            result_audio,
                            prompt_audio,
                            position_ms=current_position_ms,
                        )

                    # Add during prompt if step is long enough
                    during_position_ms = None
                    if step.duration_seconds >= DURING_MIN_DURATION_SECONDS:
                        during_prompt = self._generate_during_prompt(step)
                        if during_prompt:
                            print(f"Adding during prompt: {during_prompt}")
                            # Play during prompt at middle of step
                            during_position_ms = current_position_ms + step_duration_ms // 2
                            during_audio = await self._synthesize_text(during_prompt, step_type)
                            if during_audio:
                                result_audio = overlay_audio(
                                    result_audio,
                                    during_audio,
                                    position_ms=during_position_ms,
                                )
                                total_tts_ms += len(during_audio)

                    # Add encouragement if scheduled (skip during prompt time)
                    if self.config.encouragements:
                        result_audio, encouragement_tts_ms = await self._add_encouragements(
                            result_audio,
                            current_position_ms,
                            step_duration_ms,
                            step_type,
                            exclude_positions=[during_position_ms] if during_position_ms else [],
                        )
                        total_tts_ms += encouragement_tts_ms

                    current_position_ms += step_duration_ms

                # Total duration is the workout duration (TTS is overlaid, not appended)
                actual_total_ms = max(total_duration_ms, current_position_ms)

                # Save result
                save_audio(
                    result_audio,
                    output_path,
                    loudnorm=loudnorm,
                    target_loudness=target_loudness,
                )

                return GenerationResult(
                    success=True,
                    output_path=output_path,
                    total_duration_seconds=actual_total_ms / 1000,
                    tts_duration_seconds=total_tts_ms / 1000,
                )

        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e),
            )

    def _generate_during_prompt(self, step: WorkoutStep) -> str | None:
        """Generate during-prompt text for a step."""
        if step.type not in self.config.type_prompts:
            return None

        template = self.config.type_prompts[step.type].during
        if not template:
            return None

        # Calculate remaining time (at middle point, roughly half remaining)
        remaining = step.duration_seconds // 2
        return template.format(name=step.name, duration=remaining)

    async def _synthesize_text(self, text: str, step_type: str) -> AudioSegment | None:
        """Synthesize text to AudioSegment."""
        import edge_tts

        voice = get_voice_for_type(step_type)
        rate = "+15%" if step_type == "exercise" else "+5%"

        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_data = b""

        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
        except Exception:
            return None

        if not audio_data:
            return None

        # Save to temp file and load with pydub
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            temp_path = Path(f.name)

        try:
            audio = load_audio(temp_path)
            temp_path.unlink()
            return audio
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            return None

    async def _add_encouragements(
        self,
        audio: AudioSegment,
        start_ms: int,
        duration_ms: int,
        step_type: str,
        exclude_positions: list[int | None] | None = None,
    ) -> tuple[AudioSegment, int]:
        """Add encouragement clips at scheduled intervals."""
        schedule = self.config.encouragement_schedule
        enc_interval_ms = schedule.every_n_seconds * 1000
        probability = schedule.probability

        # Buffer around excluded positions to avoid overlapping with during prompts
        exclude_buffer_ms = 5000  # 5 seconds buffer

        encouragement_texts = [enc.text for enc in self.config.encouragements]
        weights = [enc.weight for enc in self.config.encouragements]

        current_pos = start_ms + enc_interval_ms
        total_tts_ms = 0

        while current_pos < start_ms + duration_ms:
            # Skip if too close to an excluded position (during prompt)
            skip = False
            if exclude_positions:
                for pos in exclude_positions:
                    if pos is not None and abs(current_pos - pos) < exclude_buffer_ms:
                        skip = True
                        break

            if not skip:
                import random
                if random.random() < probability:
                    # Select random encouragement
                    text = random.choices(encouragement_texts, weights=weights)[0]
                    print(f"Adding encouragement: {text}")

                    encouragement_audio = await self._synthesize_text(text, step_type)
                    if encouragement_audio:
                        audio = overlay_audio(audio, encouragement_audio, position_ms=current_pos)
                        total_tts_ms += len(encouragement_audio)

            current_pos += enc_interval_ms

        return audio, total_tts_ms


def generate_workout_audio(
    config_path: str,
    output_path: str,
    loudnorm: bool = False,
    target_loudness: float = -16.0,
) -> GenerationResult:
    """Generate workout audio from config file."""
    config = parse_config(config_path)
    generator = WorkoutAudioGenerator(config)
    return asyncio.run(generator.generate(output_path, loudnorm, target_loudness))
