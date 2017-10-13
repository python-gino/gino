class GinoException(Exception):
    pass


class NoSuchRowError(GinoException):
    pass


class InterfaceError(GinoException):
    pass
