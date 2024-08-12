import re
from dataclasses import dataclass
from collections import deque
from collections.abc import Iterator

from lua.lua_ast.exceptions import UnexpectedSymbolError


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
    def __init__(self, txt: str, pattern: str, skip_table: dict[str, bool]):
        self.__content = txt
        self.__iter = re.finditer(pattern, self.__content)
        self.__skip_table = skip_table
        self.__buffer: deque = deque()

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
            return self.__get_token()

        return self.__buffer.popleft()

    def peek(self, k: int = 0) -> Token:
        if k < len(self.__buffer):
            return self.__buffer[k]

        while len(self.__buffer) <= k:
            self.__buffer.append(self.__get_token())

        return self.__buffer[k]

    # allows to skip braced constructions like '(' exp ')'
    # index should point to start brace symbol
    # returns index of last stop brace symbol
    def peek_matching_parenthesis(self, start: str, stop: str, index: int = 0) -> int:
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
    LUA_TOKEN_PATTERNS = (
        TokenPattern("delimeter", r"[\s\n\r]+", ignore=True),
        TokenPattern(
            "comment",
            r"--(?:\[(?P<_eq>=*)\[[\s\S]*\](?P=_eq)\]|\n|[^[].*)",
            ignore=True,
        ),
        TokenPattern(
            "keyword",
            r"(?:false|local|then|break|for|nil|true|do|function|until|else|goto|while|elseif|if|repeat|end|in|return)\b",
        ),
        TokenPattern("other", r"\.{3}|::|:|\."),
        TokenPattern("op", r"not|and|or|<<|>>|//|==|~=|<=|>=|\.{2}|[+\-*%\^#&|<>=/~]"),
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
        TokenPattern("id", r"[A-Za-z_]\w*"),
        TokenPattern("EOF", r"\Z"),
    )

    def __init__(self):
        self.__final_pattern = (
            "|".join([f"(?P<{t.name}>{t.pattern})" for t in self.LUA_TOKEN_PATTERNS])
            + r"|."
        )
        self.__skip_names = {t.name: t.ignore for t in self.LUA_TOKEN_PATTERNS}

    def create_buffered_stream(self, txt: str) -> BufferedTokenStream:
        return BufferedTokenStream(txt, self.__final_pattern, self.__skip_names)

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

        prev_terminal = next(term_iter, None)

        if prev_terminal is None:
            yield ""
            return

        yield prev_terminal

        concat = prev_terminal[-1] in concat_syms

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
