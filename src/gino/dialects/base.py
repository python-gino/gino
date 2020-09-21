from contextvars import ContextVar


class PrepareResult:
    operation = None
    payload = None
    context = None


class PrepareOnlyCursorOverride:
    def __init__(self, adapt_connection, do_prepare):
        super().__init__(adapt_connection)
        self._result = PrepareResult()
        self._do_prepare = do_prepare

    def execute(self, operation, *args):
        self._result.operation = operation = self._compile(operation)
        if self._do_prepare:
            try:
                self._result.payload = self._prepare(operation)
            except Exception as error:
                self._handle_exception(error)

    executemany = execute

    def _compile(self, operation):
        raise NotImplementedError()

    def _prepare(self, operation):
        raise NotImplementedError()


class PreparedCursorOverride:
    def __init__(self, adapt_connection, prepared_stmt):
        super().__init__(adapt_connection)
        self._prepared_stmt = prepared_stmt

    def _get_prepared_result(self):
        return self._prepared_stmt._get_prepared()

    def executemany(self, operation, seq_of_parameters):
        raise ValueError("PreparedStatement does not support multiple parameters.")


class GinoCompilerOverride:
    check_override = ContextVar("check")

    def construct_params(
        self, params=None, _group_number=None, _check=True, extracted_parameters=None,
    ):
        _check = self.check_override.get(_check)
        return super().construct_params(
            params, _group_number, _check, extracted_parameters
        )


class GinoExecutionContextOverride:
    prepare_only_cursor = None
    prepared_cursor = None
    prepared_ss_cursor = None

    @classmethod
    def _init_compiled(cls, *args, **kwargs):
        token = None
        if args[3].get("check_args") is False:
            token = GinoCompilerOverride.check_override.set(False)
        try:
            return super()._init_compiled(*args, **kwargs)
        finally:
            if token:
                GinoCompilerOverride.check_override.reset(token)

    def create_cursor(self):
        if self.prepare_only_cursor and self.execution_options.get("compile_only"):
            return self.prepare_only_cursor(
                self._dbapi_connection, self.execution_options.get("do_prepare")
            )
        return super().create_cursor()

    def create_default_cursor(self):
        stmt = self.execution_options.get("prepared_stmt")
        if self.prepared_cursor and stmt:
            return self.prepared_cursor(self._dbapi_connection, stmt)
        return super().create_default_cursor()

    def create_server_side_cursor(self):
        stmt = self.execution_options.get("prepared_stmt")
        if self.prepared_ss_cursor and stmt:
            return self.prepared_ss_cursor(self._dbapi_connection, stmt)
        return super().create_server_side_cursor()

    def _setup_result_proxy(self):
        if self.prepare_only_cursor and self.execution_options.get("compile_only"):
            result = self.cursor._result
            result.context = self
            return result
        return super()._setup_result_proxy()
