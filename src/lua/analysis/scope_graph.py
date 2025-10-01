"""
This module provides the NamesStat class whose task is to analyse the abstract
syntax tree for variable names and provide the operation to perform renaming, where
the new variable name is shorter the more often it is used.
"""

from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Generator
from string import ascii_letters, digits
from functools import singledispatchmethod
from typing import Self

from lua.graph import TreeNode
from lua.lua_ast import (
    AstNode,
    NameNode,
    # functions stuff
    FuncBodyNode,
    # data nodes
    DataNode,
    ExpNode,
    TableConstrNode,
    FieldNode,
    BinOpNode,
    UnOpNode,
    FuncDefNode,
    PrefExpNode,
    # prefexpnode extractors
    FuncGetterNode,
    TableGetterNode,
    MethodGetterNode,
    # lua statements
    ChunkNode,
    BlockNode,
    VarsAssignNode,
    FuncCallNode,
    LabelNode,
    GotoNode,
    DoBlockNode,
    WhileLoopNode,
    RepeatLoopNode,
    IfNode,
    ForLoopNode,
    ForIterLoopNode,
    FuncAssignNode,
    LocalFuncAssignNode,
    LocalVarsAssignNode,
    RetNode,
)

_RESERVED_GLOBAL_NAMES = {
    # global libs
    "math",
    "table",
    "string",
    # global functions
    "pairs",
    "ipairs",
    "next",
    "tostring",
    "tonumber",
    "type",
    # stormworks specific
    "async",
    "onTick",
    "onDraw",
    "input",
    "output",
    "screen",
    "property",
    "map",
}


def _name_generator() -> Generator[str, None, None]:
    """creates string iterator that return valid short lua names for variables"""

    letters = ascii_letters + "_"
    alph = letters + digits
    first_len = len(letters)
    alph_len = len(alph)
    res = [
        0,
    ]

    yield letters[0]

    while True:
        res[0] += 1

        if res[0] == first_len:
            res[0] = 0

            for i in range(1, len(res)):
                res[i] += 1

                if res[i] == alph_len:
                    res[i] = 0
                else:
                    break

            else:
                res.append(1)

        yield "".join([alph[ind] for ind in res])


@dataclass
class _ScopeNode(TreeNode):
    """
    node scope tree, each node contains name table
    name table - dict[variable_name, list[all its uses (ast name_nodes)]]
    """

    __slots__ = "successors", "name_table"

    successors: list[_ScopeNode]
    name_table: dict[str, list[NameNode]]

    def descendants(self):
        return reversed(self.successors)

    def get_log_string(self):
        yield "scope names:"

        for k, v in self.name_table.items():
            yield k + "\tuses:\t" + str(len(v))


