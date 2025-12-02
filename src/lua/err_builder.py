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
            0,
        ]

        for i, ch in enumerate(text):
            if ch == "\n":
                positions.append(i)

        positions.append(len(text))

        self.__positions = positions
        self.__text = text

    def build_error(self, text_offset: int, err_length: int, explanation: str) -> str:
        """
        Takes subtext (text[text_offset: text_offset + err_length]) and explanation
        forms error string from it
        """

        line_num: int = bisect_left(self.__positions, text_offset)
        line_start_offset: int = self.__positions[line_num - 1] + 1
        row_num: int = text_offset - line_start_offset
        lines: list[str] = self.__text[
            line_start_offset : self.__positions[
                bisect_left(self.__positions, text_offset + err_length)
            ]
        ].split("\n")
        explanation = f"({line_num}, {row_num + 1}): {explanation}"

        if len(lines) > 1:
            l_first = lines[0].rstrip().replace("\t", " ")
            return "\n".join(
                chain(
                    (f" {l_first}\n|{' ' * row_num}{'^' * (len(l_first) - row_num)}",),
                    (f"|{x.replace('\t', ' ')}" for x in lines[1:-1]),
                    (
                        f"|{lines[-1].rstrip().replace('\t', ' ')}\n {'^' * (err_length - sum(map(len, lines[:-1])) - len(lines) + row_num + 1)}\n{explanation}",
                    ),
                )
            )

        return f"{lines[0].rstrip().replace('\t', ' ')}\n{' ' * row_num}{'^' * err_length}\n{explanation}"
