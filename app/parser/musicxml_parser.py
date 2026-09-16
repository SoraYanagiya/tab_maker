"""MusicXML パーサー（設計書 11.1 Infrastructure Layer）。"""

from __future__ import annotations

from .common import ParsedScore, parse_file, score_to_notes


def parse_musicxml(content: bytes | str, filename: str | None = None) -> ParsedScore:
    if isinstance(content, str):
        content = content.encode("utf-8")
    suffix = ".mxl" if filename and filename.lower().endswith(".mxl") else ".musicxml"
    score = parse_file(content, suffix)
    return score_to_notes(score)