class _ScopeTreeBuilder:
    """builds scope tree"""

    __slots__ = ("__nodes_stack",)

    def __init__(self) -> None:
        # node on top of stack represents global scope
        self.__nodes_stack: list[_ScopeNode] = [
            _ScopeNode([], {}),
        ]

    def build_tree(self, root: BlockNode) -> _ScopeNode:
        """returns scope tree root node"""

        self._process_chunk_node(root)

        return self.__nodes_stack[0]

    def _enter_new_scope(self) -> None:
        """appends new scope node to stack"""

        stack = self.__nodes_stack
        new_scope_node = _ScopeNode([], {})
        stack[-1].successors.append(new_scope_node)
        stack.append(new_scope_node)

    def _leave_scope(self) -> None:
        """pops scope from stack"""
        self.__nodes_stack.pop()

    def _add_local_name_use(self, name_node: NameNode) -> None:
        """adds name use entry to current (top of dfs stack) scope"""

        target = name_node.name
        name_table = self.__nodes_stack[-1].name_table

        if (u := name_table.get(target)) is not None:
            u.append(name_node)
        else:
            name_table[target] = [
                name_node,
            ]

    def _add_local_name_uses(self, name_node_list: list[NameNode]) -> None:
        """process list of local name nodes"""

        for name in name_node_list:
            self._add_local_name_use(name)

    def _add_name_use(self, name_node: NameNode) -> None:
        """traverses scope graph up to global namespace to insert name use entry"""

        target = name_node.name
        stack = self.__nodes_stack

        for scope_node in reversed(stack):
            if (u := scope_node.name_table.get(target)) is not None:
                u.append(name_node)
                return

        if target not in _RESERVED_GLOBAL_NAMES:
            stack[0].name_table[target] = [
                name_node,
            ]

    # function stuff

    def _process_funcbody_node(self, node: FuncBodyNode) -> None:
        """process funcbody node that can emerge during both block and datanode processings"""

        self._enter_new_scope()

        for name_node in node.name_node_list:
            self._add_local_name_use(name_node)

        self._process_block_node(node.block_node)
        self._leave_scope()

    def _process_funcgetter_node(self, node: FuncGetterNode) -> None:
        """process a call to a function"""
        arg = node.arg

        if isinstance(arg, list):
            self._process_exp_list(arg)
        else:
            self._process_exp_subtree(arg)

    def _process_exp_list(self, exp_node_list: list[ExpNode]) -> None:
        """process list of exp nodes"""

        for exp in exp_node_list:
            self._process_exp_subtree(exp.data_node)

    def _process_exp_node(self, node: ExpNode):
        """process exp node"""
        self._process_exp_subtree(node.data_node)

    # expression processing
    @singledispatchmethod
    def _process_exp_subtree(self, arg: DataNode) -> None:
        """process data nodes in expression tree to find all used variable names"""

    @_process_exp_subtree.register(PrefExpNode)
    def _(self, node: PrefExpNode):
        v = node.var_node

        if isinstance(v, NameNode):
            self._add_name_use(v)
        else:
            self._process_exp_node(v)

        for ext in node.extractor_node_list:
            match ext:
                case FuncGetterNode():
                    self._process_funcgetter_node(ext)

                case TableGetterNode(field_node=ExpNode() as f):
                    self._process_exp_node(f)

                case MethodGetterNode():
                    self._process_funcgetter_node(ext.funcgetter_node)

    @_process_exp_subtree.register(FuncDefNode)
    def _(self, node: FuncDefNode):
        self._process_funcbody_node(node.funcbody_node)

    @_process_exp_subtree.register(BinOpNode)
    def _(self, node: BinOpNode):
        self._process_exp_subtree(node.left_operand_node)
        self._process_exp_subtree(node.right_operand_node)

    @_process_exp_subtree.register(UnOpNode)
    def _(self, node: UnOpNode):
        self._process_exp_subtree(node.right_operand_node)

    @_process_exp_subtree.register(TableConstrNode)
    def _(self, node: TableConstrNode):
        for field in node.field_node_list:
            i_node = field.index_node

            if isinstance(i_node, ExpNode):
                self._process_exp_node(i_node)

            self._process_exp_node(field.exp_node)

    # statement processing
    def _process_chunk_node(self, node: ChunkNode) -> None:
        """process chunk node"""

        self._process_block_node(node.block_node)

    def _process_block_node(self, node: BlockNode) -> None:
        """process block node by processing each statement in it"""

        for statement in node.statement_node_list:
            self._process_statement_node(statement)

    @singledispatchmethod
    def _process_statement_node(self, arg: AstNode) -> None:
        """process statement node according to its type"""

    @_process_statement_node.register(VarsAssignNode)
    def _(self, node: VarsAssignNode):
        for prefexp_node in node.var_node_list:
            self._process_exp_subtree(prefexp_node)

        self._process_exp_list(node.exp_node_list)

    @_process_statement_node.register(FuncCallNode)
    def _(self, node: FuncCallNode):
        self._process_exp_subtree(node)

    @_process_statement_node.register(LabelNode)
    def _(self, node: LabelNode):
        self._add_local_name_use(node.name_node)

    @_process_statement_node.register(GotoNode)
    def _(self, node: GotoNode):
        self._add_name_use(node.name_node)

    @_process_statement_node.register(DoBlockNode)
    def _(self, node: DoBlockNode):
        self._enter_new_scope()
        self._process_block_node(node.block_node)
        self._leave_scope()

    @_process_statement_node.register(WhileLoopNode)
    def _(self, node: WhileLoopNode):
        self._process_exp_node(node.exp_node)
        self._enter_new_scope()
        self._process_block_node(node.block_node)
        self._leave_scope()

    @_process_statement_node.register(RepeatLoopNode)
    def _(self, node: RepeatLoopNode):
        self._enter_new_scope()
        self._process_block_node(node.block_node)
        self._process_exp_node(node.exp_node)
        self._leave_scope()

    @_process_statement_node.register(IfNode)
    def _(self, node: IfNode):
        # work on if
        (block, exp) = node.block_exp
        self._process_exp_node(exp)
        self._enter_new_scope()
        self._process_block_node(block)
        self._leave_scope()

        # work on elseif
        for block, exp in node.block_exp_list:
            self._process_exp_node(exp)
            self._enter_new_scope()
            self._process_block_node(block)
            self._leave_scope()

        # work on else
        if (else_block := node.else_block_node) is not None:
            self._enter_new_scope()
            self._process_block_node(else_block)
            self._leave_scope()

    @_process_statement_node.register(ForLoopNode)
    def _(self, node: ForLoopNode):
        self._process_exp_node(node.assign_exp_node)
        self._process_exp_node(node.cond_exp_node)

        if (i := node.iter_exp_node) is not None:
            self._process_exp_node(i)

        self._enter_new_scope()
        self._add_local_name_use(node.name_node)
        self._process_block_node(node.block_node)
        self._leave_scope()

    @_process_statement_node.register(ForIterLoopNode)
    def _(self, node: ForIterLoopNode):
        self._process_exp_list(node.exp_node_list)
        self._enter_new_scope()
        self._add_local_name_uses(node.name_node_list)
        self._process_block_node(node.block_node)
        self._leave_scope()

    @_process_statement_node.register(FuncAssignNode)
    def _(self, node: FuncAssignNode):
        self._add_name_use(node.funcname_node.name_node_list[0])
        self._process_funcbody_node(node.funcbody_node)

    @_process_statement_node.register(LocalFuncAssignNode)
    def _(self, node: LocalFuncAssignNode):
        self._add_local_name_use(node.name_node)
        self._process_funcbody_node(node.funcbody_node)

    @_process_statement_node.register(LocalVarsAssignNode)
    def _(self, node: LocalVarsAssignNode):
        self._add_local_name_uses(node.name_node_list)
        self._process_exp_list(node.exp_node_list)

    @_process_statement_node.register(RetNode)
    def _(self, node: RetNode):
        self._process_exp_list(node.exp_node_list)


