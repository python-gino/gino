from .local import enable_task_local, disable_task_local


class SanicMixin:
    """
    Enable lazy connection for request by default.
    You can use 'app.config[DB_USE_CONNECTION_FOR_REQUEST] = False' to change
    the default value.
    Database connections will be auto closed when on_response().
    simple usages:
        # simple get user
        await User.get(11)
        # close database connection by manual when needed.
        await request['connection'].close()
    """
    def init_app(self, app):
        if app.config.setdefault('DB_USE_CONNECTION_FOR_REQUEST', True):
            @app.middleware('request')
            async def on_request(request):
                # noinspection PyUnresolvedReferences
                request['conn_ctx'] = ctx = self.acquire(lazy=True)
                request['connection'] = await ctx.__aenter__()

            @app.middleware('response')
            async def on_response(request, response):
                ctx = request.pop('conn_ctx', None)
                request.pop('connection', None)
                if ctx is not None:
                    await ctx.__aexit__(None, None, None)

        @app.listener('before_server_start')
        async def before_server_start(_, loop):
            # await User.get(8)
            # await request['connection'].close()

            enable_task_local(loop)
            # noinspection PyUnresolvedReferences
            await self.create_pool(
                host=app.config.setdefault('DB_HOST', 'localhost'),
                port=app.config.setdefault('DB_PORT', 5432),
                user=app.config.setdefault('DB_USER', 'postgres'),
                password=app.config.setdefault('DB_PASSWORD', ''),
                database=app.config.setdefault('DB_DATABASE', 'postgres'),
                min_size=app.config.setdefault('DB_POOL_MIN_SIZE', 5),
                max_size=app.config.setdefault('DB_POOL_MAX_SIZE', 10),
                loop=loop,
            )

        @app.listener('after_server_stop')
        async def after_server_stop(_, loop):
            # noinspection PyUnresolvedReferences
            await self.bind.close()
            disable_task_local(loop)
