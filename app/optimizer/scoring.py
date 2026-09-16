"""運指候補のスコアリング（設計書 7.2 / 7.4 / 8.3）。"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from ..domain.candidate import Candidate
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
    fret_distance: float = 1.0
    position_change: float = 6.0
    string_change: float = 2.0
    large_hand_move: float = 12.0
    large_shift_threshold: int = 5
    same_finger_penalty: float = 4.0

    # 手の移動速度の限界（設計書 8.3.1）
    # 短い音符間で動かせるのは5フレットまで。時間があるほど許容量が増える。
    max_shift_short: int = 5
    shift_time_reference_beats: float = 1.0
    infeasible_shift_penalty: float = 40.0

    # 探索
    beam_width: int = 24

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScoringWeights":
        if not data:
            return cls()
        known = {f for f in cls().to_dict()}
        return cls(**{k: v for k, v in data.items() if k in known})


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


def allowed_shift(available_beats: float, weights: ScoringWeights) -> float:
    """与えられた時間で手が移動できるフレット数の上限（設計書 8.3.1）。

    短い音価の間では max_shift_short フレットが限界で、時間があるほど比例して伸びる。
    """
    ratio = max(1.0, available_beats / weights.shift_time_reference_beats)
    return weights.max_shift_short * ratio


def transition_cost(
    state: State,
    candidate: Candidate,
    weights: ScoringWeights,
    available_beats: float = 1.0,
) -> float:
    """直前の状態から候補へ遷移するコスト（設計書 8.3）。

    前後どちらかが開放弦の場合、フレット移動・ポジション移動・手の移動は発生しない
    ものとして扱う（設計書 7.4）。
    """
    if state.previousString is None:
        return 0.0

    open_involved = candidate.is_open or state.previousFret == 0

    fret_distance = 0 if open_involved else abs((state.previousFret or 0) - candidate.fret)

    too_fast_penalty = 0.0
    if open_involved or state.handPosition is None or candidate.handPosition is None:
        position_change = 0
        large_hand_move = 0
    else:
        shift = abs(state.handPosition - candidate.handPosition)
        position_change = shift
        large_hand_move = 1 if shift >= weights.large_shift_threshold else 0
        limit = allowed_shift(available_beats, weights)
        if shift > limit:
            too_fast_penalty = weights.infeasible_shift_penalty * (shift - limit)

    string_change = 1 if state.previousString != candidate.stringIndex else 0

    finger_conflict = 0.0
    if (
        not open_involved
        and state.previousFinger == candidate.finger
        and state.previousFret != candidate.fret
    ):
        finger_conflict = weights.same_finger_penalty

    return (
        weights.fret_distance * fret_distance
        + weights.position_change * position_change
        + weights.string_change * string_change
        + weights.large_hand_move * large_hand_move
        + finger_conflict
        + too_fast_penalty
    )