class NamesStat:
    """scope tree to track use of all variables and their names"""

    def __init__(self, root_node: _ScopeNode) -> None:
        self.root_node = root_node

    @classmethod
    def from_lua_ast(cls, block_node: BlockNode) -> Self:
        """builds scope graph from top block of lua ast"""

        return cls(_ScopeTreeBuilder().build_tree(block_node))

    def optimize_names(self) -> None:
        """perform naming optimization on scope graph"""

        main_list: list[list[NameNode]] = []
        sub_list: list[list[NameNode]] = []

        stack_2 = [
            self.root_node,
        ]
        stack_1 = []

        while stack_2:
            stack_1, stack_2 = (stack_2, stack_1)

            while stack_1:
                node = stack_1.pop()
                h = list(node.name_table.values())
                h.sort(key=len, reverse=True)

                for i, v in enumerate(h):
                    if i < len(sub_list):
                        sub_list[i].extend(v)
                    else:
                        sub_list.append(v)

                stack_2.extend(node.descendants())

            main_list.extend(sub_list)
            sub_list.clear()

        main_list.sort(key=len, reverse=True)
        name_gen = _name_generator()

        for name_node_list in main_list:
            new_name = next(name_gen)

            for name_node in name_node_list:
                name_node.name = new_name

    def show_tree(self):
        self.root_node.show()
