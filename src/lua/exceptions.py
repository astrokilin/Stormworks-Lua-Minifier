class ParsingError(Exception):
    """represents error during parsing
    fields:
    file_pos -- tuple containing info about error position
        (line number, row number, length of error token)
    err_line -- line with the error
    err_msg  -- message describing the error
    """

    def __init__(
        self, file_pos: tuple[int, int, int], err_line: str, err_msg: str
    ) -> None:
        self.file_pos = file_pos
        self.err_line = err_line
        self.err_msg = err_msg

    def __str__(self):
        return f"{self.file_pos[:2]}: {self.err_msg}"
