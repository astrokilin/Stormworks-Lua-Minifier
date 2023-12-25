from lua.lexer import Token, BufferedTokenStream


class WrongTokenError(Exception):
    def __init__(
        self,
        err_token: Token,
        err_stream: BufferedTokenStream,
        err_name: str,
        prev_err_name: str = "",
    ):
        self.err_token = err_token
        self.err_pos, self.err_str = err_stream.find_token(err_token)
        self.explanation = err_name + " expected"
        if prev_err_name:
            self.explanation += " after " + prev_err_name

    def get_underscore_str(self) -> str:
        return "".join(
            [" " if sym != "\t" else sym for sym in self.err_str[: self.err_pos[1] - 1]]
        ) + "^" * len(self.err_token.content)

    def __str__(self):
        return f"wrong token on {self.err_pos[:2]} Got: {self.err_token.content} but {self.explanation}"
