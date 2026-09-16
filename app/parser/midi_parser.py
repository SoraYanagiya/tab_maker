"""MIDI パーサー（設計書 11.1 Infrastructure Layer）。"""

from __future__ import annotations

from .common import ParsedScore, parse_file, score_to_notes


def parse_midi(content: bytes) -> ParsedScore:
    score = parse_file(content, ".mid")
    return score_to_notes(score)
