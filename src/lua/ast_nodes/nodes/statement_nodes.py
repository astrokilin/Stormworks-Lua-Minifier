from __future__ import annotations
from collections.abc import Sequence

from lua.lexer import BufferedTokenStream
from lua.ast_nodes.base_nodes import AstNode, starts_with
from lua.parsing_routines import (
    TokenDispatchTable,
    parse_node_list,
    parse_simple_rule,
    parse_terminal,
    parse_node,
)
from lua.runtime_routines import iter_sep

import lua.ast_nodes.nodes.data_nodes as data_nodes
import lua.ast_nodes.nodes.extractor_nodes as extractor_nodes


class FuncCallNode(data_nodes.PrefExpNode):
    ERROR_NAME = "function call"

    __slots__ = ()

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
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
    FIRST_CONTENTS = {"::"}

    ERROR_NAME = "label"

    __slots__ = ("name_node",)

    def __init__(self, name_node: data_nodes.NameNode):
        self.name_node = name_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        (name_node,) = parse_simple_rule(
            stream, (data_nodes.NameNode, "::"), next(stream).content
        )
        return cls(name_node)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "::", self.name_node, "::"


class BreakNode(AstNode):
    FIRST_CONTENTS = {"break"}

    __slots__ = ()

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return ("break",)


class GotoNode(AstNode):
    FIRST_CONTENTS = {"goto"}

    ERROR_NAME = "goto statement"

    __slots__ = ("name_node",)

    def __init__(self, name_node: data_nodes.NameNode):
        self.name_node = name_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(parse_node(stream, data_nodes.NameNode, next(stream).content))

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "goto", self.name_node


class DoBlockNode(AstNode):
    FIRST_CONTENTS = {"do"}

    ERROR_NAME = "do statement"

    __slots__ = ("block_node",)

    def __init__(self, block_node: BlockNode):
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        (block_node,) = parse_simple_rule(
            stream, (BlockNode, "end"), next(stream).content
        )
        return cls(block_node)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "do", self.block_node, "end"


# =============================== loop nodes ===========================


class WhileLoopNode(AstNode):
    FIRST_CONTENTS = {"while"}

    ERROR_NAME = "while loop"

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "while", self.exp_node, "do", self.block_node, "end"


class RepeatLoopNode(AstNode):
    FIRST_CONTENTS = {"repeat"}

    ERROR_NAME = "repeat loop"

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "repeat", self.exp_node, "until", self.block_node


class ForLoopNode(AstNode):
    FIRST_CONTENTS = {"for"}

    ERROR_NAME = "for loop"

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
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        return (
            stream.peek(index + 2).content == "="
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (
            "for",
            self.name_node,
            "=",
            self.assign_exp_node,
            ",",
            self.cond_exp_node,
            *((",", self.iter_exp_node) if self.iter_exp_node is not None else ()),
            "do",
            self.block_node,
            "end",
        )


class ForIterLoopNode(AstNode):
    FIRST_CONTENTS = {"for"}

    ERROR_NAME = "iterator loop"

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
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        return (
            stream.peek(index + 2).content in {",", "in"}
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (
            "for",
            *iter_sep(self.name_node_list),
            "in",
            *iter_sep(self.exp_node_list),
            "do",
            self.block_node,
            "end",
        )


# =============================  assign nodes ============================


@starts_with(data_nodes.VarNode)
class VarsAssignNode(AstNode):
    ERROR_NAME = "variable assigment"

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
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        return data_nodes.VarNode.presented_in_stream(stream, index)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return *iter_sep(self.var_node_list), "=", *iter_sep(self.exp_node_list)


class LocalVarsAssignNode(AstNode):
    FIRST_CONTENTS = {"local"}

    ERROR_NAME = "local variable assigment"

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
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        return (
            data_nodes.NameNode.presented_in_stream(stream, index + 1)
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (
            "local",
            *iter_sep(self.name_node_list),
            "=",
            *iter_sep(self.exp_node_list),
        )


import lua.ast_nodes.nodes.function_nodes as function_nodes


class FuncAssignNode(AstNode):
    FIRST_CONTENTS = {"function"}

    ERROR_NAME = "function declaration"

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "function", self.funcname_node, self.funcbody_node


class LocalFuncAssignNode(AstNode):
    FIRST_CONTENTS = {"local"}

    ERROR_NAME = "local function declaration"

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
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        return (
            stream.peek(index + 1).content == "function"
            and stream.peek(index).content in cls.FIRST_CONTENTS
        )

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "local", self.name_node, self.funcbody_node


# =============================  branch nodes ============================


class ElseIfNode(AstNode):
    FIRST_CONTENTS = {"elseif"}

    ERROR_NAME = "elseif statement"

    __slots__ = "exp_node", "block_node"

    def __init__(self, exp_node: data_nodes.ExpNode, block_node: BlockNode, **kwargs):
        self.exp_node = exp_node
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream, parent: AstNode | None = None):
        exp_node, block_node = parse_simple_rule(
            stream,
            (data_nodes.ExpNode, "then", BlockNode),
            next(stream).content,
        )

        return cls(exp_node, block_node)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "elseif", self.exp_node, "then", self.block_node


class ElseNode(AstNode):
    FIRST_CONTENTS = {"else"}

    ERROR_NAME = "else statement"

    __slots__ = ("block_node",)

    def __init__(self, block_node: BlockNode, **kwargs):
        self.block_node = block_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream, parent: AstNode | None = None):
        return cls(parse_node(stream, BlockNode, next(stream).content))

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "else", self.block_node


class IfNode(AstNode):
    FIRST_CONTENTS = {"if"}

    ERROR_NAME = "if statement"

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (
            "if",
            self.exp_node,
            "then",
            self.block_node,
            *self.elseif_node_list,
            *((self.else_node,) if self.else_node is not None else ()),
            "end",
        )


# ============================= other nodes ============================


class EmptyNode(AstNode):
    FIRST_CONTENTS = {";"}

    ERROR_NAME = "';' statement"

    __slots__ = ()

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (";",)


class RetNode(AstNode):
    FIRST_CONTENTS = {"return"}

    ERROR_NAME = "return statement"

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "return", *iter_sep(self.exp_node_list)


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

    FIRST_CONTENTS = _D_T_STATEMENTS.contents.keys()
    FIRST_NAMES = _D_T_STATEMENTS.names.keys()

    # RetNode if it exists should be the last element of statement list

    __slots__ = ("statement_node_list",)

    def __init__(self, statement_node_list: list[AstNode]):
        self.statement_node_list = statement_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        statement_node_list = []

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

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return self.statement_node_list
