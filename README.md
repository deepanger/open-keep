# Workout Audio Generator

Generate workout MP3 audio files with TTS voice prompts and background music.

## Features

- Generate audio workouts from JSON configuration
- Edge-TTS for natural Chinese voice synthesis
- Background music with ducking during voice prompts
- Weighted encouragement messages at scheduled intervals
- Fade in/out for smooth transitions

## Installation

```bash
pip install -e .
```

Or with uv:

```bash
uv pip install -e .
```

## Usage

```bash
workout-gen config/workout.json -o output.mp3
```

## Configuration

See `config/workout.json` for a complete example.

### Complete Example

```json
{
  "title": "15分钟HIIT燃脂训练",
  "description": "高强度间歇训练，适合有一定基础的健身者",

  "background_music": {
    "url": "beat1.mp3",
    "fade_in_seconds": 3,
    "fade_out_seconds": 5,
    "loop": true
  },

  "workout": [
    {
      "type": "warmup",
      "name": "原地高抬腿",
      "duration_seconds": 30,
      "prompt": "开始热身，原地高抬腿，保持节奏"
    }
  ],

  "type_prompts": {
    "warmup": {
      "intro": "热身开始，{name}，保持节奏",
      "during": "继续，节奏不要停"
    },
    "exercise": {
      "intro": "开始{name}，全力以赴！",
      "during": "加油！坚持住！还有{duration}秒"
    },
    "rest": {
      "intro": "休息{duration}秒，调整呼吸",
      "during": "保持呼吸节奏，准备下一个动作"
    }
  },

  "encouragements": [
    {"text": "加油！你可以的！", "weight": 1},
    {"text": "坚持住！马上就好！", "weight": 2}
  ],

  "encouragement_schedule": {
    "every_n_seconds": 30,
    "probability": 0.3
  }
}
```

### Field Details

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Workout title, shown in dry-run output |
| `description` | No | Workout description, shown in dry-run output |
| `background_music.url` | Yes | Background music. Can be: local file (`beat1.mp3`), relative path, or URL |
| `background_music.fade_in_seconds` | No | Fade in duration at start (default: 3) |
| `background_music.fade_out_seconds` | No | Fade out duration at end (default: 5) |
| `background_music.loop` | No | Loop music to fit workout duration (default: true) |
| `workout` | Yes | Array of workout steps |

#### Workout Step

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Step type: `warmup` (舒缓), `exercise` (激昂), `rest` (放松). Affects TTS voice and ducking. |
| `name` | Yes | Step name, used in auto-generated prompts |
| `duration_seconds` | Yes | Duration in seconds |
| `prompt` | No | Custom TTS text. If not provided, auto-generated from `type_prompts`. |

#### type_prompts

Templates for auto-generated prompts. Available variables:
- `{name}` - step name
- `{duration}` - step duration in seconds (for `during` template, shows remaining time at middle point)

Each type (`warmup`, `exercise`, `rest`) can have:
- `intro` - spoken at the **start** of the step
- `during` - spoken at the **middle** of the step (only if duration >= 15s)

#### encouragements

Random encouragement messages. Each has:
- `text` - the message
- `weight` - selection weight (higher = more likely)

#### encouragement_schedule

| Field | Default | Description |
|-------|---------|-------------|
| `every_n_seconds` | 30 | Check for encouragement every N seconds |
| `probability` | 0.3 | Chance to play encouragement (0-1) |

### Step Types Effect

| Type | TTS Voice | Ducking | Rate |
|------|-----------|---------|------|
| `warmup` | XiaoxiaoNeural (女声) | -3dB | +5% |
| `exercise` | YunxiNeural (男声) | -6dB | +15% |
| `rest` | XiaoyiNeural (女声) | -3dB | +5% |

## Project Structure

```
workout-audio-generator/
├── pyproject.toml              # Project config & dependencies
├── workout_gen.py              # CLI entry point (module)
├── src/workout_gen/
│   ├── __init__.py
│   ├── cli.py                  # CLI interface
│   ├── config.py               # JSON configuration parsing
│   ├── tts.py                  # Edge-TTS integration
│   ├── audio.py                # pydub audio processing
│   └── generator.py            # Main generation logic
└── config/
    └── workout.json            # Example configuration
```

## Requirements

- Python 3.10+
- Edge-TTS compatible (requires network for TTS service)
- FFmpeg (required by pydub for MP3 support)
