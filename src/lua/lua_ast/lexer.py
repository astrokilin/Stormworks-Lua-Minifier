"""
This module provides everything connected with lexical structure of lua
"""

from re import finditer
from collections import deque
from dataclasses import dataclass

from lua.lua_ast.exceptions import UnexpectedSymbolError


@dataclass(eq=True, frozen=True, slots=True)
class Token:
    name: str
    content: str
    pos: int


@dataclass(slots=True)
class TokenPattern:
    name: str
    pattern: str
    ignore: bool = False


class BufferedTokenStream:
    """
    Iterator that returns tokens and supports lookahead for n tokens
    Fields:
        last_pos - position where last extracted token ends
    """

    __slots__ = "__content", "__iter", "__skip_table", "__buffer", "last_pos"

    def __init__(self, txt: str, pattern: str, skip_table: dict[str, bool]) -> None:
        self.__content = txt
        self.__iter = finditer(pattern, self.__content)
        self.__skip_table = skip_table
        self.__buffer: deque = deque()
        self.last_pos: int = 0

    def __get_token(self) -> Token:
        while True:
            match = next(self.__iter)

            if (matched_target := match.lastgroup) is None:
                raise UnexpectedSymbolError(match.group(0), match.span()[0])

            if self.__skip_table[matched_target]:
                continue

            return Token(matched_target, match.group(matched_target), match.span()[0])

    def __iter__(self):
        return self

    def __next__(self) -> Token:
        if not self.__buffer:
            t = self.__get_token()
        else:
            t = self.__buffer.popleft()

        self.last_pos = t.pos + len(t.content)
        return t

    def peek(self, k: int = 0) -> Token:
        """used to lookahead for k symbols
        does not change the iterator state
        """

        if k < len(self.__buffer):
            return self.__buffer[k]

        while len(self.__buffer) <= k:
            self.__buffer.append(self.__get_token())

        return self.__buffer[k]

    def peek_matching_parenthesis(self, start: str, stop: str, index: int = 0) -> int:
        """used to lookahead the braced constructions like '(' exp ')'

        index should point to opening brace symbol
        return index of last equal closing brace symbol
        """

        if (sym := self.peek(index).content) == start:
            stack = [
                sym,
            ]
            while stack:
                index += 1
                t = self.peek(index)
                sym = t.content
                if sym == start:
                    stack.append(sym)
                elif sym == stop:
                    stack.pop()
                elif t.name == "EOF":
                    return index

            return index + 1

        return index


class LuaLexer:
    """singleton class representing lua lexical rules"""

    __slots__ = "__final_pattern", "__skip_names"

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

    LUA_TOKEN_PATTERNS = (
        TokenPattern("delimeter", r"[\s\n\r]+", ignore=True),
        TokenPattern(
            "comment",
            r"--(?:\[(?P<_eq>=*)\[[\s\S]*\](?P=_eq)\]|\n|[^[].*)",
            ignore=True,
        ),
        TokenPattern(
            "keyword",
            (
                r"(?:(false|local|then|break|for|nil|true|do|function|until"
                r"|else|goto|while|elseif|if|repeat|end|in|return)(?![A-Za-z0-9_]))\b"
            ),
        ),
        TokenPattern("other", r"\.{3}|::|:"),
        TokenPattern(
            "op",
            r"(not|and|or)(?![A-Za-z0-9_])|<<|>>|//|==|~=|<=|>=|\.{2}|[+\-*%\^#&|<>=/~]",
        ),
        TokenPattern("dot", r"\."),
        TokenPattern(
            "string",
            r'"(?:[^"\\\n]|' +
            # escape sequence regex
            r"""\\(?:[abfnrtvz\\"']|x[a-fA-F0-9]{2}|[0-9]{1,3}|u{[a-fA-F0-9]+}|\n\s*)"""
            + r""")*"|'(?:[^'\\\n]|"""
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
            r"0[xX][a-fA-F0-9]+(?:\.[a-fA-F0-9]+)?(?:[pPeE][+-]?[a-fA-F0-9]+)?"
            + ")|(?:"
            +
            # dec num regex
            r"[0-9]+(?:\.[0-9]+)?(?:[pPeE][+-]?[0-9]+)?" + ")",
        ),
        TokenPattern("id", r"[A-Za-z_][A-Za-z0-9_]*"),
        TokenPattern("EOF", r"\Z"),
    )

    def __init__(self):
        self.__final_pattern = (
            "|".join([f"(?P<{t.name}>{t.pattern})" for t in self.LUA_TOKEN_PATTERNS])
            + r"|."
        )
        self.__skip_names = {t.name: t.ignore for t in self.LUA_TOKEN_PATTERNS}

    def create_buffered_stream(self, txt: str) -> BufferedTokenStream:
        """create token iterator from text string"""

        return BufferedTokenStream(txt, self.__final_pattern, self.__skip_names)

    @staticmethod
    def is_concat(sym_a: str, sym_b: str) -> bool:
        """
        given last char of first terminal (sym_a) and first char of last
        terminal (sym_b) should we place delimeter between them?
        """

        return (
            not (sym_a in LuaLexer.concat_syms or sym_b in LuaLexer.concat_syms)
            or sym_a == "."
            and sym_b == "."
        )
