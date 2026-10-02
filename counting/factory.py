from typing import List

from .counter import LineCounter, VirtualLine


def build_counter(config: dict) -> LineCounter:
    lines: List[VirtualLine] = [
        VirtualLine(
            line_id=item["line_id"],
            coords=tuple(item["coords"]),
            direction_pos_to_neg=item.get("direction_pos_to_neg", "in"),
            direction_neg_to_pos=item.get("direction_neg_to_pos", "out"),
            use_point=item.get("use_point", "bottom_center"),
        )
        for item in config["VIRTUAL_LINES"]
    ]
    return LineCounter(lines=lines, **config["COUNTING_PARAMS"])

