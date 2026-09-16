"""API のリクエスト/レスポンススキーマ（設計書 12.3 / 17.5 / 17.7.3）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..domain.note import Accidental, Duration, MeasureInfo, Note


class NoteSchema(BaseModel):
    midiNumber: int | None = None
    pitchName: str = "C"
    octave: int = 4
    accidental: Accidental = Accidental.NONE
    duration: Duration = Duration.QUARTER
    isDotted: bool = False
    tieToNext: bool = False
    isRest: bool = False
    onsetBeat: float = 0.0
    measureIndex: int = 0

    def to_domain(self) -> Note:
        return Note(
            midiNumber=self.midiNumber,
            pitchName=self.pitchName,
            octave=self.octave,
            accidental=self.accidental,
            duration=self.duration,
            isDotted=self.isDotted,
            tieToNext=self.tieToNext,
            isRest=self.isRest,
            onsetBeat=self.onsetBeat,
            measureIndex=self.measureIndex,
        )

    @classmethod
    def from_domain(cls, note: Note) -> "NoteSchema":
        return cls(**vars(note))


class MeasureSchema(BaseModel):
    measureIndex: int = 0
    keySignature: str = "C"
    timeSignature: str = "4/4"

    def to_domain(self) -> MeasureInfo:
        return MeasureInfo(
            measureIndex=self.measureIndex,
            keySignature=self.keySignature,
            timeSignature=self.timeSignature,
        )

    @classmethod
    def from_domain(cls, measure: MeasureInfo) -> "MeasureSchema":
        return cls(**vars(measure))


class ScoreContent(BaseModel):
    notes: list[NoteSchema] = Field(default_factory=list)
    measures: list[MeasureSchema] = Field(default_factory=list)


class ConvertSettings(BaseModel):
    tuning: str = "standard"
    weights: dict[str, Any] = Field(default_factory=dict)
    includeDetails: bool = False
    measuresPerLine: int = 4
    # ギター譜は実音より1オクターブ高く記譜するため、既定で -1 オクターブして実音に変換する
    notationOctaveShift: int = -1


class ConvertRequest(BaseModel):
    inputType: Literal["note_list", "musicxml", "midi"] = "note_list"
    content: Any = None
    target: Literal["guitar_tab"] = "guitar_tab"
    mode: Literal["single_note"] = "single_note"
    settings: ConvertSettings = Field(default_factory=ConvertSettings)


class FingeringSchema(BaseModel):
    noteIndex: int
    measureIndex: int
    onsetBeat: float
    isRest: bool
    stringIndex: int | None = None
    stringLabel: str | None = None
    fret: int | None = None
    finger: int = 0
    position: int | None = None
    handShift: int = 0
    isTiedContinuation: bool = False


class WarningSchema(BaseModel):
    noteIndex: int
    measureIndex: int
    onsetBeat: float
    kind: str
    message: str


class ConvertResponse(BaseModel):
    tab: str
    details: str | None = None
    fingerings: list[FingeringSchema] = Field(default_factory=list)
    warnings: list[WarningSchema] = Field(default_factory=list)
    totalCost: float = 0.0
    notes: list[NoteSchema] | None = None
    measures: list[MeasureSchema] | None = None


class ImportResponse(BaseModel):
    title: str | None = None
    notes: list[NoteSchema] = Field(default_factory=list)
    measures: list[MeasureSchema] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    name: str = "無題のプロジェクト"
    notes: list[NoteSchema] | None = None
    measures: list[MeasureSchema] | None = None
    settings: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    notes: list[NoteSchema] | None = None
    measures: list[MeasureSchema] | None = None
    settings: dict[str, Any] | None = None
    generatedTab: dict[str, Any] | None = None


class ProjectDuplicateRequest(BaseModel):
    name: str | None = None


class ProjectSummary(BaseModel):
    projectId: str
    name: str
    createdAt: str | None = None
    updatedAt: str | None = None
    noteCount: int = 0
    measureCount: int = 0
    hasGeneratedTab: bool = False


class ProjectDetail(BaseModel):
    projectId: str
    name: str
    createdAt: str | None = None
    updatedAt: str | None = None
    notes: list[NoteSchema] = Field(default_factory=list)
    measures: list[MeasureSchema] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    generatedTab: dict[str, Any] | None = None
