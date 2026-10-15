from dataclasses import dataclass, field
from datetime import date
from typing import List
from player_refs import new_id

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
    id: str = field(default_factory=lambda: new_id()[:8])  # Unique identifier for the event
    choices: List[Choice] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)  # Effects that apply regardless of choice
    is_read: bool = False  # Track if the event has been read by the player
    resolution: str = ""  # Optional field to store the outcome of the event after choices are made
    related_player_id: str = ""  # Player this event concerns (meetings, injuries, etc.)