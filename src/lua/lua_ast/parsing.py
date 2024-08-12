from __future__ import annotations
from collections.abc import Generator, KeysView, Callable
from typing import Any, TypeVar

from lua.lua_ast.lexer import LuaLexer, Token, BufferedTokenStream
from lua.lua_ast.exceptions import WrongTokenError


ParsableFirstTokenType = set[str] | KeysView[str]

T = TypeVar("T", bound="Parsable")


class Parsable:
    PARSABLE_FIRST_TOKEN_CONTENTS: ParsableFirstTokenType = set()
    PARSABLE_FIRST_TOKEN_NAMES: ParsableFirstTokenType = set()

    PARSABLE_ERROR_NAME: str = ""

    PARSABLE_MARK_POS: bool = False

    __slots__ = ()

    # this method should construct node from parser.token_stream
    # changes parser state
    # should be called only when u can guarantee that it will get right first token
    @classmethod
    def parsable_from_parser(cls: type[T], parser: LuaParser) -> T:
        next(parser.token_stream)
        return cls()

    # since this method should not change the stream state
    # it can be called directly during parsing
    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        t = stream.peek(index)
        return (
            t.content in cls.PARSABLE_FIRST_TOKEN_CONTENTS
            or t.name in cls.PARSABLE_FIRST_TOKEN_NAMES
        )


# to determine some nodes we need to skip n tokens in stream
# thus skiping the nodes
class ParsableSkipable(Parsable):
    # skips enought tokens in stream to skip the node, returns index of
    # first token that is not cls node
    # should not change the stream state
    # can be called directly during parsing
    @classmethod
    def parsable_skip_in_stream(cls, stream: BufferedTokenStream, index: int) -> int:
        return index + 1


ParsableType = type[Parsable]


# decorator that help to form correct FIRST_TOKEN fields for
# parsable type that starts with another parsable when parsing
def parsable_starts_with(
    *starting_nonterms: ParsableType,
) -> Callable[[ParsableType], ParsableType]:
    def decorate(orig_class: ParsableType):
        for nonterm_class in starting_nonterms:
            # I guess sometimes we can just link
            # to a existing set without creating a copy
            if not orig_class.PARSABLE_FIRST_TOKEN_CONTENTS:
                orig_class.PARSABLE_FIRST_TOKEN_CONTENTS = (
                    nonterm_class.PARSABLE_FIRST_TOKEN_CONTENTS
                )
            elif nonterm_class.PARSABLE_FIRST_TOKEN_CONTENTS:
                orig_class.PARSABLE_FIRST_TOKEN_CONTENTS |= (
                    nonterm_class.PARSABLE_FIRST_TOKEN_CONTENTS
                )

            if not orig_class.PARSABLE_FIRST_TOKEN_NAMES:
                orig_class.PARSABLE_FIRST_TOKEN_NAMES = (
                    nonterm_class.PARSABLE_FIRST_TOKEN_NAMES
                )
            elif nonterm_class.PARSABLE_FIRST_TOKEN_NAMES:
                orig_class.PARSABLE_FIRST_TOKEN_NAMES |= (
                    nonterm_class.PARSABLE_FIRST_TOKEN_NAMES
                )

        return orig_class

    return decorate


# adds dupclicates to dict src
# store values with the same key in a list
def _dict_add_duplicates(src: dict, keys: ParsableFirstTokenType, value: Any):
    overlap = src.keys() & keys
    for unit in overlap:
        if type(src[unit]) is list:
            src[unit].append(value)

        else:
            src[unit] = [src[unit], value]

    src |= dict.fromkeys(keys - overlap, value)


class TokenDispatchTable:
    __slots__ = "contents", "names"

    def __init__(self, contents: dict[str, Any], names: dict[str, Any]):
        self.contents = contents
        self.names = names

    # makes class dispatch table from parsable classes and their
    # PARSABLE_FIRST_TOKEN_CONTENTS and PARSABLE_FIRST_TOKEN_NAMES
    # if we have 2 classes starting with same content or name
    # will return list with these classes
    @classmethod
    def dispatch_types(cls, *parsable_classes: ParsableType):
        contents: dict[str, ParsableType] = {}
        names: dict[str, ParsableType] = {}

        for n_cls in parsable_classes:
            _dict_add_duplicates(contents, n_cls.PARSABLE_FIRST_TOKEN_CONTENTS, n_cls)
            _dict_add_duplicates(names, n_cls.PARSABLE_FIRST_TOKEN_NAMES, n_cls)

        return cls(contents, names)

    def __contains__(self, token: Token) -> bool:
        return token.content in self.contents or token.name in self.names

    def __getitem__(self, token: Token) -> Any:
        return self.names.get(token.name, self.contents.get(token.content))


class LuaParser:
    LEXER = LuaLexer()

    def __init__(self, txt: str):
        self.token_stream: BufferedTokenStream = self.LEXER.create_buffered_stream(txt)
        # id(node): position in file
        self.positions_map: dict[int, int] = dict()

    def parse_terminal(
        self,
        expected_value: str,
        prev_err_name: str,
        err_name: str = "",
    ):
        if (t := next(self.token_stream)).content != expected_value:
            raise WrongTokenError(
                t.content,
                t.pos,
                err_name if err_name else f"'{expected_value}'",
                prev_err_name,
            )

    def parse_parsable(
        self,
        parsable_type: type[T],
        prev_err_name: str = "",
        greedy: bool = False,
        err_name: str = "",
    ) -> T:
        stream = self.token_stream

        if greedy and not parsable_type.parsable_presented_in_stream(stream):
            t = next(stream)
            raise WrongTokenError(
                t.content,
                t.pos,
                err_name if err_name else parsable_type.PARSABLE_ERROR_NAME,
                prev_err_name,
            )

        pos = stream.peek().pos
        res = parsable_type.parsable_from_parser(self)

        if parsable_type.PARSABLE_MARK_POS:
            self.positions_map[id(res)] = pos

        return res

    # used to parse constructions like
    # nonterm separator nonterm ....
    # non_empty - extract at least 1 element
    def parse_list(
        self,
        parsable_type: type[T],
        separators: set[str] = {","},
        non_empty: bool = False,
        error_name: str = "",
        greedy: bool = False,
    ) -> Generator[T, None, None]:
        stream = self.token_stream

        if non_empty:
            yield self.parse_parsable(parsable_type, error_name, True)

        elif parsable_type.parsable_presented_in_stream(stream):
            yield self.parse_parsable(parsable_type)

        else:
            return

        while stream.peek().content in separators:
            if parsable_type.parsable_presented_in_stream(stream, 1):
                next(stream)
                yield self.parse_parsable(parsable_type)

            elif not greedy:
                break

            else:
                error_name = f"'{next(stream).content}'"
                t = next(stream)
                raise WrongTokenError(
                    t.content, t.pos, parsable_type.PARSABLE_ERROR_NAME, error_name
                )

    # used to parse simple rules
    # like sequences of terms and nonterms
    def parse_simple_rule(
        self,
        rule: tuple[ParsableType | str, ...],
        error_name: str = "",
    ) -> Generator[Any, None, None]:
        for unit in rule:
            if isinstance(unit, str):
                self.parse_terminal(unit, error_name)
                error_name = unit
            else:
                yield self.parse_parsable(unit, error_name, True)
                error_name = unit.PARSABLE_ERROR_NAME
