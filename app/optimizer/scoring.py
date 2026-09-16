"""運指候補のスコアリング（設計書 7.2 / 7.4 / 8.3 / 9.2）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..domain.candidate import Candidate, EventPlacement
from ..domain.state import State


@dataclass
class ScoringWeights:
    """コストの重み。値が大きいほど「避けたい」動作になる。"""

    # 候補そのものの評価（設計書 7.2）
    base_fret_preference: float = 0.4
    high_fret_penalty: float = 1.5
    high_fret_threshold: int = 12
    open_string_bonus: float = 2.0

    # 遷移コスト（設計書 8.3）
    # ポジション内での弦移動は日常的な動作なので安く、手の移動は高く見積もる。
    # この配分により、音列がポジション内に収まる限り手を動かさない運指が選ばれる。
    #
    # position_changeは、曲全体でのポジション移動回数を最小化する目的で
    # 6から15に引き上げた（設計書 8.3）。値を上げるほど、多少ぎこちない
    # 指使いや弦選択になってでもポジションを維持する方向に倒れる。
    # 60曲のランダム旋律での検証では、6→15で移動回数が平均202→160回
    # (約21%減)に減り、15を超えると改善が鈍化する。
    fret_distance: float = 1.0
    position_change: float = 15.0
    string_change: float = 2.0
    large_hand_move: float = 12.0
    large_shift_threshold: int = 5
    same_finger_penalty: float = 4.0

    # 手の移動速度の限界（設計書 8.3.1）
    # 短い音符間で動かせるのは5フレットまで。時間があるほど許容量が増える。
    max_shift_short: int = 5
    shift_time_reference_beats: float = 1.0
    infeasible_shift_penalty: float = 40.0

    # 和音の押さえ方（設計書 9.2）
    chord_span_penalty: float = 2.0
    barre_penalty: float = 5.0
    non_index_barre_penalty: float = 10.0
    muted_string_penalty: float = 2.0
    string_crossing_penalty: float = 6.0

    # 探索
    beam_width: int = 24

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScoringWeights":
        if not data:
            return cls()
        known = set(cls().to_dict())
        return cls(**{key: value for key, value in data.items() if key in known})


def allowed_shift(available_beats: float, weights: ScoringWeights) -> float:
    """与えられた時間で手が移動できるフレット数の上限（設計書 8.3.1）。

    短い音価の間では max_shift_short フレットが限界で、時間があるほど比例して伸びる。
    """
    ratio = max(1.0, available_beats / weights.shift_time_reference_beats)
    return weights.max_shift_short * ratio


def base_cost(candidate: Candidate, weights: ScoringWeights) -> float:
    """候補単体のコスト。低いフレットと開放弦を優先する。

    弦の選好は、同じ音に対して「より低いフレットで押さえられる弦」を優先することで
    表現されるため、フレット選好に統合している。
    """
    cost = weights.base_fret_preference * candidate.fret
    if candidate.fret > weights.high_fret_threshold:
        cost += weights.high_fret_penalty * (candidate.fret - weights.high_fret_threshold)
    if candidate.is_open:
        cost -= weights.open_string_bonus
    return cost


def _muted_inner_strings(placement: EventPlacement) -> int:
    """鳴らす弦に挟まれた、鳴らさない弦の数（ミュートが必要になる）。"""
    strings = sorted(placement.strings)
    if len(strings) < 2:
        return 0
    return (strings[-1] - strings[0] + 1) - len(strings)


def _string_crossings(placement: EventPlacement) -> int:
    """低い弦に高い音が乗っている（弦をまたぐ）組み合わせの数。

    stringIndex 0 が最も高い弦なので、弦の番号が小さいほど音も高いのが自然な配置。
    """
    ordered = sorted(placement.candidates, key=lambda candidate: candidate.stringIndex)
    crossings = 0
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            if ordered[i].pitch < ordered[j].pitch:
                crossings += 1
    return crossings


def event_base_cost(placement: EventPlacement, weights: ScoringWeights) -> float:
    """イベント（単音または和音）そのもののコスト（設計書 7.2 / 9.2）。"""
    cost = sum(base_cost(candidate, weights) for candidate in placement.candidates)
    if len(placement.candidates) == 1:
        return cost

    fretted = placement.fretted
    if fretted:
        span = max(c.fret for c in fretted) - min(c.fret for c in fretted)
        cost += weights.chord_span_penalty * span
    if placement.barreFret is not None:
        cost += weights.barre_penalty
        if placement.barreFret != placement.handPosition:
            cost += weights.non_index_barre_penalty
    cost += weights.muted_string_penalty * _muted_inner_strings(placement)
    cost += weights.string_crossing_penalty * _string_crossings(placement)
    return cost


def event_transition_cost(
    state: State,
    placement: EventPlacement,
    weights: ScoringWeights,
    available_beats: float = 1.0,
) -> float:
    """直前の状態からイベントへ遷移するコスト（設計書 8.3）。

    前後どちらかが開放弦のみの場合、フレット移動・ポジション移動・手の移動は
    発生しないものとして扱う（設計書 7.4）。
    """
    if not state.previousPlacements:
        return 0.0

    previous_fretted = [fret for fret in state.previous_frets if fret > 0]
    open_involved = placement.is_all_open or not previous_fretted

    if open_involved:
        fret_distance = 0
    else:
        fret_distance = abs(min(previous_fretted) - placement.anchor_fret)

    too_fast_penalty = 0.0
    if open_involved or state.handPosition is None or placement.handPosition is None:
        position_change = 0
        large_hand_move = 0
    else:
        shift = abs(state.handPosition - placement.handPosition)
        position_change = shift
        large_hand_move = 1 if shift >= weights.large_shift_threshold else 0
        limit = allowed_shift(available_beats, weights)
        if shift > limit:
            too_fast_penalty = weights.infeasible_shift_penalty * (shift - limit)

    string_change = 1 if state.previous_strings != placement.strings else 0

    finger_conflict = 0.0
    if not open_involved:
        previous_fingers = {
            finger: fret for _, fret, finger in state.previousPlacements if finger > 0
        }
        for candidate in placement.fretted:
            previous_fret = previous_fingers.get(candidate.finger)
            if previous_fret is not None and previous_fret != candidate.fret:
                finger_conflict += weights.same_finger_penalty

    return (
        weights.fret_distance * fret_distance
        + weights.position_change * position_change
        + weights.string_change * string_change
        + weights.large_hand_move * large_hand_move
        + finger_conflict
        + too_fast_penalty
    )


def transition_cost(
    state: State,
    candidate: Candidate,
    weights: ScoringWeights,
    available_beats: float = 1.0,
) -> float:
    """単音の遷移コスト（設計書 8.3）。イベント版に委譲する。"""
    placement = EventPlacement(candidates=(candidate,), handPosition=candidate.handPosition)
    return event_transition_cost(state, placement, weights, available_beats)
