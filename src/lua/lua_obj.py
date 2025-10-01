from typing import TextIO

from lua.exceptions import ParsingError

from lua.lua_ast.lexer import LuaLexer
from lua.lua_ast.parsing import LuaParser
from lua.lua_ast.ast_nodes.nodes.statement_nodes import ChunkNode
from lua.lua_ast.exceptions import UnexpectedSymbolError, WrongTokenError
from lua.analysis.scope_graph import NamesStat


class LuaObject:
    """represents lua code file"""

    def __init__(self, code: str) -> None:
        try:
            self.ast_chunk: ChunkNode = LuaParser(code).parse_parsable(ChunkNode)
        except (UnexpectedSymbolError, WrongTokenError) as e:
            line_num = code.count("\n", 0, e.err_file_offset) + 1
            row_num = e.err_file_offset - code[: e.err_file_offset].rfind("\n")
            line = code.split("\n")[line_num - 1]
            raise ParsingError(
                (line_num, row_num, len(e.err_content)), line, str(e)
            ) from e

    def __str__(self):
        return str(self.ast_chunk)

    def do_renaming(self):
        """rename all variables to shortest names"""

        st = NamesStat.from_lua_ast(self.ast_chunk)
        st.optimize_names()

    def text(self) -> str:
        """converts lua abstract syntax tree to short text"""

        return "".join(LuaLexer.concat(self.ast_chunk.terminals()))

    def show_ast(self):
        """prints lua abstract syntax tree, used mostly for debug reasons"""

        self.ast_chunk.show()
