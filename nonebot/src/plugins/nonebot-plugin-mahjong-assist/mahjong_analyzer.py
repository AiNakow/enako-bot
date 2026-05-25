from pydantic import BaseModel, Field
from functools import lru_cache
import re
import time

TILES_34 = [
    "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "1z", "2z", "3z", "4z", "5z", "6z", "7z"
    ]

TILE_INDEX = {tile: i for i, tile in enumerate(TILES_34)}

class MahjongHandError(Exception):
    """手牌格式错误"""
    pass

class TileInfo(BaseModel):
    id: str
    remaining: int

class DiscardInfo(BaseModel):
    discard: TileInfo
    total_waits: int = 0
    good_shape_count: int = 0
    good_shape_draws: list[str] = Field(default_factory=list)
    waits: list[TileInfo] = []

class AnalysisResult(BaseModel):
    kind: str = "discard"   # discard / draw
    tile_count: int = 0
    hand: list[str] = []
    shanten: int = 8
    is_tenpai: bool = False
    is_agari: bool = False
    total_draws: int = 0
    good_shape_count: int = 0
    good_shape_draws: list[str] = Field(default_factory=list)
    discards: list[DiscardInfo] = []
    draws: list[TileInfo] = []

def is_valid_handstr(hand_str: str) -> bool:
    hand_str = hand_str.strip()
    if not hand_str:
        return False
    
    if not re.fullmatch(r'^(\d+[mps]|[1-7]+z)+$', hand_str):
        return False
    
    hand_list = []
    groups = re.findall(r'(\d+[mpsz])', hand_str)
    for group in groups:
        hand_list.extend(n + group[-1] for n in group[:-1])

    count = len(hand_list)
    if count > 14:
        return False
    if count % 3 == 2:
        if count // 3 == 0:
            return False
    elif count % 3 == 0:
        return False

    tile_counter = {}
    for tile in hand_list:
        if tile not in tile_counter:
            tile_counter[tile] = 0
        tile_counter[tile] += 1

    for count in tile_counter.values():
        if count > 4:
            return False
        
    return True


def str_to_count(hand_str: str) -> list[int]:
    hand_list = []
    groups = re.findall(r'(\d+[mpsz])', hand_str)
    for group in groups:
        hand_list.extend(n + group[-1] for n in group[:-1])

    hand_count = [0] * 34
    for tile in hand_list:
        hand_count[TILE_INDEX[tile]] += 1

    return hand_count

def str_to_list(hand_str: str) -> list[str]:
    hand_list = []
    groups = re.findall(r'(\d+[mpsz])', hand_str)
    for group in groups:
        hand_list.extend(n + group[-1] for n in group[:-1])

    return hand_list

@lru_cache(maxsize=None)
def analyze_block(block_count: tuple[int, ...], allow_sequence: bool) -> frozenset[tuple[int, int, int]]:
    result = set()

    def search(current_count: list[int], start: int, melds: int, taatsu: int, pairs: int, remaining_count: int):
        nonlocal result
        if remaining_count == 0:
            result.add((melds, taatsu, min(pairs, 1)))
            return
        
        index = start
        while index < len(current_count) and current_count[index] == 0:
            index += 1

        # 刻子
        if current_count[index] >= 3:
            current_count[index] -= 3
            search(current_count, index, melds + 1, taatsu, pairs, remaining_count - 3)
            current_count[index] += 3

        # 顺子
        if allow_sequence and index <= 6 and current_count[index + 1] > 0 and current_count[index + 2] > 0:
            current_count[index] -= 1
            current_count[index + 1] -= 1
            current_count[index + 2] -= 1
            search(current_count, index, melds + 1, taatsu, pairs, remaining_count - 3)
            current_count[index] += 1
            current_count[index + 1] += 1
            current_count[index + 2] += 1

        # 相邻搭子
        if allow_sequence and index <= 7 and current_count[index + 1] > 0:
            current_count[index] -= 1
            current_count[index + 1] -= 1
            search(current_count, index, melds, taatsu + 1, pairs, remaining_count - 2)
            current_count[index] += 1
            current_count[index + 1] += 1

        # 坎张搭子
        if allow_sequence and index <= 6 and current_count[index + 2] > 0:
            current_count[index] -= 1
            current_count[index + 2] -= 1
            search(current_count, index, melds, taatsu + 1, pairs, remaining_count - 2)
            current_count[index] += 1
            current_count[index + 2] += 1

        # 对子搭子
        if current_count[index] >= 2:
            current_count[index] -= 2
            search(current_count, index, melds, taatsu + 1, pairs, remaining_count - 2)
            current_count[index] += 2

        # 雀头
        if current_count[index] >= 2:
            current_count[index] -= 2
            search(current_count, index, melds, taatsu, pairs + 1, remaining_count - 2)
            current_count[index] += 2

        # 孤张
        current_count[index] -= 1
        search(current_count, index, melds, taatsu, pairs, remaining_count - 1)
        current_count[index] += 1

    search(list(block_count), 0, 0, 0, 0, sum(block_count))
    return frozenset(result)


