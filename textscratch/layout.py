import re
from typing import Any, Dict, List, Optional, Tuple

from .opcodes import CONTROL_BLOCKS, OPCODE_MAP

# Layout tuning constants for auto-arranging top-level stacks
BLOCK_BASE_WIDTH = 220
BLOCK_BASE_HEIGHT = 40
BLOCK_LABEL_CHAR_WIDTH = 6
STACK_GAP = 12
BRANCH_GAP = 12
CLAUSE_GAP = 16
INDENT_WIDTH = 28
ARRANGE_GAP_X = 80
ARRANGE_GAP_Y = 40
TARGET_RATIO = 0.5
RATIO_WEIGHT = 2.5
# Bracket (C-shaped) blocks have thinner end caps; scale their height to fit.
BRACKET_HEIGHT_SCALE = 1.66


def _extract_stack_id(input_entry: Any) -> Optional[str]:
    if not input_entry:
        return None
    if isinstance(input_entry, list) and len(input_entry) >= 2 and isinstance(input_entry[1], str):
        return input_entry[1]
    return None


def _estimate_label_width(block: Dict[str, Any]) -> int:
    opcode = block.get("opcode", "")
    fmt = OPCODE_MAP.get(opcode, opcode)
    label_text = re.sub(r"\{[^}]+\}", "", fmt)
    return max(BLOCK_BASE_WIDTH, BLOCK_LABEL_CHAR_WIDTH * len(label_text) + 80)


def _block_size(
    block_id: str,
    blocks: Dict[str, Dict[str, Any]],
    stack_cache: Dict[str, Tuple[int, int]],
    block_cache: Dict[str, Tuple[int, int]],
) -> Tuple[int, int]:
    if block_id in block_cache:
        return block_cache[block_id]

    block = blocks.get(block_id, {})
    width = _estimate_label_width(block)
    height = BLOCK_BASE_HEIGHT

    inputs = block.get("inputs", {}) or {}

    substack_id = _extract_stack_id(inputs.get("SUBSTACK") or inputs.get("substack"))
    if substack_id:
        child_w, child_h = _stack_size(substack_id, blocks, stack_cache, block_cache)
        width = max(width, child_w + INDENT_WIDTH)
        height += BRANCH_GAP + child_h

    substack2_id = _extract_stack_id(inputs.get("SUBSTACK2") or inputs.get("substack2"))
    if substack2_id:
        child_w2, child_h2 = _stack_size(substack2_id, blocks, stack_cache, block_cache)
        width = max(width, child_w2 + INDENT_WIDTH)
        height += CLAUSE_GAP + child_h2

    if block.get("opcode") in CONTROL_BLOCKS:
        height = int(height * BRACKET_HEIGHT_SCALE)

    block_cache[block_id] = (width, height)
    return width, height


def _stack_size(
    start_id: str,
    blocks: Dict[str, Dict[str, Any]],
    stack_cache: Dict[str, Tuple[int, int]],
    block_cache: Dict[str, Tuple[int, int]],
) -> Tuple[int, int]:
    if start_id in stack_cache:
        return stack_cache[start_id]

    total_height = 0
    max_width = 0
    current = start_id
    visited: set = set()

    while current and current not in visited:
        visited.add(current)
        block_width, block_height = _block_size(current, blocks, stack_cache, block_cache)
        total_height += block_height
        next_id = blocks.get(current, {}).get("next")
        if next_id:
            total_height += STACK_GAP
        max_width = max(max_width, block_width)
        current = next_id

    stack_cache[start_id] = (max_width, total_height)
    return max_width, total_height


def auto_arrange_top_blocks(blocks: Dict[str, Dict[str, Any]]) -> None:
    top_blocks = [bid for bid, blk in blocks.items() if blk.get("topLevel")]
    if not top_blocks:
        return

    block_cache: Dict[str, Tuple[int, int]] = {}
    stack_cache: Dict[str, Tuple[int, int]] = {}
    sizes: List[Tuple[str, int, int, int]] = []

    for order, bid in enumerate(top_blocks):
        width, height = _stack_size(bid, blocks, stack_cache, block_cache)
        sizes.append((bid, width, height, order))

    best_layout: Optional[Tuple[float, List[List[Tuple[str, int, int, int]]], List[int], List[int], int, int]] = None
    max_cols = max(1, min(len(sizes), 5))
    script_gap = ARRANGE_GAP_Y * 3
    script_gap_x = ARRANGE_GAP_X * 3

    for cols in range(1, max_cols + 1):
        columns: List[List[Tuple[str, int, int, int]]] = [[] for _ in range(cols)]
        col_heights = [0 for _ in range(cols)]

        for entry in sorted(sizes, key=lambda item: item[2], reverse=True):
            bid, width, height, order = entry
            target_col = min(range(cols), key=lambda idx: col_heights[idx])
            if columns[target_col]:
                col_heights[target_col] += script_gap
            col_heights[target_col] += height
            columns[target_col].append((bid, width, height, order))

        col_widths = [max((item[1] for item in col), default=0) for col in columns]
        total_width = sum(col_widths) + script_gap_x * (cols - 1)
        total_height = max(col_heights) if col_heights else 0
        ratio = total_width / total_height if total_height else 1.0
        area = total_width * total_height
        score = area * (1 + RATIO_WEIGHT * abs(ratio - TARGET_RATIO))

        if best_layout is None or score < best_layout[0]:
            best_layout = (score, columns, col_widths, col_heights, total_width, total_height)

    if not best_layout:
        return

    _, chosen_columns, col_widths, col_heights, total_width, total_height = best_layout

    y_scale = 1.0
    x_offset = 40
    y_offset = 40

    x = x_offset
    for col_width, col_height, column in zip(col_widths, col_heights, chosen_columns):
        y = y_offset
        for bid, _, height, order in sorted(column, key=lambda item: item[3]):
            blk = blocks.get(bid, {})
            blk["x"] = x
            blk["y"] = int(y)
            y += (height + script_gap) * y_scale
        x += col_width + script_gap_x


def clear_block_positions(blocks: Dict[str, Dict[str, Any]]) -> None:
    """Remove x/y coordinates so the editor can place stacks itself."""
    for blk in blocks.values():
        blk.pop("x", None)
        blk.pop("y", None)
