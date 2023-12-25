import re
from dataclasses import dataclass
from typing import TextIO
from collections import deque
from collections.abc import Iterator


@dataclass(eq=True, frozen=True)
class Token:
    name: str
    content: str
    pos: int


@dataclass
class TokenPattern:
    name: str
    pattern: str
    ignore: bool = False


class BufferedTokenStream:
    def __init__(self, txt_file: TextIO, pattern: str, ignore_table: dict[str, bool]):
        self._content = txt_file.read()
        self._iter = re.finditer(pattern, self._content)
        self._table = ignore_table
        self.__buffer: deque = deque()

    def __get_token(self) -> Token:
        match = next(self._iter)
        matched_target = ""
        for target_name in self._table:
            if match.group(target_name) is not None:
                matched_target = target_name
                break

        if self._table[matched_target]:
            return self.__get_token()

        return Token(matched_target, match.group(matched_target), match.span()[0])

    def __iter__(self):
        return self

    def __next__(self) -> Token:
        if not self.__buffer:
            return self.__get_token()

        return self.__buffer.popleft()

    def peek(self, k: int = 0) -> Token:
        if k < len(self.__buffer):
            return self.__buffer[k]

        while len(self.__buffer) <= k:
            self.__buffer.append(self.__get_token())

        return self.__buffer[k]

    # ((line_number, line_offset), full string containing the error)
    def find_token(self, t: Token) -> tuple[tuple[int, int], str]:
        line_num = self._content.count("\n", 0, t.pos) + 1
        return (
            (
                line_num,
                t.pos - self._content[: t.pos].rfind("\n"),
            ),
            self._content.split("\n")[line_num - 1],
        )


class LuaLexer:
    LUA_TOKEN_PATTERNS = (
        TokenPattern("comment", r"(?:--\[\[[\s\S]*--\]\])|--[^\n]*", ignore=True),
        TokenPattern(
            "keyword",
            r"(?:false|local|then|break|for|nil|true|do|function|until|else|goto|while|elseif|if|repeat|end|in|return)\b",
        ),
        TokenPattern("other", r"\.{3}|::|:|\."),
        TokenPattern("op", r"not|and|or|<<|>>|//|==|~=|<=|>=|\.{2}|[+\-*%\^#&|<>=/]"),
        TokenPattern(
            "string",
            r'"(?:[^"\\\n]|' +
            # escape sequence regex
            r"""\\(?:[abfnrtvz\\"']|x[a-fA-F0-9]{2}|[0-9]{1,3}|u{[a-fA-F0-9]+}|\n\s*)"""
            + r""")*"|'(?:[^'\\\n]"""
            +
            # escape sequence regex
            r"""\\(?:[abfnrtvz\\"']|x[a-fA-F0-9]{2}|[0-9]{1,3}|u{[a-fA-F0-9]+}|\n\s*)"""
            + r")*'|(?:\[(?P<eq_sign>=*)\[[\s\S]*\](?P=eq_sign)\])",
        ),
        TokenPattern("punct", r"[(){}\[\];,]"),
        TokenPattern(
            "numeral",
            r"-?(?:" +
            # hex num regex
            r"0[xX][a-fA-F0-9]+(?:.[a-fA-F0-9]+)?(?:[pPeE][+-]?[a-fA-F0-9]+)?"
            + ")|(?:"
            +
            # dec num regex
            r"[0-9]+(?:.[0-9]+)?(?:[pPeE][+-]?[0-9]+)?" + ")",
        ),
        TokenPattern("id", r"[\w_][\w_\d]*"),
        TokenPattern("EOF", r"\Z"),
    )

    def __init__(self):
        self.__final_pattern = "".join(
            [f"(?P<{t.name}>{t.pattern})|" for t in self.LUA_TOKEN_PATTERNS]
        ).strip("|")
        self.__target_names_ignore = {t.name: t.ignore for t in self.LUA_TOKEN_PATTERNS}

    def create_buffered_stream(self, txt_file: TextIO) -> BufferedTokenStream:
        return BufferedTokenStream(
            txt_file, self.__final_pattern, self.__target_names_ignore
        )

    @staticmethod
    def concat(term_iter: Iterator[str]) -> Iterator[str]:
        concat_syms = {
            "+",
            "-",
            "*",
            "/",
            "%",
            "^",
            "#",
            "&",
            "~",
            "|",
            "<",
            ">",
            "=",
            "(",
            ")",
            "{",
            "}",
            "[",
            "]",
            ":",
            ";",
            ",",
            ".",
            "'",
            '"',
        }
        if (prev_terminal := next(term_iter, None)) is None:
            return ""

        concat = prev_terminal[-1] in concat_syms
        yield prev_terminal

        for terminal in term_iter:
            new_concat = terminal[-1] in concat_syms
            if (
                not (concat or new_concat)
                or prev_terminal[-1] == "."
                and terminal[-1] == "."
            ):
                yield " "

            yield terminal
            concat = new_concat
            prev_terminal = terminal
