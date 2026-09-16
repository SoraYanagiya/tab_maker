"""TAB変換API（設計書 12.3 / 17.5）。"""

from __future__ import annotations

import base64

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..domain.tuning import get_tuning
from ..optimizer.fingering_optimizer import optimize
from ..optimizer.scoring import ScoringWeights
from ..parser.midi_parser import parse_midi
from ..parser.musicxml_parser import parse_musicxml
from ..renderer.tab_renderer import render_details, render_text
from .schemas import (
    ConvertRequest,
    ConvertResponse,
    FingeringSchema,
    ImportResponse,
    MeasureSchema,
    NoteSchema,
    ScoreContent,
    WarningSchema,
)

router = APIRouter(prefix="/api", tags=["convert"])


def _decode_content(request: ConvertRequest):
    """inputType に応じて Note 列・小節情報を取り出す（設計書 17.5）。"""
    if request.inputType == "note_list":
        if not isinstance(request.content, dict):
            raise HTTPException(status_code=422, detail="note_list には notes/measures を含むオブジェクトが必要です")
        content = ScoreContent.model_validate(request.content)
        return content.notes, content.measures, []

    if request.content is None or not isinstance(request.content, str):
        raise HTTPException(status_code=422, detail=f"{request.inputType} には文字列の content が必要です")

    if request.inputType == "musicxml":
        parsed = parse_musicxml(request.content)
    else:
        try:
            raw = base64.b64decode(request.content, validate=True)
        except Exception as error:  # noqa: BLE001 - 入力不備をまとめて422にする
            raise HTTPException(status_code=422, detail="MIDI は base64 で渡してください") from error
        parsed = parse_midi(raw)

    return (
        [NoteSchema.from_domain(note) for note in parsed.notes],
        [MeasureSchema.from_domain(measure) for measure in parsed.measures],
        parsed.warnings,
    )


@router.post("/convert", response_model=ConvertResponse)
def convert(request: ConvertRequest) -> ConvertResponse:
    note_schemas, measure_schemas, parser_warnings = _decode_content(request)

    notes = [schema.to_domain() for schema in note_schemas]
    measures = [schema.to_domain() for schema in measure_schemas]
    tuning = get_tuning(request.settings.tuning)
    weights = ScoringWeights.from_dict(request.settings.weights)

    result = optimize(
        notes,
        measures,
        tuning=tuning,
        weights=weights,
        notation_octave_shift=request.settings.notationOctaveShift,
    )

    tab = render_text(notes, result.fingerings, tuning, request.settings.measuresPerLine)
    details = (
        render_details(notes, result.fingerings, tuning) if request.settings.includeDetails else None
    )

    warnings = [WarningSchema(**vars(warning)) for warning in result.warnings]
    for message in parser_warnings:
        warnings.insert(
            0,
            WarningSchema(
                noteIndex=-1, measureIndex=0, onsetBeat=0.0, kind="parser", message=message
            ),
        )

    return ConvertResponse(
        tab=tab,
        details=details,
        fingerings=[FingeringSchema(**vars(fingering)) for fingering in result.fingerings],
        warnings=warnings,
        totalCost=result.totalCost,
        notes=note_schemas if request.inputType != "note_list" else None,
        measures=measure_schemas if request.inputType != "note_list" else None,
    )


@router.post("/import", response_model=ImportResponse)
async def import_score(file: UploadFile = File(...)) -> ImportResponse:
    """MusicXML / MIDI ファイルを読み込んで Note 列に変換する（設計書 17.2）。"""
    filename = (file.filename or "").lower()
    content = await file.read()

    if filename.endswith((".mid", ".midi")):
        parsed = parse_midi(content)
        # MIDIは実音。五線譜はギター記譜（実音より1オクターブ上）で扱うため持ち上げる
        for note in parsed.notes:
            if note.midiNumber is not None:
                note.midiNumber += 12
                note.octave += 1
        parsed.warnings.append("MIDIの実音を、ギター記譜（実音より1オクターブ上）に変換して読み込みました。")
    elif filename.endswith((".xml", ".musicxml", ".mxl")):
        parsed = parse_musicxml(content, filename)
    else:
        raise HTTPException(
            status_code=422,
            detail="対応していない形式です（.musicxml / .xml / .mxl / .mid / .midi）",
        )

    return ImportResponse(
        title=parsed.title,
        notes=[NoteSchema.from_domain(note) for note in parsed.notes],
        measures=[MeasureSchema.from_domain(measure) for measure in parsed.measures],
        warnings=parsed.warnings,
    )
