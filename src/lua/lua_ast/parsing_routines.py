from collections.abc import Generator
from typing import Any

from lua.lua_ast.lexer import Token, BufferedTokenStream
from lua.lua_ast.exceptions import WrongTokenError
from lua.lua_ast.ast_nodes.base_nodes import AstNode, NodeFirst, AstNodeType

# adds dupclicates to dict src
# store values with the same key in a list


def _dict_add_duplicates(src: dict, keys: NodeFirst, value: Any):
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

    # makes class dispatch table from classes and their
    # FIRST_CONTENTS and FIRST_NAMES
    # if we have 2 classes starting with same content or name
    # will return list with these classes

    @classmethod
    def dispatch_types(cls, *node_classes: type[AstNodeType]):
        contents: dict[str, type[AstNodeType]] = {}
        names: dict[str, type[AstNodeType]] = {}

        for n_cls in node_classes:
            _dict_add_duplicates(contents, n_cls.FIRST_CONTENTS, n_cls)
            _dict_add_duplicates(names, n_cls.FIRST_NAMES, n_cls)

        return cls(contents, names)

    def __contains__(self, token: Token) -> bool:
        return token.content in self.contents or token.name in self.names

    def __getitem__(self, token: Token) -> Any | None:
        return self.names.get(token.name, self.contents.get(token.content))


# allows to skip braced constructions like '(' exp ')'
# index should point to start brace symbol
# returns index of last stop brace symbol


def skip_parenthesis(
    stream: BufferedTokenStream, start: str, stop: str, index: int = 0
) -> int:
    if (sym := stream.peek(index).content) == start:
        stack = [
            sym,
        ]
        while stack:
            index += 1
            sym = stream.peek(index).content
            if sym == start:
                stack.append(sym)
            elif sym == stop:
                stack.pop()
            elif sym == r"\Z":
                return index

        return index + 1

    return index


# sometimes we need to check just one term
# in such cases instead of copy - pasting if ... raise
# just use this function


def parse_terminal(
    stream: BufferedTokenStream,
    expected_value: str,
    prev_err_name: str,
    err_name: str = "",
):
    if (t := next(stream)).content != expected_value:
        raise WrongTokenError(
            t.content,
            t.pos,
            err_name if err_name else f"'{expected_value}'",
            prev_err_name,
        )


# same situation here


def parse_node(
    stream: BufferedTokenStream,
    node_type: type[AstNodeType],
    prev_err_name: str,
    err_name: str = "",
) -> AstNodeType:
    if not node_type.presented_in_stream(stream):
        t = next(stream)
        raise WrongTokenError(
            t.content,
            t.pos,
            err_name if err_name else node_type.ERROR_NAME,
            prev_err_name,
        )

    return node_type.from_tokens(stream)


# used to parse constructions like
# term separator term ....
# non_empty - extract at least 1 element


def parse_node_list(
    stream: BufferedTokenStream,
    node_type: type[AstNodeType],
    separators: set[str] = {","},
    non_empty: bool = False,
    error_name: str = "",
    greedy: bool = False,
) -> Generator[AstNodeType, None, None]:
    if non_empty:
        yield parse_node(stream, node_type, error_name)

    elif node_type.presented_in_stream(stream):
        yield node_type.from_tokens(stream)

    else:
        return

    while stream.peek().content in separators:
        if node_type.presented_in_stream(stream, 1):
            next(stream)
            yield node_type.from_tokens(stream)

        elif not greedy:
            break

        else:
            error_name = f"'{next(stream).content}'"
            t = next(stream)
            raise WrongTokenError(t.content, t.pos, node_type.ERROR_NAME, error_name)


# used to reduce code while parsing simple rules
# like sequences of terms and nonterms


# TypeVarTuple cannot properly handle this situation so return type is Any
# but actually it returns objects of classes specified in rule tuple


def parse_simple_rule(
    stream: BufferedTokenStream,
    rule: tuple[type[AstNode] | str, ...],
    error_name: str = "",
) -> Generator[Any, None, None]:
    for unit in rule:
        if isinstance(unit, str):
            parse_terminal(stream, unit, error_name)
            error_name = unit
        else:
            yield parse_node(stream, unit, error_name)
            error_name = unit.ERROR_NAME
