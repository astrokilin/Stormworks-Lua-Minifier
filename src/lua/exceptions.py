class ParsingError(Exception):
    # file_pos: line_num, row_num, error token length
    def __init__(
        self, filename: str, file_pos: tuple[int, int, int], err_line: str, err_msg: str
    ):
        self.filename = filename
        self.file_pos = file_pos
        self.err_line = err_line
        self.err_msg = err_msg

    def __str__(self):
        return f"{self.filename} {self.file_pos[:2]}: {self.err_msg}"
