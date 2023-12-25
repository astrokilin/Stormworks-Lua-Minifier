from typing import TextIO
from enum import Enum, auto

from lua.lexer import LuaLexer
from lua.parsing_routines import parse_node
from lua.ast_nodes.nodes.statement_nodes import BlockNode


class LuaAst:
    def __init__(self, txt_file: TextIO, lexer: LuaLexer = LuaLexer()):
        self.top_block = parse_node(
            lexer.create_buffered_stream(txt_file), BlockNode, "start of file"
        )

    def __str__(self):
        return str(self.top_block)

    def text(self):
        print(*LuaLexer.concat(self.top_block.terminals()), sep="")

    def show(self):
        first_syms = []
        dfs_iter = self.top_block.dfs()

        # skip top node
        print(repr(next(dfs_iter)[0]))

        for n, _, i, c in dfs_iter:
            print(*first_syms, ("├" if i else "└"), "── ", repr(n), sep="")
            if i and c:
                first_syms.extend(("│", "    "))
            elif not i:
                first_syms.append("    ")

            if (not i) and (not c):
                while first_syms and first_syms.pop() != "│":
                    pass
