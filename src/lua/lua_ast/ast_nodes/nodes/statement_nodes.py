from __future__ import annotations
from typing import Self
from itertools import chain, cycle

from lua.lua_ast.lexer import BufferedTokenStream
from lua.lua_ast.parsing import (
    Parsable,
    parsable_starts_with,
    TokenDispatchTable,
    LuaParser,
)
from lua.lua_ast.runtime_routines import iter_sep
from lua.lua_ast.ast_nodes.base_nodes import AstNode

import lua.lua_ast.ast_nodes.nodes.data_nodes as data_nodes
import lua.lua_ast.ast_nodes.nodes.extractor_nodes as extractor_nodes


class FuncCallNode(data_nodes.PrefExpNode):
    __slots__ = ()

    PARSABLE_ERROR_NAME = "function call"

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        new_index = cls.skip_to_last_ext(stream, index)

        if new_index == index:
            return False

        # now check last extractor
        last_ext = cls._D_T_EXTRACTORS[stream.peek(new_index)]
        return (
            last_ext is extractor_nodes.FuncGetterNode
            or last_ext is extractor_nodes.MethodGetterNode
        )


class LabelNode(AstNode, Parsable):
    __slots__ = ("name_node",)

    def __init__(self, name_node: data_nodes.NameNode) -> None:
        self.name_node = name_node

    def descendants(self):
        return iter((self.name_node,))

    def parse_tree_descendants(self):
        return iter(("::", self.name_node, "::"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"::"}
    PARSABLE_ERROR_NAME = "label"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        (name_node,) = parser.parse_simple_rule(
            (data_nodes.NameNode, "::"), next(parser.token_stream).content
        )
        return cls(name_node)


class BreakNode(AstNode, Parsable):
    __slots__ = ()

    def parse_tree_descendants(self):
        return iter(("break",))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"break"}
    PARSABLE_MARK_POS = True


