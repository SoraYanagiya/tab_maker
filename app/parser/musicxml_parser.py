"""MusicXML パーサー（設計書 11.1 Infrastructure Layer）。"""

from __future__ import annotations

from .common import ParsedPart, ParsedScore, parse_file, score_title, score_to_notes, score_to_parts


def parse_musicxml(content: bytes | str, filename: str | None = None) -> ParsedScore:
    if isinstance(content, str):
        content = content.encode("utf-8")
    suffix = ".mxl" if filename and filename.lower().endswith(".mxl") else ".musicxml"
    score = parse_file(content, suffix)
    return score_to_notes(score)


def parse_musicxml_parts(
    content: bytes | str, filename: str | None = None
) -> tuple[str | None, list[ParsedPart]]:
    """全パートを抽出する（設計書 17.2 パート選択）。"""
    if isinstance(content, str):
        content = content.encode("utf-8")
    suffix = ".mxl" if filename and filename.lower().endswith(".mxl") else ".musicxml"
    score = parse_file(content, suffix)
    return score_title(score), score_to_parts(score)
