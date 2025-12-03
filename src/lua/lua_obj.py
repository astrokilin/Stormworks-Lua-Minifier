from lua.exceptions import ParsingError
from lua.err_builder import ErrBuilder

from lua.lua_ast.lexer import LuaLexer
from lua.lua_ast.parsing import LuaParser
from lua.lua_ast.ast_nodes.nodes.statement_nodes import ChunkNode
from lua.lua_ast.exceptions import UnexpectedSymbolError, WrongTokenError
from lua.analysis.scope_graph import NamesStat
from lua.analysis.control_flow_check import StaticChecker


class LuaObject:
    """Represents lua code file"""

    def __init__(self, code: str) -> None:
        parser: LuaParser = LuaParser(code)
        try:
            self.ast_chunk: ChunkNode = parser.parse_parsable(ChunkNode)
        except (UnexpectedSymbolError, WrongTokenError) as e:
            raise ParsingError(
                ErrBuilder(code).build_error(
                    e.err_file_offset, len(e.err_content), str(e)
                )
            ) from e

        control_flow_errors = StaticChecker(
            self.ast_chunk, parser.positions_map
        ).check()

        if control_flow_errors:
            err_builder = ErrBuilder(code)
            raise ParsingError(
                "\n\n".join(
                    err_builder.build_error(pos, length, expl)
                    for pos, length, expl in control_flow_errors
                )
            )

    def __str__(self):
        return str(self.ast_chunk)

    def do_renaming(self):
        """Rename all variables to shortest names"""

        st = NamesStat.from_lua_ast(self.ast_chunk)
        st.optimize_names()

    def text(self) -> str:
        """Converts lua abstract syntax tree to short text"""

        return "".join(LuaLexer.concat(self.ast_chunk.terminals()))

    def show_ast(self):
        """Prints lua abstract syntax tree, used mostly for debug reasons"""

        self.ast_chunk.show()
