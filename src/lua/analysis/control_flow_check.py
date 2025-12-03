from bisect import bisect
from dataclasses import dataclass
from functools import singledispatchmethod

from lua.lua_ast import (
    AstNode,
    # statement nodes
    ChunkNode,
    BlockNode,
    IfNode,
    LocalFuncAssignNode,
    FuncAssignNode,
    LocalVarsAssignNode,
    VarsAssignNode,
    ForIterLoopNode,
    ForLoopNode,
    RepeatLoopNode,
    WhileLoopNode,
    DoBlockNode,
    GotoNode,
    BreakNode,
    LabelNode,
    EmptyNode,
    # extractors
    TableGetterNode,
    MethodGetterNode,
    FuncGetterNode,
    # expression nodes
    ExpNode,
    FuncDefNode,
    PrefExpNode,
    TableConstrNode,
    VarargNode,
    BinOpNode,
    UnOpNode,
)


@dataclass(slots=True)
class BlockInfo:
    in_loop: bool
    cur_pos: int
    labels: dict[str, int]
    local_defs: list[int]
    block_node: BlockNode


class StaticChecker:
    """
    Performs static check required for lua compilation
    Mainly: labels + gotos + breaks + use of vararg
    """

    __slots__ = (
        "__block_stack",
        "__block_traverse_stack",
        "__err_nodes",
        "__pos_map",
        "__outside_vararg_func",
    )

    def __init__(self, root_node: ChunkNode, positions_map: dict[int, tuple[int, int]]):
        self.__block_stack: list[BlockInfo] = []
        self.__block_traverse_stack: list[tuple[BlockNode, bool]] = [
            (root_node.block_node, False)
        ]
        self.__err_nodes: list[tuple[int, int, str]] = []
        self.__pos_map = positions_map
        self.__outside_vararg_func: bool = True

    def check(self) -> list[tuple[int, int, str]]:
        """Do the check itself"""

        while self.__block_traverse_stack:
            block, self.__outside_vararg_func = self.__block_traverse_stack.pop()
            self._process_block_node(block, False)

        self.__err_nodes.sort()
        return self.__err_nodes

    def _add_error(self, node: AstNode, s: str):
        self.__err_nodes.append((*self.__pos_map[id(node)], s))

    def _process_block_node(self, node: BlockNode, from_loop: bool):
        labels: dict[str, int] = {}
        local_defs: list[int] = []

        for i, stmnt in enumerate(node.statement_node_list):
            match stmnt:
                case LabelNode():
                    if labels.setdefault(stmnt.name_node.name, i) != i:
                        self._add_error(
                            stmnt,
                            f"duplicate of label '{stmnt.name_node.name}' in same scope ",
                        )

                case LocalVarsAssignNode() | LocalFuncAssignNode():
                    local_defs.append(i)

        top: BlockInfo = BlockInfo(from_loop, 0, labels, local_defs, node)
        self.__block_stack.append(top)

        for i, stmnt in enumerate(node.statement_node_list):
            top.cur_pos = i
            self._processs_node(stmnt)

        self.__block_stack.pop()

    @singledispatchmethod
    def _processs_node(self, arg: AstNode) -> None:
        """Process statement node according to its type"""

    # extractors
    @_processs_node.register(TableGetterNode)
    def _(self, node: TableGetterNode):
        self._processs_node(node.field_node)

    @_processs_node.register(FuncGetterNode)
    def _(self, node: FuncGetterNode):
        if isinstance(node.arg, list):
            for exp_node in node.arg:
                self._processs_node(exp_node)

        else:
            self._processs_node(node.arg)

    @_processs_node.register(MethodGetterNode)
    def _(self, node: MethodGetterNode):
        if isinstance(node.funcgetter_node.arg, list):
            for exp_node in node.funcgetter_node.arg:
                self._processs_node(exp_node)

        else:
            self._processs_node(node.funcgetter_node.arg)

    # expressions
    @_processs_node.register(ExpNode)
    def _(self, node: ExpNode):
        self._processs_node(node.data_node)

    @_processs_node.register(FuncDefNode)
    def _(self, node: FuncDefNode):
        self.__block_traverse_stack.append(
            (node.funcbody_node.block_node, node.funcbody_node.vararg_node is None)
        )

    @_processs_node.register(PrefExpNode)
    def _(self, node: PrefExpNode):
        self._processs_node(node.var_node)

        for extractor_node in node.extractor_node_list:
            self._processs_node(extractor_node)

    @_processs_node.register(TableConstrNode)
    def _(self, node: TableConstrNode):
        for field in node.field_node_list:
            self._processs_node(field.index_node)
            self._processs_node(field.exp_node.data_node)

    @_processs_node.register(VarargNode)
    def _(self, node: VarargNode):
        if self.__outside_vararg_func:
            self._add_error(node, "use of '...' outside vararg function")

    @_processs_node.register(BinOpNode)
    def _(self, node: BinOpNode):
        self._processs_node(node.left_operand_node)
        self._processs_node(node.right_operand_node)

    @_processs_node.register(UnOpNode)
    def _(self, node: UnOpNode):
        self._processs_node(node.right_operand_node)

    # statements
    @_processs_node.register(IfNode)
    def _(self, node: IfNode):
        in_loop: bool = self.__block_stack[-1].in_loop
        self._processs_node(node.block_exp[1].data_node)
        self._process_block_node(node.block_exp[0], in_loop)

        for block_node, exp_node in node.block_exp_list:
            self._processs_node(exp_node.data_node)
            self._process_block_node(block_node, in_loop)

        if node.else_block_node is not None:
            self._process_block_node(node.else_block_node, in_loop)

    @_processs_node.register(LocalFuncAssignNode)
    def _(self, node: LocalFuncAssignNode):
        self.__block_traverse_stack.append(
            (node.funcbody_node.block_node, node.funcbody_node.vararg_node is None)
        )

    @_processs_node.register(FuncAssignNode)
    def _(self, node: FuncAssignNode):
        self.__block_traverse_stack.append(
            (node.funcbody_node.block_node, node.funcbody_node.vararg_node is None)
        )

    @_processs_node.register(LocalVarsAssignNode)
    def _(self, node: LocalVarsAssignNode):
        for exp_node in node.exp_node_list:
            self._processs_node(exp_node.data_node)

    @_processs_node.register(VarsAssignNode)
    def _(self, node: VarsAssignNode):
        for exp_node in node.exp_node_list:
            self._processs_node(exp_node.data_node)

    @_processs_node.register(ForIterLoopNode)
    def _(self, node: ForIterLoopNode):
        for exp_node in node.exp_node_list:
            self._processs_node(exp_node.data_node)

        self._process_block_node(node.block_node, True)

    @_processs_node.register(ForLoopNode)
    def _(self, node: ForLoopNode):
        self._processs_node(node.assign_exp_node.data_node)
        self._processs_node(node.cond_exp_node.data_node)

        if node.iter_exp_node is not None:
            self._processs_node(node.iter_exp_node.data_node)

        self._process_block_node(node.block_node, True)

    @_processs_node.register(RepeatLoopNode)
    def _(self, node: RepeatLoopNode):
        self._processs_node(node.exp_node.data_node)
        self._process_block_node(node.block_node, True)

    @_processs_node.register(WhileLoopNode)
    def _(self, node: WhileLoopNode):
        self._processs_node(node.exp_node.data_node)
        self._process_block_node(node.block_node, True)

    @_processs_node.register(DoBlockNode)
    def _(self, node: DoBlockNode):
        self._process_block_node(node.block_node, self.__block_stack[-1].in_loop)

    @_processs_node.register(GotoNode)
    def _(self, node: GotoNode):
        label_name: str = node.name_node.name

        for block_info in reversed(self.__block_stack):
            target_pos: int | None = block_info.labels.get(label_name, None)

            if target_pos is None:
                continue

            cur_pos: int = block_info.cur_pos
            # for block-end goto (it works over local defs)
            last_meaningful_stmnt_pos: int = next(
                (
                    len(block_info.block_node.statement_node_list) - 1 - i
                    for i, x in enumerate(
                        reversed(block_info.block_node.statement_node_list)
                    )
                    if not isinstance(x, (EmptyNode, LabelNode))
                ),
                cur_pos,
            )

            # backward jump is always valid
            if cur_pos < target_pos and target_pos != last_meaningful_stmnt_pos:
                nearest_local_def_ind: int = block_info.local_defs[
                    bisect(block_info.local_defs, cur_pos)
                ]

                if nearest_local_def_ind < target_pos:
                    match block_info.block_node.statement_node_list[
                        nearest_local_def_ind
                    ]:
                        case LocalVarsAssignNode() as v:
                            local_name = v.name_node_list[0].name

                        case LocalFuncAssignNode() as v:
                            local_name = v.name_node.name

                    self._add_error(node, f"jump into scope of local '{local_name}'")

            return

        self._add_error(node, f"no visible label '{label_name}' for 'goto'")

    @_processs_node.register(BreakNode)
    def _(self, node: BreakNode):
        if not self.__block_stack[-1].in_loop:
            self._add_error(node, "'break' not inside a loop")
