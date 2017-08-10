from .local import get_local
from .local import enable_task_local, disable_task_local


class LazyTransactionalConnection:
    def __init__(self, metadata):
        self._metadata = metadata
        self._ctx = self

    async def get_bind(self):
        if self._ctx is None:
            self._ctx = self._metadata.transaction()
            await self._ctx.__aenter__()
        return self._ctx.connection

    async def exit(self, *args):
        if self._ctx is not None:
            ctx, self._ctx = self._ctx, None
            await ctx.__aexit__(*args)


class SanicMixin:
    def init_app(self, app):
        @app.middleware('request')
        async def on_request(request):
            print('on_request')
            local = get_local()
            if local:
                stack = local.get('connection_stack')
                if stack:
                    stack.append(LazyTransactionalConnection(self))

        @app.middleware('response')
        async def on_response(request, response):
            print('on_response')
            local = get_local()
            if local:
                stack = local.get('connection_stack')
                if stack:
                    ltc = stack.pop()
                    await ltc.exit(None if response.status == 200 else True,
                                   None, None)

        @app.listener('before_server_start')
        async def before_server_start(_, loop):
            enable_task_local(loop)
            await self.create_pool(
                host=app.config.setdefault('GINO_HOST', 'localhost'),
                port=app.config.setdefault('GINO_PORT', 5432),
                user=app.config.setdefault('GINO_USER', 'postgres'),
                password=app.config.setdefault('GINO_PASSWORD', ''),
                database=app.config.setdefault('GINO_DATABASE', 'postgres'),
                min_size=app.config.setdefault('DB_POOL_MIN_SIZE', 5),
                max_size=app.config.setdefault('DB_POOL_MAX_SIZE', 10),
                loop=loop,
            )

        @app.listener('after_server_stop')
        async def after_server_stop(_, loop):
            await self.bind.close()
            disable_task_local(loop)
