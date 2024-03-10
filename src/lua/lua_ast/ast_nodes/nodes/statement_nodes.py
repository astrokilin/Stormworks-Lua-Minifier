from __future__ import annotations
from collections.abc import Iterator
from itertools import chain

from lua.lua_ast.lexer import BufferedTokenStream
from lua.lua_ast.parsing_routines import (
    TokenDispatchTable,
    parse_node_list,
    parse_simple_rule,
    parse_terminal,
    parse_node,
)
from lua.lua_ast.runtime_routines import iter_sep, starts_with
from lua.lua_ast.ast_nodes.base_nodes import AstNode, NodeFirst

import lua.lua_ast.ast_nodes.nodes.data_nodes as data_nodes
import lua.lua_ast.ast_nodes.nodes.extractor_nodes as extractor_nodes


class FuncCallNode(data_nodes.PrefExpNode):
    ERROR_NAME: str = "function call"

    __slots__ = ()

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        new_index = cls.skip_to_last_ext(stream, index)

        if new_index == index:
            return False

        # now check last extractor
        last_ext = cls._D_T_EXTRACTORS[stream.peek(new_index)]
        return (
            last_ext is extractor_nodes.FuncGetterNode
            or last_ext is extractor_nodes.MethodGetterNode
        )


class LabelNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"::"}

    ERROR_NAME: str = "label"

    __slots__ = ("name_node",)

    def __init__(self, name_node: data_nodes.NameNode):
        self.name_node = name_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        (name_node,) = parse_simple_rule(
            stream, (data_nodes.NameNode, "::"), next(stream).content
        )
        return cls(name_node)

    def descendants(self):
        return iter((self.name_node,))

    def parse_tree_descendants(self):
        return iter(("::", self.name_node, "::"))


# for this two dudes we need to know their positions in orig file
# since they could be the cause why control flow analysis is impossible


class BreakNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"break"}

    __slots__ = ("__file_offset",)

    def __init__(self, file_offset: int):
        self.__file_offset = file_offset

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(next(stream).pos)

    def parse_tree_descendants(self):
        return iter(("break",))

    @property
    def file_offset(self) -> int:
        return self.__file_offset


class GotoNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"goto"}

    ERROR_NAME: str = "goto statement"

    __slots__ = ("name_node", "__file_offset")

    def __init__(self, name_node: data_nodes.NameNode, file_offset: int):
        self.name_node = name_node
        self.__file_offset = file_offset

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        goto_t = next(stream)
        return cls(parse_node(stream, data_nodes.NameNode, goto_t.content), goto_t.pos)

    def descendants(self):
        return iter((self.name_node,))

    def parse_tree_descendants(self):
        return iter(self.name_node, "goto")

    @property
    def file_offset(self) -> int:
        return self.__file_offset


class DoBlockNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"do"}

    ERROR_NAME: str = "do statement"

    __slots__ = ("block_node",)

    def __init__(self, block_node: BlockNode):
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        (block_node,) = parse_simple_rule(
            stream, (BlockNode, "end"), next(stream).content
        )
        return cls(block_node)

    def descendants(self):
        return iter((self.block_node,))

    def parse_tree_descendants(self):
        return iter(("end", self.block_node, "do"))


# =============================== loop nodes =================================


class WhileLoopNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"while"}

    ERROR_NAME: str = "while loop"

    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode):
        self.exp_node = exp_node
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        exp_node, block_node = parse_simple_rule(
            stream,
            (data_nodes.ExpNode, "do", BlockNode, "end"),
            next(stream).content,
        )

        return cls(exp_node, block_node)

    def descendants(self):
        return iter((self.block_node, self.exp_node))

    def parse_tree_descendants(self):
        return iter(("end", self.block_node, "do", self.exp_node, "while"))


class RepeatLoopNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"repeat"}

    ERROR_NAME: str = "repeat loop"

    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode):
        self.exp_node = exp_node
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        block_node, exp_node = parse_simple_rule(
            stream,
            (BlockNode, "until", data_nodes.ExpNode),
            next(stream).content,
        )
        return cls(block_node, exp_node)

    def descendants(self):
        return iter((self.block_node, self.exp_node))

    def parse_tree_descendants(self):
        return iter((self.block_node, "until", self.exp_node, "repeat"))


class ForLoopNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"for"}

    ERROR_NAME: str = "for loop"

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
    ):
        self.name_node = name_node
        self.assign_exp_node = assign_exp_node
        self.cond_exp_node = cond_exp_node
        self.iter_exp_node = iter_exp_node
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        name_node, assign_exp_node, cond_exp_node = parse_simple_rule(
            stream,
            (data_nodes.NameNode, "=", data_nodes.ExpNode, ",", data_nodes.ExpNode),
            next(stream).content,
        )

        # get optional iter expression
        last_err_str = cond_exp_node.ERROR_NAME
        iter_exp_node = None
        if stream.peek().content == ",":
            iter_exp_node = parse_node(stream, data_nodes.ExpNode, next(stream).content)
            last_err_str = iter_exp_node.ERROR_NAME

        (block_node,) = parse_simple_rule(
            stream, ("do", BlockNode, "end"), last_err_str
        )

        return cls(name_node, assign_exp_node, cond_exp_node, iter_exp_node, block_node)

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return (
            stream.peek(index + 2).content == "="
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

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


class ForIterLoopNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"for"}

    ERROR_NAME: str = "iterator loop"

    __slots__ = "name_node_list", "exp_node_list", "block_node"

    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        exp_node_list: list[data_nodes.ExpNode],
        block_node: BlockNode,
    ):
        self.name_node_list = name_node_list
        self.exp_node_list = exp_node_list
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        name_node_list = list(
            parse_node_list(
                stream,
                data_nodes.NameNode,
                non_empty=True,
                error_name=next(stream).content,
            )
        )

        parse_terminal(stream, "in", name_node_list[-1].ERROR_NAME)

        exp_node_list = list(
            parse_node_list(
                stream, data_nodes.ExpNode, non_empty=True, error_name="'in'"
            )
        )

        (block_node,) = parse_simple_rule(
            stream, ("do", BlockNode, "end"), exp_node_list[-1].ERROR_NAME
        )

        return cls(name_node_list, exp_node_list, block_node)

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return (
            stream.peek(index + 2).content in {",", "in"}
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

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


# =============================  assign nodes =================================


@starts_with(data_nodes.VarNode)
class VarsAssignNode(AstNode):
    ERROR_NAME: str = "variable assigment"

    __slots__ = "var_node_list", "exp_node_list"

    def __init__(
        self,
        var_node_list: list[data_nodes.VarNode],
        exp_node_list: list[data_nodes.ExpNode],
    ):
        self.var_node_list = var_node_list
        self.exp_node_list = exp_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        var_node_list = list(parse_node_list(stream, data_nodes.VarNode, greedy=True))

        parse_terminal(stream, "=", var_node_list[-1].ERROR_NAME)

        exp_node_list = list(
            parse_node_list(
                stream,
                data_nodes.ExpNode,
                non_empty=True,
                error_name="'='",
                greedy=True,
            )
        )

        return cls(var_node_list, exp_node_list)

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return data_nodes.VarNode.presented_in_stream(stream, index)

    def descendants(self):
        return chain(reversed(self.exp_node_list), reversed(self.var_node_list))

    def parse_tree_descendants(self):
        return chain(
            iter_sep(reversed(self.exp_node_list)),
            ("=",),
            iter_sep(reversed(self.var_node_list)),
        )


class LocalVarsAssignNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"local"}

    ERROR_NAME: str = "local variable assigment"

    __slots__ = "name_node_list", "exp_node_list"

    def __init__(
        self,
        name_node_list: list[data_nodes.NameNode],
        exp_node_list: list[data_nodes.ExpNode],
    ):
        self.name_node_list = name_node_list
        self.exp_node_list = exp_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        name_node_list = list(
            parse_node_list(
                stream,
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
                parse_node_list(
                    stream,
                    data_nodes.ExpNode,
                    non_empty=True,
                    error_name=next(stream).content,
                    greedy=True,
                )
            )

        return cls(name_node_list, exp_node_list)

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return (
            data_nodes.NameNode.presented_in_stream(stream, index + 1)
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

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


import lua.lua_ast.ast_nodes.nodes.function_nodes as function_nodes


class FuncAssignNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"function"}

    ERROR_NAME: str = "function declaration"

    __slots__ = "funcname_node", "funcbody_node"

    def __init__(
        self,
        funcname_node: function_nodes.FuncNameNode,
        funcbody_node: function_nodes.FuncBodyNode,
    ):
        self.funcname_node = funcname_node
        self.funcbody_node = funcbody_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        funcname_node, funcbody_node = parse_simple_rule(
            stream,
            (function_nodes.FuncNameNode, function_nodes.FuncBodyNode),
            next(stream).content,
        )
        return cls(funcname_node, funcbody_node)

    def descendants(self):
        return iter((self.funcbody_node, self.funcname_node))

    def parse_tree_descendants(self):
        return iter((self.funcbody_node, self.funcname_node, "function"))


class LocalFuncAssignNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"local"}

    ERROR_NAME: str = "local function declaration"

    __slots__ = "name_node", "funcbody_node"

    def __init__(
        self, name_node: data_nodes.NameNode, funcbody_node: function_nodes.FuncBodyNode
    ):
        self.name_node = name_node
        self.funcbody_node = funcbody_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        name_node, funcbody_node = parse_simple_rule(
            stream,
            ("function", data_nodes.NameNode, function_nodes.FuncBodyNode),
            next(stream).content,
        )

        return cls(name_node, funcbody_node)

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return (
            stream.peek(index + 1).content == "function"
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

    def descendants(self):
        return iter((self.funcbody_node, self.name_node))

    def parse_tree_descendants(self):
        return iter((self.funcbody_node, self.name_node, "function", "local"))


# =============================  branch nodes =================================


class ElseIfNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"elseif"}

    ERROR_NAME: str = "elseif statement"

    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode, **kwargs):
        self.exp_node = exp_node
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        exp_node, block_node = parse_simple_rule(
            stream,
            (data_nodes.ExpNode, "then", BlockNode),
            next(stream).content,
        )

        return cls(exp_node, block_node)

    def descendants(self):
        return iter((self.block_node, self.exp_node))

    def parse_tree_descendants(self):
        return iter((self.block_node, "then", self.exp_node, "elseif"))


class ElseNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"else"}

    ERROR_NAME: str = "else statement"

    __slots__ = ("block_node",)

    def __init__(self, block_node: BlockNode, **kwargs):
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(parse_node(stream, BlockNode, next(stream).content))

    def descendants(self):
        return iter((self.block_node,))

    def parse_tree_descendants(self):
        return iter((self.block_node, "else"))


class IfNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"if"}

    ERROR_NAME: str = "if statement"

    __slots__ = "exp_node", "block_node", "elseif_node_list", "else_node"

    def __init__(
        self,
        exp_node: data_nodes.ExpNode,
        block_node: BlockNode,
        elseif_node_list: list[ElseIfNode],
        else_node: ElseNode | None,
    ):
        self.exp_node = exp_node
        self.block_node = block_node
        self.elseif_node_list = elseif_node_list
        self.else_node = else_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        exp_node, block_node = parse_simple_rule(
            stream,
            (data_nodes.ExpNode, "then", BlockNode),
            next(stream).content,
        )

        err_name = BlockNode.ERROR_NAME

        # parse {elseif exp then block}
        elseif_node_list = []
        while ElseIfNode.presented_in_stream(stream):
            elseif_node_list.append(ElseIfNode.from_tokens(stream))

        if elseif_node_list:
            err_name = ElseIfNode.ERROR_NAME

        # parse [else block]
        else_node = None
        if ElseNode.presented_in_stream(stream):
            else_node = ElseNode.from_tokens(stream)
            err_name = ElseNode.ERROR_NAME

        parse_terminal(stream, "end", err_name)

        return cls(exp_node, block_node, elseif_node_list, else_node)

    def descendants(self):
        return chain(
            () if self.else_node is None else (self.else_node,),
            reversed(self.elseif_node_list),
            (self.block_node, self.exp_node),
        )

    def parse_tree_descendants(self):
        return chain(
            ("end", *(() if self.else_node is None else (self.else_node,))),
            self.elseif_node_list,
            (self.block_node, "then", self.exp_node, "if"),
        )


# ==============================  other nodes =================================


class EmptyNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {";"}

    ERROR_NAME: str = "';' statement"

    __slots__ = ()

    def parse_tree_descendants(self):
        return iter((";",))


class RetNode(AstNode):
    FIRST_CONTENTS: NodeFirst = {"return"}

    ERROR_NAME: str = "return statement"

    __slots__ = ("exp_node_list",)

    def __init__(self, exp_node_list: list[data_nodes.ExpNode]):
        self.exp_node_list = exp_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        next(stream)
        # parse [explist]
        exp_node_list: list[data_nodes.ExpNode] = []
        if data_nodes.ExpNode.presented_in_stream(stream):
            exp_node_list.extend(parse_node_list(stream, data_nodes.ExpNode))

        # parse [';'] at the end
        if stream.peek().content == ";":
            next(stream)

        return cls(exp_node_list)

    def descendants(self):
        return reversed(self.exp_node_list)

    def parse_tree_descendants(self):
        return chain(iter_sep(reversed(self.exp_node_list)), ("return",))


class BlockNode(AstNode):
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

    # since presented_in_stream() is always true we dont need this guys

    # FIRST_CONTENTS: NodeFirst = _D_T_STATEMENTS.contents.keys()
    # FIRST_NAMES: NodeFirst = _D_T_STATEMENTS.names.keys()

    # RetNode if it exists should be the last element of statement list

    __slots__ = ("statement_node_list",)

    def __init__(self, statement_node_list: list[AstNode]):
        self.statement_node_list = statement_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        statement_node_list: list[AstNode] = []

        while True:
            match cls._D_T_STATEMENTS[stream.peek()]:
                case None:
                    break

                case list() as possible_candidates:
                    for candidate in possible_candidates[:-1]:
                        if candidate.presented_in_stream(stream):
                            statement_node_list.append(candidate.from_tokens(stream))
                            break
                    else:
                        statement_node_list.append(
                            possible_candidates[-1].from_tokens(stream)
                        )

                case RetNode():
                    statement_node_list.append(RetNode.from_tokens(stream))
                    break

                case AstNode:
                    statement_node_list.append(AstNode.from_tokens(stream))

        return cls(statement_node_list)

    # since block can be empty we assume that
    # it can be always extracted from stream

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0):
        return True

    def descendants(self):
        return reversed(self.statement_node_list)

    def parse_tree_descendants(self):
        return reversed(self.statement_node_list)
