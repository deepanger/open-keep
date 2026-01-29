#!/usr/bin/env python3
"""Command-line interface for workout audio generator."""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from workout_gen import __version__
from workout_gen.config import parse_config
from workout_gen.generator import generate_workout_audio


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    td = timedelta(seconds=int(seconds))
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def estimate_tts_duration(text: str, step_type: str) -> float:
    """Estimate TTS duration based on text length."""
    # Rough estimate: ~4 Chinese characters per second at default rate
    # Exercise uses +15% rate (faster), others +5%
    chars_per_second = 4.0
    if step_type == "exercise":
        chars_per_second = 4.5
    return len(text) / chars_per_second


def dry_run(config_path: str) -> None:
    """Print workout timeline without generating audio."""
    config = parse_config(config_path)

    print(f"Workout: {config.title}")
    print(f"Description: {config.description}")
    print("-" * 70)
    print(f"{'#':<3} {'Type':<10} {'Name':<15} {'Start':>8} {'Duration':>8} {'TTS':>6}")
    print("-" * 70)

    current_time = 0
    total_workout = 0
    total_tts = 0

    for i, step in enumerate(config.workout, 1):
        from .tts import generate_prompt_for_step
        prompt_text = generate_prompt_for_step(
            step.type, step.name, step.duration_seconds, step.prompt, config.type_prompts
        )
        tts_est = estimate_tts_duration(prompt_text, step.type)

        start_time = format_time(current_time)
        duration = format_time(step.duration_seconds)
        tts_str = f"{tts_est:.1f}s"

        print(f"{i:<3} {step.type:<10} {step.name:<15} {start_time:>8} {duration:>8} {tts_str:>6}")

        current_time += step.duration_seconds
        total_workout += step.duration_seconds
        total_tts += tts_est

    print("-" * 70)
    print(f"Total workout time: {format_time(total_workout)} ({total_workout:.1f}s)")
    print(f"Total TTS audio: ~{total_tts:.1f}s (overlaid on workout)")
    print(f"Final MP3 duration: {format_time(total_workout)} ({total_workout:.1f}s)")
    print(f"Total steps: {len(config.workout)}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate workout audio with TTS prompts and background music"
    )
    parser.add_argument(
        "config",
        type=Path,
        help="Path to workout configuration JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output MP3 file path (default: workout.mp3)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show workout timeline without generating audio",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--loudnorm",
        action="store_true",
        help="Apply loudness normalization (EBU R128)",
    )
    parser.add_argument(
        "--target-loudness",
        type=float,
        default=-16.0,
        help="Target loudness in LUFS (default: -16, Spotify: -14, YouTube: -14)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Validate config file
    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    # Dry run mode
    if args.dry_run:
        dry_run(str(args.config))
        return

    # Set default output path
    output_path = args.output or Path("workout.mp3")

    if args.verbose:
        print(f"Config: {args.config}")
        print(f"Output: {output_path}")

    # Generate audio
    print("Generating workout audio...")
    if args.loudnorm:
        print(f"Applying loudnorm (target: {args.target_loudness} LUFS)...")
    result = generate_workout_audio(
        str(args.config),
        str(output_path),
        loudnorm=args.loudnorm,
        target_loudness=args.target_loudness,
    )

    if result.success:
        print(f"Success! Audio saved to: {output_path}")
        print(f"Total duration: {result.total_duration_seconds:.1f} seconds")
        if result.tts_duration_seconds > 0:
            print(f"(TTS audio: {result.tts_duration_seconds:.1f}s)")
    else:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