def prune_states(states):
    best = {}

    for m, t, p in states:
        key = (m, p)
        if key not in best or t > best[key]:
            best[key] = t

    return {(m, t, p) for (m, p), t in best.items()}


def calculate_standard_shanten_dp(hand_count: list[int] | tuple[int, ...]) -> int:
    hand_count = tuple(hand_count)
    m = tuple(hand_count[0:9])
    p = tuple(hand_count[9:18])
    s = tuple(hand_count[18:27])
    z = tuple(hand_count[27:34])

    m_states = analyze_block(m, True)
    p_states = analyze_block(p, True)
    s_states = analyze_block(s, True)
    z_states = analyze_block(z, False)

    target_melds = sum(hand_count) // 3
    states = {(0, 0, 0)}
    for block_states in [m_states, p_states, s_states, z_states]:
        next_states = set()

        for a in states:
            for b in block_states:
                melds = min(a[0] + b[0], target_melds)
                taatsu = min(a[1] + b[1], target_melds - melds)
                pairs = min(1, a[2] + b[2])

                next_states.add((melds, taatsu, pairs))

        states = prune_states(next_states)

    best_shanten = 8
    for melds, taatsu, pairs in states:
        useful_taatsu = min(taatsu, target_melds - melds)
        best_shanten = min(best_shanten, 2 * target_melds - 2 * melds - useful_taatsu - min(pairs, 1))

    return best_shanten

