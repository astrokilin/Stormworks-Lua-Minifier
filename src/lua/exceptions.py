class ParsingError(Exception):
    """represents error during parsing
    fields:
    err_msg  -- message describing the error
    """

    def __init__(self, err_msg: str) -> None:
        self.err_msg = err_msg

    def __str__(self):
        return self.err_msg