class GotoNode(AstNode, Parsable):
    __slots__ = ("name_node",)

    def __init__(self, name_node: data_nodes.NameNode) -> None:
        self.name_node = name_node

    def descendants(self):
        return iter((self.name_node,))

    def parse_tree_descendants(self):
        return iter((self.name_node, "goto"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"goto"}
    PARSABLE_ERROR_NAME = "goto statement"
    PARSABLE_MARK_POS = True

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        return cls(
            parser.parse_parsable(
                data_nodes.NameNode, next(parser.token_stream).content, True
            )
        )


class DoBlockNode(AstNode, Parsable):
    __slots__ = ("block_node",)

    def __init__(self, block_node: BlockNode) -> None:
        self.block_node = block_node

    def descendants(self):
        return iter((self.block_node,))

    def parse_tree_descendants(self):
        return iter(("end", self.block_node, "do"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"do"}
    PARSABLE_ERROR_NAME = "do statement"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        (block_node,) = parser.parse_simple_rule(
            (BlockNode, "end"), next(parser.token_stream).content
        )
        return cls(block_node)


# =============================== loop nodes =================================


class WhileLoopNode(AstNode, Parsable):
    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode) -> None:
        self.exp_node = exp_node
        self.block_node = block_node

    def descendants(self):
        return iter((self.block_node, self.exp_node))

    def parse_tree_descendants(self):
        return iter(("end", self.block_node, "do", self.exp_node, "while"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"while"}
    PARSABLE_ERROR_NAME = "while loop"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        exp_node, block_node = parser.parse_simple_rule(
            (data_nodes.ExpNode, "do", BlockNode, "end"),
            next(parser.token_stream).content,
        )
        return cls(exp_node, block_node)


class RepeatLoopNode(AstNode, Parsable):
    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode) -> None:
        self.exp_node = exp_node
        self.block_node = block_node

    def descendants(self):
        return iter((self.block_node, self.exp_node))

    def parse_tree_descendants(self):
        return iter((self.block_node, "until", self.exp_node, "repeat"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"repeat"}
    PARSABLE_ERROR_NAME = "repeat loop"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        block_node, exp_node = parser.parse_simple_rule(
            (BlockNode, "until", data_nodes.ExpNode),
            next(parser.token_stream).content,
        )
        return cls(exp_node, block_node)


class ForLoopNode(AstNode, Parsable):
    __slots__ = (
        "name_node",
        "assign_exp_node",
        "cond_exp_node",
        "iter_exp_node",
        "block_node",
    )

    def __init__(
        self,
        name_node: data_nodes.NameNode,
        assign_exp_node: data_nodes.ExpNode,
        cond_exp_node: data_nodes.ExpNode,
        iter_exp_node: data_nodes.ExpNode | None,
        block_node: BlockNode,
    ) -> None:
        self.name_node = name_node
        self.assign_exp_node = assign_exp_node
        self.cond_exp_node = cond_exp_node
        self.iter_exp_node = iter_exp_node
        self.block_node = block_node

    def descendants(self):
        return iter(
            (
                self.block_node,
                *(() if self.iter_exp_node is None else (self.iter_exp_node,)),
                self.cond_exp_node,
                self.assign_exp_node,
                self.name_node,
            )
        )

    def parse_tree_descendants(self):
        return chain(
            ("end", self.block_node, "do"),
            () if self.iter_exp_node is None else (self.iter_exp_node, ","),
            (self.cond_exp_node, ",", self.assign_exp_node, "=", self.name_node, "for"),
        )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"for"}
    PARSABLE_ERROR_NAME = "for loop"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        name_node, assign_exp_node, cond_exp_node = parser.parse_simple_rule(
            (data_nodes.NameNode, "=", data_nodes.ExpNode, ",", data_nodes.ExpNode),
            next(stream).content,
        )

        # get optional iter expression
        last_err_str = cond_exp_node.PARSABLE_ERROR_NAME
        iter_exp_node = None
        if stream.peek().content == ",":
            iter_exp_node = parser.parse_parsable(
                data_nodes.ExpNode, next(stream).content, True
            )
            last_err_str = iter_exp_node.PARSABLE_ERROR_NAME

        (block_node,) = parser.parse_simple_rule(("do", BlockNode, "end"), last_err_str)

        return cls(name_node, assign_exp_node, cond_exp_node, iter_exp_node, block_node)

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return (
            stream.peek(index + 2).content == "="
            and stream.peek(index).content in cls.PARSABLE_FIRST_TOKEN_CONTENTS
        )


class ForIterLoopNode(AstNode, Parsable):
    __slots__ = "name_node_list", "exp_node_list", "block_node"

    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        exp_node_list: list[data_nodes.ExpNode],
        block_node: BlockNode,
    ) -> None:
        self.name_node_list = name_node_list
        self.exp_node_list = exp_node_list
        self.block_node = block_node

    def descendants(self):
        return chain(
            (self.block_node,),
            reversed(self.exp_node_list),
            reversed(self.name_node_list),
        )

    def parse_tree_descendants(self):
        return chain(
            ("end", self.block_node, "do"),
            iter_sep(reversed(self.exp_node_list)),
            ("in",),
            iter_sep(reversed(self.name_node_list)),
            ("for",),
        )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"for"}
    PARSABLE_ERROR_NAME = "iterator loop"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        name_node_list = list(
            parser.parse_list(
                data_nodes.NameNode,
                non_empty=True,
                error_name=next(stream).content,
            )
        )

        parser.parse_terminal("in", name_node_list[-1].PARSABLE_ERROR_NAME)

        exp_node_list = list(
            parser.parse_list(data_nodes.ExpNode, non_empty=True, error_name="'in'")
        )

        (block_node,) = parser.parse_simple_rule(
            ("do", BlockNode, "end"), exp_node_list[-1].PARSABLE_ERROR_NAME
        )

        return cls(name_node_list, exp_node_list, block_node)

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return (
            stream.peek(index + 2).content in {",", "in"}
            and stream.peek(index).content in cls.PARSABLE_FIRST_TOKEN_CONTENTS
        )


# =============================  assign nodes =================================


@parsable_starts_with(data_nodes.VarNode)
class VarsAssignNode(AstNode, Parsable):
    __slots__ = "var_node_list", "exp_node_list"

    def __init__(
        self,
        var_node_list: list[data_nodes.VarNode],
        exp_node_list: list[data_nodes.ExpNode],
    ) -> None:
        self.var_node_list = var_node_list
        self.exp_node_list = exp_node_list

    def descendants(self):
        return chain(reversed(self.exp_node_list), reversed(self.var_node_list))

    def parse_tree_descendants(self):
        return chain(
            iter_sep(reversed(self.exp_node_list)),
            ("=",),
            iter_sep(reversed(self.var_node_list)),
        )

    PARSABLE_ERROR_NAME = "variable assigment"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        var_node_list = list(parser.parse_list(data_nodes.VarNode, greedy=True))

        parser.parse_terminal("=", var_node_list[-1].PARSABLE_ERROR_NAME)

        exp_node_list = list(
            parser.parse_list(
                data_nodes.ExpNode,
                non_empty=True,
                error_name="'='",
                greedy=True,
            )
        )

        return cls(var_node_list, exp_node_list)

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return data_nodes.VarNode.parsable_presented_in_stream(stream, index)


