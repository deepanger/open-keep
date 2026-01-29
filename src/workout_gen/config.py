"""Configuration parsing for workout audio generator."""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BackgroundMusic:
    url: str
    fade_in_seconds: int = 3
    fade_out_seconds: int = 5
    loop: bool = True


@dataclass
class WorkoutStep:
    type: str  # warmup, exercise, rest
    name: str
    duration_seconds: int
    prompt: Optional[str] = None


@dataclass
class TypePrompt:
    intro: str
    during: str


@dataclass
class Encouragement:
    text: str
    weight: int = 1


@dataclass
class EncouragementSchedule:
    every_n_seconds: int = 30
    probability: float = 0.3


@dataclass
class WorkoutConfig:
    title: str
    description: str
    background_music: BackgroundMusic
    workout: list[WorkoutStep]
    type_prompts: dict[str, TypePrompt] = field(default_factory=dict)
    encouragements: list[Encouragement] = field(default_factory=list)
    encouragement_schedule: EncouragementSchedule = field(
        default_factory=EncouragementSchedule
    )


def parse_config(config_path: str) -> WorkoutConfig:
    """Parse workout configuration from JSON file."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse background music
    bg_music_data = data.get("background_music", {})
    background_music = BackgroundMusic(
        url=bg_music_data["url"],
        fade_in_seconds=bg_music_data.get("fade_in_seconds", 3),
        fade_out_seconds=bg_music_data.get("fade_out_seconds", 5),
        loop=bg_music_data.get("loop", True),
    )

    # Parse workout steps
    workout = []
    for step in data.get("workout", []):
        workout.append(
            WorkoutStep(
                type=step["type"],
                name=step["name"],
                duration_seconds=step["duration_seconds"],
                prompt=step.get("prompt"),
            )
        )

    # Parse type prompts
    type_prompts = {}
    for type_name, prompts in data.get("type_prompts", {}).items():
        type_prompts[type_name] = TypePrompt(
            intro=prompts.get("intro", ""),
            during=prompts.get("during", ""),
        )

    # Parse encouragements
    encouragements = []
    for enc in data.get("encouragements", []):
        encouragements.append(
            Encouragement(text=enc["text"], weight=enc.get("weight", 1))
        )

    # Parse encouragement schedule
    schedule_data = data.get("encouragement_schedule", {})
    schedule = EncouragementSchedule(
        every_n_seconds=schedule_data.get("every_n_seconds", 30),
        probability=schedule_data.get("probability", 0.3),
    )

    return WorkoutConfig(
        title=data["title"],
        description=data.get("description", ""),
        background_music=background_music,
        workout=workout,
        type_prompts=type_prompts,
        encouragements=encouragements,
        encouragement_schedule=schedule,
    )
