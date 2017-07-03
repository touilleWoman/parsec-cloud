import os
import asyncio
import attr
from effect2 import ComposedDispatcher, asyncio_perform

from parsec.core.base import base_dispatcher
from parsec.core.server import run_unix_socket_server
from parsec.core.client_connection import on_connection_factory
from parsec.core.core_api import execute_raw_cmd
from parsec.core.identity import identity_dispatcher_factory, IdentityMixin
from parsec.core.privkey import PrivKeyComponent


def app_factory(*additional_dispatchers):
    app = App()
    privkey = PrivKeyComponent()
    dispatcher = ComposedDispatcher([
        base_dispatcher,
        identity_dispatcher_factory(app),
        privkey.get_dispatcher(),
    ] + list(additional_dispatchers))
    on_connection = on_connection_factory(execute_raw_cmd, dispatcher)
    app.on_connection = on_connection
    app.dispatcher = dispatcher
    return app


def run_app(socket_path, app=None, loop=None):
    app = app or app_factory()
    loop = loop or asyncio.get_event_loop()
    server = loop.run_until_complete(run_unix_socket_server(app.on_connection, socket_path))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(server.stop())
    finally:
        loop.close()


@attr.s
class App(IdentityMixin):
    async def async_perform(self, intent):
        return await asyncio_perform(self.dispatcher, intent)