class LocalVarsAssignNode(AstNode, Parsable):
    __slots__ = "name_node_list", "exp_node_list"

    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        exp_node_list: list[data_nodes.ExpNode],
    ) -> None:
        self.name_node_list = name_node_list
        self.exp_node_list = exp_node_list

    def descendants(self):
        return chain(reversed(self.exp_node_list), reversed(self.name_node_list))

    def parse_tree_descendants(self):
        if self.exp_node_list:
            return chain(
                iter_sep(reversed(self.exp_node_list)),
                ("=",),
                iter_sep(reversed(self.name_node_list)),
                ("local",),
            )

        return chain(iter_sep(reversed(self.name_node_list)), ("local",))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"local"}
    PARSABLE_ERROR_NAME = "local variable assigment"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        name_node_list = list(
            parser.parse_list(
                data_nodes.NameNode,
                non_empty=True,
                error_name=next(stream).content,
                greedy=True,
            )
        )

        exp_node_list: list[data_nodes.ExpNode] = []
        # parse ['=' explist]
        if stream.peek().content == "=":
            exp_node_list.extend(
                parser.parse_list(
                    data_nodes.ExpNode,
                    non_empty=True,
                    error_name=next(stream).content,
                    greedy=True,
                )
            )

        return cls(name_node_list, exp_node_list)

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return (
            data_nodes.NameNode.parsable_presented_in_stream(stream, index + 1)
            and stream.peek(index).content in cls.PARSABLE_FIRST_TOKEN_CONTENTS
        )


import lua.lua_ast.ast_nodes.nodes.function_nodes as function_nodes


class FuncAssignNode(AstNode, Parsable):
    __slots__ = "funcname_node", "funcbody_node"

    def __init__(
        self,
        funcname_node: function_nodes.FuncNameNode,
        funcbody_node: function_nodes.FuncBodyNode,
    ) -> None:
        self.funcname_node = funcname_node
        self.funcbody_node = funcbody_node

    def descendants(self):
        return iter((self.funcbody_node, self.funcname_node))

    def parse_tree_descendants(self):
        return iter((self.funcbody_node, self.funcname_node, "function"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"function"}
    PARSABLE_ERROR_NAME = "function declaration"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        funcname_node, funcbody_node = parser.parse_simple_rule(
            (function_nodes.FuncNameNode, function_nodes.FuncBodyNode),
            next(parser.token_stream).content,
        )
        return cls(funcname_node, funcbody_node)


class LocalFuncAssignNode(AstNode, Parsable):
    __slots__ = "name_node", "funcbody_node"

    def __init__(
        self, name_node: data_nodes.NameNode, funcbody_node: function_nodes.FuncBodyNode
    ) -> None:
        self.name_node = name_node
        self.funcbody_node = funcbody_node

    def descendants(self):
        return iter((self.funcbody_node, self.name_node))

    def parse_tree_descendants(self):
        return iter((self.funcbody_node, self.name_node, "function", "local"))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"local"}
    PARSABLE_ERROR_NAME = "local function declaration"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        name_node, funcbody_node = parser.parse_simple_rule(
            ("function", data_nodes.NameNode, function_nodes.FuncBodyNode),
            next(parser.token_stream).content,
        )

        return cls(name_node, funcbody_node)

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return (
            stream.peek(index + 1).content == "function"
            and stream.peek(index).content in cls.PARSABLE_FIRST_TOKEN_CONTENTS
        )


# =============================  branch node ==================================


