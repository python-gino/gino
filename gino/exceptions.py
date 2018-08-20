class GinoException(Exception):
    pass


class NoSuchRowError(GinoException):
    pass


class UninitializedError(GinoException):
    pass
