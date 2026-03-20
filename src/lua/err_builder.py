"""
This module provides tools for error strings construction
"""

from itertools import chain
from bisect import bisect_left


class ErrBuilder:
    """
    Builds error strings containing parts of original text
    """

    def __init__(self, text: str) -> None:
        positions: list[int] = [
            -1,
        ]

        for i, ch in enumerate(text):
            if ch == "\n":
                positions.append(i)

        positions.append(len(text))

        self.__positions = positions
        self.__text = text

    def build_error(
        self, text_start_index: int, text_end_index: int, explanation: str
    ) -> str:
        """
        Takes subtext (text[text_start_index: text_end_index]) and explanation
        forms error string from it
        """

        err_length: int = text_end_index - text_start_index
        line_num: int = bisect_left(self.__positions, text_start_index)
        line_start_offset: int = (
            self.__positions[line_num - 1 if line_num > 0 else 0] + 1
        )

        row_num: int = text_start_index - line_start_offset
        line_end: int = bisect_left(self.__positions, text_end_index)
        lines: list[str] = self.__text[
            line_start_offset : self.__positions[
                (
                    line_end
                    if line_end < len(self.__positions)
                    else len(self.__positions) - 1
                )
            ]
        ].split("\n")
        explanation = f"({line_num}, {row_num + 1}): {explanation}"

        l_first = lines[0].rstrip().replace("\t", " ")

        if len(lines) > 1:
            l_last = lines[-1].rstrip().replace("\t", " ")
            last_part_len = (
                err_length - sum(map(len, lines[:-1])) - len(lines) + row_num + 1
            )
            return "\n".join(
                chain(
                    (f" {l_first}\n|{' ' * row_num}{'^' * (len(l_first) - row_num)}",),
                    ("|" + x.replace("\t", " ") for x in lines[1:-1]),
                    (f"|{l_last}\n {'^' * last_part_len}\n{explanation}",),
                )
            )

        return f"{l_first}\n{' ' * row_num}{'^' * err_length}\n{explanation}"
