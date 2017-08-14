class GinoException(Exception):
    pass


class NoSuchRowError(GinoException):
    pass


class NotInstalledError(GinoException):
    pass
