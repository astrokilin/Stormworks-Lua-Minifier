from __future__ import annotations
from collections.abc import Generator, Sequence

from lua.lexer import BufferedTokenStream
from lua.exceptions import WrongTokenError
from lua.ast_nodes.base_nodes import AstNode, DataNode, OperationNode, starts_with
from lua.parsing_routines import (
    skip_parenthesis,
    TokenDispatchTable,
    parse_node_list,
    parse_simple_rule,
    parse_terminal,
    parse_node,
)
from lua.runtime_routines import iter_sep


class NameNode(DataNode):
    FIRST_NAMES = {"id"}

    ERROR_NAME = "variable name"

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream, parent: AstNode | None = None):
        return cls(name=next(stream).content)

    @classmethod
    def skip(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        if stream.peek(index).name in cls.FIRST_NAMES:
            return index + 1

        return index

    def descendants(self) -> Generator[AstNode, None, None]:
        yield from ()

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (self.name,)

    def __repr__(self):
        return super().__repr__() + f" name: {self.name}"


class VarargNode(DataNode):
    FIRST_CONTENTS = {"..."}

    ERROR_NAME = "vararg expression"

    __slots__ = ()

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return ("...",)

    def get_type(self) -> DataNode.DataTypes:
        return DataNode.DataTypes.VARARG


class ConstNode(DataNode):
    _D_T_TYPES = TokenDispatchTable(
        {
            "nil": DataNode.DataTypes.NIL,
            "true": DataNode.DataTypes.BOOLEAN,
            "false": DataNode.DataTypes.BOOLEAN,
        },
        {
            "string": DataNode.DataTypes.STRING,
            "numeral": DataNode.DataTypes.NUMBER_INT,
        },
    )

    FIRST_CONTENTS = _D_T_TYPES.contents.keys()
    FIRST_NAMES = _D_T_TYPES.names.keys()

    ERROR_NAME = "consant variable"

    __slots__ = "value", "d_type"

    def __init__(self, value: str, d_type: DataNode.DataTypes):
        self.value = value
        self.d_type = d_type

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        t = next(stream)
        d_type: DataNode.DataTypes = cls._D_T_TYPES[t]  # type: ignore
        # float check
        if d_type == DataNode.DataTypes.NUMBER_INT:
            for lit in t.content:
                if lit in {".", "p", "P", "e", "E"}:
                    d_type = DataNode.DataTypes.NUMBER_FLOAT
                    break

        return cls(value=t.content, d_type=d_type)

    def descendants(self) -> Generator[AstNode, None, None]:
        yield from ()

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (self.value,)

    def __repr__(self):
        return super().__repr__() + f" value: {self.value}"

    def get_type(self) -> DataNode.DataTypes:
        return self.d_type


class TableConstrNode(DataNode):
    FIRST_CONTENTS: set = {"{"}

    ERROR_NAME = "table constructor"

    __slots__ = ("field_node_list",)

    def __init__(self, field_node_list: list[FieldNode]):
        self.field_node_list = field_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        field_node_list: list[FieldNode] = []
        # skip {
        err_name = next(stream).content
        # fill fieldlist if it exist
        if FieldNode.presented_in_stream(stream):
            field_separators = {",", ";"}
            field_node_list.extend(parse_node_list(stream, FieldNode, field_separators))
            err_name = field_node_list[-1].ERROR_NAME

            if stream.peek().content in field_separators:
                err_name = next(stream).content

        parse_terminal(stream, "}", err_name)

        return cls(field_node_list)

    @classmethod
    def skip(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        return skip_parenthesis(stream, "{", "}", index)

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "{", *iter_sep(self.field_node_list), "}"

    def get_type(self) -> DataNode.DataTypes:
        return DataNode.DataTypes.TABLE


import lua.ast_nodes.nodes.extractor_nodes as extractor_nodes


@starts_with(NameNode)
class PrefExpNode(DataNode):
    _D_T_EXTRACTORS = TokenDispatchTable.dispatch_types(
        extractor_nodes.TableGetterNode,
        extractor_nodes.FuncGetterNode,
        extractor_nodes.MethodGetterNode,
    )

    FIRST_CONTENTS = {"("}

    ERROR_NAME = "prefix expression"

    __slots__ = "var_node", "extractor_node_list"

    def __init__(
        self, var_node: NameNode | ExpNode, extractor_node_list: list[AstNode]
    ):
        self.var_node = var_node
        self.extractor_node_list = extractor_node_list

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        if NameNode.presented_in_stream(stream):
            var = NameNode.from_tokens(stream)
        else:
            (var,) = parse_simple_rule(stream, (ExpNode, ")"), next(stream).content)

        extractor_node_list = []
        # now parse all extractor_nodes
        while (ext_type := cls._D_T_EXTRACTORS[stream.peek()]) is not None:
            extractor_node_list.append(ext_type.from_tokens(stream))

        return cls(var, extractor_node_list)

    # return index of first token of last extractor
    # if no extractors will return index of first token
    # before Name | ( exp ) rule

    @classmethod
    def skip_to_last_ext(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        new_index = NameNode.skip(stream, index)

        if new_index == index:
            new_index = skip_parenthesis(stream, "(", ")", index)

        # if we havent moved -> there is no prefexp in stream
        if new_index == index:
            return index

        # now get position of the last extractor
        if (last_extractor := cls._D_T_EXTRACTORS[stream.peek(new_index)]) is not None:
            while True:
                index = last_extractor.skip(stream, new_index)
                if (next_extractor := cls._D_T_EXTRACTORS[stream.peek(index)]) is None:
                    break

                new_index = index
                last_extractor = next_extractor

        return new_index

    @classmethod
    def skip(cls, stream: BufferedTokenStream, index: int = 0) -> int:
        new_index = cls.skip_to_last_ext(stream, index)

        # have we moved?
        if new_index == index:
            return index

        if (last_extractor := cls._D_T_EXTRACTORS[stream.peek(new_index)]) is not None:
            new_index = last_extractor.skip(stream, new_index)

        return new_index

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        if isinstance(self.var_node, ExpNode):
            return ("(", self.var_node, ")", *self.extractor_node_list)

        else:
            return (self.var_node, *self.extractor_node_list)


# var node is just PrefExpNode which ends with table extractor or
# PrefExpNode with var = NameNode and no extractors


class VarNode(PrefExpNode):
    ERROR_NAME = "variable"

    __slots__ = ()

    @classmethod
    def presented_in_stream(cls, stream: BufferedTokenStream, index: int = 0) -> bool:
        # VarNode is PrefExpNode with var = name and extractors = []
        # or just PrefExpNode with extractors[-1] = TableGetterNode

        last_ext_offset = cls.skip_to_last_ext(stream, index)

        if extractor_nodes.TableGetterNode.presented_in_stream(stream, last_ext_offset):
            return True

        else:
            return NameNode.presented_in_stream(stream, index)


import lua.ast_nodes.nodes.function_nodes as function_nodes


class FuncDefNode(DataNode):
    FIRST_CONTENTS = {"function"}

    ERROR_NAME = "function definition"

    __slots__ = ("funcbody_node",)

    def __init__(
        self,
        funcbody_node: function_nodes.FuncBodyNode,
    ):
        self.funcbody_node = funcbody_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        return cls(
            parse_node(stream, function_nodes.FuncBodyNode, next(stream).content)
        )

    def get_type(self) -> DataNode.DataTypes:
        return DataNode.DataTypes.FUNCTION

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return "function", self.funcbody_node


import lua.ast_nodes.nodes.operation_nodes as operation_nodes


@starts_with(
    ConstNode,
    PrefExpNode,
    VarargNode,
    FuncDefNode,
    TableConstrNode,
    operation_nodes.UnOpNode,
)
class ExpNode(DataNode):
    _D_T_OPERAND = TokenDispatchTable.dispatch_types(
        ConstNode, PrefExpNode, TableConstrNode, FuncDefNode, VarargNode
    )

    ERROR_NAME = "expression"

    __slots__ = ("data_node",)

    def __init__(self, data_node: DataNode | OperationNode):
        self.data_node = data_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        def traverse_stack(
            top_precedence: int,
            exp_stack: list,
        ):
            while len(exp_stack) > 1 and (
                exp_stack[-2].get_precedence() > top_precedence
                or exp_stack[-2].get_precedence() == top_precedence
                and exp_stack[-2].is_right_assoc()
            ):
                d_2 = exp_stack.pop()
                op = exp_stack.pop()

                op.right_operand_node = d_2

                if isinstance(op, operation_nodes.BinOpNode):
                    op.left_operand_node = exp_stack.pop()

                exp_stack.append(op)

        exp_stack = []

        while True:
            while operation_nodes.UnOpNode.presented_in_stream(stream):
                exp_stack.append(operation_nodes.UnOpNode.from_tokens(stream))

            if (operand_type := cls._D_T_OPERAND[stream.peek()]) is None:
                raise WrongTokenError(next(stream), stream, "operand")

            exp_stack.append(operand_type.from_tokens(stream))

            if operation_nodes.BinOpNode.presented_in_stream(stream):
                next_op = operation_nodes.BinOpNode.from_tokens(stream)
                traverse_stack(next_op.get_precedence(), exp_stack)
                exp_stack.append(next_op)

            else:
                traverse_stack(-1, exp_stack)
                break

        return cls(exp_stack.pop())

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        return (self.data_node,)


@starts_with(ExpNode, NameNode)
class FieldNode(DataNode):
    FIRST_CONTENTS = {"["}

    ERROR_NAME = "table constructor field"

    __slots__ = "index_node", "exp_node"

    def __init__(self, index_node: ExpNode | NameNode | None, exp_node: ExpNode):
        self.index_node = index_node
        self.exp_node = exp_node

    @classmethod
    def from_tokens(cls, stream: BufferedTokenStream):
        index_node = None
        if stream.peek().content == "[":
            (index_node,) = parse_simple_rule(
                stream, (ExpNode, "]", "="), next(stream).content
            )

        elif stream.peek(1).content == "=":
            index_node = NameNode.from_tokens(stream)
            next(stream)

        err_name = "=" if index_node is not None else ""

        return cls(index_node, parse_node(stream, ExpNode, err_name))

    def get_parse_tree_descendants(self) -> Sequence[AstNode | str]:
        match self.index_node:
            case ExpNode():
                return ("[", self.index_node, "]", "=", self.exp_node)

            case NameNode():
                return (self.index_node, "=", self.exp_node)

            case None:
                return (self.exp_node,)
