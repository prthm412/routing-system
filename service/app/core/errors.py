class DomainError(Exception):
    """A rule of the delivery sservice was broken. The endpoint turns it into an HTTP error."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code