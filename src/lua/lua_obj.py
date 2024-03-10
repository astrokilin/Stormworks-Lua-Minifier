from typing import TextIO
from enum import Enum, auto

from lua.exceptions import ParsingError

from lua.lua_ast.lexer import LuaLexer
from lua.lua_ast.parsing_routines import parse_node
from lua.lua_ast.ast_nodes.nodes.statement_nodes import *
from lua.lua_ast.exceptions import UnexpectedSymbolError, WrongTokenError


class LuaObject:
    def __init__(self, code_file: TextIO):
        self.code_file = code_file
        code = code_file.read()

        try:
            self.ast_top_block = parse_node(
                LuaLexer().create_buffered_stream(code),
                BlockNode,
                "start of file",
                "statement",
            )
        except (UnexpectedSymbolError, WrongTokenError) as e:
            line_num = code.count("\n", 0, e.err_file_offset) + 1
            row_num = e.err_file_offset - code[: e.err_file_offset].rfind("\n")
            line = code.split("\n")[line_num - 1]
            raise ParsingError(
                code_file.name, (line_num, row_num, len(e.err_content)), line, str(e)
            )

    def __str__(self):
        return str(self.ast_top_block)

    def text(self):
        print(*LuaLexer.concat(self.ast_top_block.terminals()), sep="")

    def show_ast(self):
        first_syms = []
        dfs_iter = self.ast_top_block.dfs()

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