def calculate_chiitoi_shanten(hand_count: list[int] | tuple[int, ...]) -> int:
    # 七对子向听 = 6 - 有效对子数
    return 6 - sum(1 for n in hand_count if n // 2 > 0)


def calculate_kokushi_shanten(hand_count: list[int] | tuple[int, ...]) -> int:
    # 国士无双向听 = 13 - 不同幺九数 - max(1, 幺九对子)
    yao_jiu_list = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    pair = 0
    for i in yao_jiu_list:
        if hand_count[i] // 2 > 0:
            pair = 1
            break

    return 13 - sum(1 for i in yao_jiu_list if hand_count[i] > 0) - pair

def analyze_draws(hand_count: list[int] | tuple[int, ...], mode: int, shanten_cache: dict | None = None) -> int:
    hand_count_key = tuple(hand_count)
    cache_key = (hand_count_key, mode)
    if shanten_cache is not None and cache_key in shanten_cache:
        return shanten_cache[cache_key]

    stantard_shanten = calculate_standard_shanten_dp(hand_count_key)
    if mode == 0:
        chiitoi_shanten = calculate_chiitoi_shanten(hand_count_key)
        kokushi_shanten = calculate_kokushi_shanten(hand_count_key)
        result = min(stantard_shanten, chiitoi_shanten, kokushi_shanten)
    else:
        result = stantard_shanten

    if shanten_cache is not None:
        shanten_cache[cache_key] = result

    return result

def get_draws(hand_count: list[int], shanten: int, mode: int, shanten_cache: dict | None = None) -> list[TileInfo]:
    draws = []
    for i in range(len(hand_count)):
        if hand_count[i] >= 4:
            continue

        hand_count[i] += 1
        new_shanten = analyze_draws(hand_count, mode, shanten_cache)
        hand_count[i] -= 1
        if new_shanten < shanten:
            draws.append(
                TileInfo(
                    id=TILES_34[i],
                    remaining=4 - hand_count[i]
                )
            )

    return draws

def has_more_waits_than(hand_count: list[int], shanten: int, mode: int, limit: int, shanten_cache: dict | None = None) -> bool:
    total_waits = 0
    for i in range(len(hand_count)):
        if hand_count[i] >= 4:
            continue

        hand_count[i] += 1
        new_shanten = analyze_draws(hand_count, mode, shanten_cache)
        hand_count[i] -= 1
        if new_shanten < shanten:
            total_waits += 4 - hand_count[i]
            if total_waits > limit:
                return True

    return False

def get_good_shape_count(hand_count: list[int], draws, shanten: int, mode: int, shanten_cache: dict | None = None) -> tuple[int, list[str]]:
    good_shape_count = 0
    good_shape_draws = []
    for draw in draws:
        draw_index = TILE_INDEX[draw.id]
        hand_count[draw_index] += 1
        for i in range(len(hand_count)):
            if hand_count[i] <= 0:
                continue
            hand_count[i] -= 1
            has_good_waits = has_more_waits_than(hand_count, shanten - 1, mode, 4, shanten_cache)
            hand_count[i] += 1

            if has_good_waits:
                good_shape_count += draw.remaining
                good_shape_draws.append(draw.id)
                break
        hand_count[draw_index] -= 1

    return good_shape_count, good_shape_draws
        

def analyze_hand(hand_str: str, mode: int = 0) -> AnalysisResult:
    if not is_valid_handstr(hand_str):
        raise MahjongHandError(f"非法手牌：{hand_str}")
    
    shanten_cache = {}
    analysis_result = AnalysisResult()

    hand_count = str_to_count(hand_str)
    tile_count = sum(hand_count)
    analysis_result.tile_count = tile_count
    analysis_result.hand = str_to_list(hand_str)

    if tile_count % 3 == 1:
        analysis_result.kind = "draw"
        analysis_result.shanten = analyze_draws(hand_count, mode, shanten_cache)
        analysis_result.draws = get_draws(hand_count, analysis_result.shanten, mode, shanten_cache)
        analysis_result.is_tenpai = True if analysis_result.shanten <= 0 else False
        analysis_result.total_draws = sum(draw.remaining for draw in analysis_result.draws)
        if analysis_result.shanten == 1:
            analysis_result.good_shape_count, analysis_result.good_shape_draws = get_good_shape_count(hand_count, analysis_result.draws, analysis_result.shanten, mode, shanten_cache)

    elif tile_count % 3 == 2:
        analysis_result.kind = "discard"
        discards_shanten = [8] * 34
        best_shanten = 8
        for i in range(len(hand_count)):
            if hand_count[i] <= 0:
                continue

            hand_count[i] -= 1
            discards_shanten[i] = analyze_draws(hand_count, mode, shanten_cache)
            hand_count[i] += 1
            best_shanten = min(best_shanten, discards_shanten[i])

        discards = []
        for i in range(len(discards_shanten)):
            if discards_shanten[i] == best_shanten and hand_count[i] > 0:
                discard_info = DiscardInfo(
                    discard=TileInfo(
                        id=TILES_34[i],
                        remaining=4 - hand_count[i]
                    )
                )

                hand_count[i] -= 1
                discard_info.waits = get_draws(hand_count, best_shanten, mode, shanten_cache)
                hand_count[i] += 1

                for j in range(len(discard_info.waits)):
                    if discard_info.waits[j].id == TILES_34[i]:
                        discard_info.waits[j].remaining -= 1
                        break

                discard_info.total_waits = sum(wait.remaining for wait in discard_info.waits)

                discards.append(discard_info)
        
        analysis_result.shanten = best_shanten

        if analysis_result.shanten == 1:
            for i, discard in enumerate(discards):
                draws = discard.waits
                discard_index = TILE_INDEX[discard.discard.id]
                hand_count[discard_index] -= 1
                discards[i].good_shape_count, discards[i].good_shape_draws = get_good_shape_count(hand_count, draws, analysis_result.shanten, mode, shanten_cache)
                hand_count[discard_index] += 1

        analysis_result.discards = sorted(discards, key=lambda p: p.total_waits, reverse=True)
        analysis_result.is_tenpai = True if analysis_result.shanten <= 0 else False
        analysis_result.is_agari = True if analyze_draws(hand_count, mode, shanten_cache) < 0 else False
        

    return analysis_result

    
if __name__ == "__main__":
    hand_str: str = "3456m3455p123788s"
    start_time = time.perf_counter()
    analysis_result = analyze_hand(hand_str, 0)
    elapsed_time = time.perf_counter() - start_time

    print(analysis_result.model_dump_json())
    print(f"Calculation time: {elapsed_time:.6f}s")
