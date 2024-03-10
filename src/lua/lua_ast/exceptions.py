class UnexpectedSymbolError(Exception):
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
    def __init__(
        self,
        err_content: str,
        err_file_offset: int,
        err_name: str,
        prev_err_name: str = "",
    ):
        self.err_content = err_content
        self.err_file_offset = err_file_offset
        self.__explanation = f"{err_name} expected"
        if prev_err_name:
            self.__explanation += f" after {prev_err_name}"

    def __str__(self):
        return f"wrong token: '{self.err_content}' but {self.__explanation}"