class IfNode(AstNode, Parsable):
    __slots__ = "block_exp", "block_exp_list", "else_block_node"

    def __init__(
        self,
        block_exp: tuple[BlockNode, data_nodes.ExpNode],
        block_exp_list: list[tuple[BlockNode, data_nodes.ExpNode]],
        else_block_node: BlockNode | None,
    ) -> None:
        self.block_exp = block_exp
        self.block_exp_list = block_exp_list
        self.else_block_node = else_block_node

    def descendants(self):
        return chain(
            () if self.else_block_node is None else (self.else_block_node,),
            chain.from_iterable(reversed(self.block_exp_list)),
            iter(self.block_exp),
        )

    def parse_tree_descendants(self):
        return chain(
            (
                "end",
                *(
                    ()
                    if self.else_block_node is None
                    else (self.else_block_node, "else")
                ),
            ),
            chain.from_iterable(
                zip(
                    chain.from_iterable(reversed(self.block_exp_list)),
                    cycle(("then", "elseif")),
                )
            ),
            (self.block_exp[0], "then", self.block_exp[1], "if"),
        )

    PARSABLE_FIRST_TOKEN_CONTENTS = {"if"}
    PARSABLE_ERROR_NAME = "if statement"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        block_exp_list: list[tuple[BlockNode, data_nodes.ExpNode]] = []
        else_block_node = None

        (tmp_exp, tmp_block) = parser.parse_simple_rule(
            (data_nodes.ExpNode, "then", BlockNode), next(stream).content
        )

        block_exp: tuple[BlockNode, data_nodes.ExpNode] = (tmp_block, tmp_exp)

        # parse {elseif exp then block}
        while stream.peek().content == "elseif":
            (tmp_exp, tmp_block) = parser.parse_simple_rule(
                (data_nodes.ExpNode, "then", BlockNode), next(stream).content
            )
            block_exp_list.append((tmp_block, tmp_exp))

        # parse [else block]
        if stream.peek().content == "else":
            else_block_node = parser.parse_parsable(
                BlockNode, next(stream).content, True
            )

        parser.parse_terminal("end", "block inside if statement")

        return cls(block_exp, block_exp_list, else_block_node)


# ==============================  other nodes =================================


class EmptyNode(AstNode, Parsable):
    __slots__ = ()

    def parse_tree_descendants(self):
        return iter((";",))

    PARSABLE_FIRST_TOKEN_CONTENTS = {";"}
    PARSABLE_ERROR_NAME = "';' statement"


class RetNode(AstNode, Parsable):
    __slots__ = ("exp_node_list",)

    def __init__(self, exp_node_list: list[data_nodes.ExpNode]) -> None:
        self.exp_node_list = exp_node_list

    def descendants(self):
        return reversed(self.exp_node_list)

    def parse_tree_descendants(self):
        return chain(iter_sep(reversed(self.exp_node_list)), ("return",))

    PARSABLE_FIRST_TOKEN_CONTENTS = {"return"}
    PARSABLE_ERROR_NAME = "return statement"

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        exp_node_list: list[data_nodes.ExpNode] = []
        next(stream)

        # parse [explist]
        if data_nodes.ExpNode.parsable_presented_in_stream(stream):
            exp_node_list.extend(parser.parse_list(data_nodes.ExpNode))

        # parse [';'] at the end
        if stream.peek().content == ";":
            next(stream)

        return cls(exp_node_list)


class BlockNode(AstNode, Parsable):
    # RetNode if it exists should be the last element of statement list
    __slots__ = ("statement_node_list",)

    def __init__(self, statement_node_list: list[AstNode]) -> None:
        self.statement_node_list = statement_node_list

    def descendants(self):
        return reversed(self.statement_node_list)

    def parse_tree_descendants(self):
        return reversed(self.statement_node_list)

    _D_T_STATEMENTS = TokenDispatchTable.dispatch_types(
        FuncCallNode,
        LabelNode,
        BreakNode,
        GotoNode,
        DoBlockNode,
        WhileLoopNode,
        RepeatLoopNode,
        ForLoopNode,
        ForIterLoopNode,
        VarsAssignNode,
        FuncAssignNode,
        LocalFuncAssignNode,
        LocalVarsAssignNode,
        IfNode,
        EmptyNode,
        RetNode,
    )

    @classmethod
    def parsable_from_parser(cls, parser: LuaParser) -> Self:
        stream = parser.token_stream
        statement_node_list: list[AstNode] = []

        while True:
            match cls._D_T_STATEMENTS[stream.peek()]:
                case None:
                    break

                case list() as possible_candidates:
                    for candidate in possible_candidates[:-1]:
                        if candidate.parsable_presented_in_stream(stream):
                            statement_node_list.append(parser.parse_parsable(candidate))
                            break
                    else:
                        statement_node_list.append(
                            parser.parse_parsable(possible_candidates[-1])
                        )

                case RetNode():
                    statement_node_list.append(parser.parse_parsable(RetNode))
                    break

                case p:
                    statement_node_list.append(parser.parse_parsable(p))

        return cls(statement_node_list)

    # since block can be empty we assume that
    # it can be always extracted from stream

    @classmethod
    def parsable_presented_in_stream(
        cls, stream: BufferedTokenStream, index: int = 0
    ) -> bool:
        return True
