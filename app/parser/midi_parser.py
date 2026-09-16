"""MIDI パーサー（設計書 11.1 Infrastructure Layer）。"""

from __future__ import annotations

from .common import ParsedPart, ParsedScore, parse_file, score_title, score_to_notes, score_to_parts


def parse_midi(content: bytes) -> ParsedScore:
    score = parse_file(content, ".mid")
    return score_to_notes(score)


def parse_midi_parts(content: bytes) -> tuple[str | None, list[ParsedPart]]:
    """全トラックを抽出する（設計書 17.2 パート選択）。"""
    score = parse_file(content, ".mid")
    return score_title(score), score_to_parts(score)
