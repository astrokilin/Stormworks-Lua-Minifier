import sys

from lua import LuaAst, WrongTokenError

if __name__ == "__main__":
    with open(sys.argv[1], "r") as file:
        try:
            ast = LuaAst(file)
            # ast.show()
            ast.text()

        except WrongTokenError as e:
            print(
                f"Error while parsing: {file.name}:",
                e.err_str,
                e.get_underscore_str(),
                str(e),
                sep="\n",
            )
