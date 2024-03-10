import sys

from lua import LuaObject, ParsingError

if __name__ == "__main__":
    with open(sys.argv[1], "r") as file:
        try:
            l_obj = LuaObject(file)
            # l_obj.show_ast()
            l_obj.text()

        except ParsingError as e:
            print(
                e.err_line,
                e.err_line[: e.file_pos[1] - 1] + "^" * e.file_pos[2],
                str(e),
                sep="\n",
            )
