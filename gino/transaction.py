class BaseTransaction:
    pass


class ConnectionTransaction:
    def __init__(self, connection):
        self._conn = connection

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
