"""
This module contains exceptions that can occur during building of lua syntax tree
"""


class UnexpectedSymbolError(Exception):
    """represents error during lexical analysis
    public fields:
        err_content -- term that caused an error
        err_file_offset -- error offset in file
    """

    def __init__(
        self,
        err_content: str,
        err_file_offset: int,
    ):
        self.err_content = err_content
        self.err_file_offset = err_file_offset

    def __str__(self):
        return f"unexpected symbol: {self.err_content}"


class WrongTokenError(Exception):
    """represents error during syntax analysis
    public fields:
        token_name      -- type of token
        err_content     -- term that caused an error
        err_file_offset -- error offset in file
        err_name        -- what is expected
        prev_err_name   -- after what the error has occured
    """

    def __init__(
        self,
        token_name: str,
        err_content: str,
        err_file_offset: int,
        err_name: str,
        prev_err_name: str = "",
    ):
        self.err_file_offset: int = err_file_offset
        self.err_content: str
        self.__explanation: str

        if token_name == "EOF":
            self.err_content = " "
            self.__explanation = f"<EOF> reached, but {err_name} expected"

        else:
            self.err_content = err_content
            self.__explanation = f"wrong token: '{err_content}' but {err_name} expected"

            if prev_err_name:
                self.__explanation += f" after {prev_err_name}"

    def __str__(self):
        return self.__explanation
