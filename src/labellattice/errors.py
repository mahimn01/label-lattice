"""Errors. There is exactly one refusal type, and it always looks the same."""


class LabelLatticeError(Exception):
    """Base class for all errors raised by this package."""


class Refused(LabelLatticeError):
    """The caller may not have this result.

    Every reason for refusal raises this same error with the same message:
    the caller is not entitled, the document does not exist, the document was
    deleted, the version does not exist. A caller cannot tell these apart, and
    cannot tell a cached result from an uncached one.
    """

    MESSAGE = "refused"

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)
