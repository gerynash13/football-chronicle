from dataclasses import dataclass
from datetime import date
from typing import List
import uuid

@dataclass
class Effect:
    target_type: str    # "team" or "player"
    target_id: str      # team_id or player_id
    attribute: str      # "morale" | "board_confidence" | "fan_satisfaction" | "manager_relationship"
    value: float
    
@dataclass
class Choice:
    text: str
    effects: List[Effect] = field(default_factory=list)
    
@dataclass
class Event:
    date: date
    category: str       # "match" | "training" | "media" | "transfer" | "other"
    blocking: bool      # If true, player must choose an option before proceeding
    title: str
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])  # Unique identifier for the event
    choices: List[Choice] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)  # Effects that apply regardless of choice
    is_read: bool = False  # Track if the event has been read by the player
    resolution: str = ""  # Optional field to store the outcome of the event after choices are made