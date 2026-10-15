"""Code ingestion: read a Godot project into a structured, LLM-friendly form."""

from gamelink.ingest.godot import GodotProject, parse_godot_config

__all__ = ["GodotProject", "parse_godot_config"]
