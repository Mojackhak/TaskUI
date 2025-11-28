from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict


DEFAULT_AUTHOR = "mojack"
RHYTHM_VERSION = "v1.0.0"


@dataclass
class ParameterState:
    paradigm_name: str
    language: str  # "zh" or "en"
    test_mode: bool
    cue_type: str  # "audio" or "visual"
    cue_frequency_hz: float
    cue_tone_hz: float
    cue_on_time_ms: int
    start_sound_type: str
    end_sound_type: str
    visual_color_hex: str
    visual_radius_px: int
    num_blocks: int
    inter_block_interval_s: float
    part_durations_s: Dict[str, float] = field(default_factory=dict)
    output_folder: str = ""
    file_prefix: str = "session"
    notes: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["part_durations_s"] = dict(self.part_durations_s)
        return data

    @classmethod
    def from_defaults(cls) -> "ParameterState":
        return cls(
            paradigm_name="Rhythm Paradigm",
            language="en",
            test_mode=False,
            cue_type="audio",
            cue_frequency_hz=1.0,
            cue_tone_hz=880.0,
            cue_on_time_ms=300,
            start_sound_type="start_sequence",
            end_sound_type="end_sequence",
            visual_color_hex="#FF0000",
            visual_radius_px=160,
            num_blocks=2,
            inter_block_interval_s=5.0,
            part_durations_s={
                "rest_pre": 5.0,
                "cued_movement": 15.0,
                "rest_instruction": 5.0,
                "internal_movement": 15.0,
                "rest_post": 5.0,
            },
            output_folder=str(Path.cwd()),
            file_prefix="session",
            notes="",
        )
