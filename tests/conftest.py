import pytest
import attr
import os
import socket
import asyncpg
import contextlib
from unittest.mock import patch
import trio
import trio_asyncio
from async_generator import asynccontextmanager
import hypothesis
from pathlib import Path

from parsec.logging import configure_logging
from parsec.types import BackendAddr, OrganizationID
from parsec.core import CoreConfig
from parsec.core.logged_core import logged_core_factory
from parsec.core.mountpoint import FUSE_AVAILABLE
from parsec.backend import BackendApp, config_factory as backend_config_factory
from parsec.api.protocole import ClientHandshake, AnonymousClientHandshake
from parsec.api.transport import Transport

# TODO: needed ?
pytest.register_assert_rewrite("tests.event_bus_spy")

from tests.common import freeze_time, FreezeTestOnTransportError
from tests.open_tcp_stream_mock_wrapper import OpenTCPStreamMockWrapper
from tests.event_bus_spy import SpiedEventBus
from tests.fixtures import *  # noqa


from tests.oracles import oracle_fs_factory, oracle_fs_with_sync_factory  # noqa: Republishing


def pytest_addoption(parser):
    parser.addoption("--hypothesis-max-examples", default=100, type=int)
    parser.addoption("--hypothesis-derandomize", action="store_true")
    parser.addoption(
        "--postgresql",
        action="store_true",
        help="Use PostgreSQL backend instead of default memory mock",
    )
    parser.addoption("--runslow", action="store_true", help="Don't skip slow tests")
    parser.addoption("--runfuse", action="store_true", help="Don't skip fuse tests")
    parser.addoption(
        "--realcrypto", action="store_true", help="Don't mock crypto operation to save time"
    )


@pytest.fixture(scope="session")
def hypothesis_settings(request):
    return hypothesis.settings(
        max_examples=pytest.config.getoption("--hypothesis-max-examples"),
        derandomize=pytest.config.getoption("--hypothesis-derandomize"),
        deadline=None,
    )


@pytest.fixture(scope="session")
def parsec_logging():
    configure_logging()


def pytest_runtest_setup(item):
    # Mock and non-UTC timezones are a really bad mix, so keep things simple
    os.environ.setdefault("TZ", "UTC")
    if item.get_closest_marker("slow") and not item.config.getoption("--runslow"):
        pytest.skip("need --runslow option to run")
    if item.get_closest_marker("fuse"):
        if not item.config.getoption("--runfuse"):
            pytest.skip("need --runfuse option to run")
        elif not FUSE_AVAILABLE:
            pytest.skip("fuse is not available")


@pytest.fixture(autouse=True, scope="session", name="unmock_crypto")
def mock_crypto():
    # Crypto is CPU hungry
    if pytest.config.getoption("--realcrypto"):

        def unmock():
            pass

        yield unmock

    else:

        def unsecure_but_fast_argon2i_kdf(size, password, salt, *args, **kwargs):
            data = password + salt
            return data[:size] + b"\x00" * (size - len(data))

        from parsec.crypto import argon2i

        vanilla_kdf = argon2i.kdf

        def unmock():
            return patch("parsec.crypto.argon2i.kdf", new=vanilla_kdf)

        with patch("parsec.crypto.argon2i.kdf", new=unsecure_but_fast_argon2i_kdf):
            yield unmock


@pytest.fixture
def realcrypto(unmock_crypto):
    with unmock_crypto():
        yield


def _patch_url_if_xdist(url):
    xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
    if xdist_worker:
        return f"{url}_{xdist_worker}"
    else:
        return url


# Use current unix user's credential, don't forget to do
# `psql -c 'CREATE DATABASE parsec_test;'` prior to run tests
DEFAULT_POSTGRESQL_TEST_URL = "postgresql:///parsec_test"


def _get_postgresql_url():
    return _patch_url_if_xdist(
        os.environ.get("PARSEC_POSTGRESQL_TEST_URL", DEFAULT_POSTGRESQL_TEST_URL)
    )


@pytest.fixture(scope="session")
def postgresql_url():
    if not pytest.config.getoption("--postgresql"):
        pytest.skip("`--postgresql` option not provided")
    return _get_postgresql_url()


@pytest.fixture
async def asyncio_loop():
    # When a ^C happens, trio send a Cancelled exception to each running
    # coroutine. We must protect this one to avoid deadlock if it is cancelled
    # before another coroutine that uses trio-asyncio.
    with trio.open_cancel_scope(shield=True):
        async with trio_asyncio.open_loop() as loop:
            yield loop


@pytest.fixture(scope="session")
def unused_tcp_port():
    """Find an unused localhost TCP port from 1024-65535 and return it."""
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def unused_tcp_addr(unused_tcp_port):
    return "ws://127.0.0.1:%s" % unused_tcp_port


@pytest.fixture(scope="session")
def event_bus_factory():
    return SpiedEventBus


@pytest.fixture
def event_bus(event_bus_factory):
    return event_bus_factory()


@pytest.fixture
def tcp_stream_spy():
    open_tcp_stream_mock_wrapper = OpenTCPStreamMockWrapper()
    with patch("trio.open_tcp_stream", new=open_tcp_stream_mock_wrapper):
        yield open_tcp_stream_mock_wrapper


@pytest.fixture(scope="session")
def monitor():
    from tests.monitor import Monitor

    return Monitor()


@attr.s
class AppServer:
    entry_point = attr.ib()
    addr = attr.ib()
    connection_factory = attr.ib()


@pytest.fixture
def server_factory(tcp_stream_spy):
    count = 0

    @asynccontextmanager
    async def _server_factory(entry_point, url=None):
        nonlocal count
        count += 1

        if not url:
            url = f"ws://server-{count}.localhost:9999"

        try:
            async with trio.open_nursery() as nursery:

                def connection_factory(*args, **kwargs):
                    right, left = trio.testing.memory_stream_pair()
                    nursery.start_soon(entry_point, left)
                    return right

                tcp_stream_spy.push_hook(url, connection_factory)

                yield AppServer(entry_point, url, connection_factory)

                nursery.cancel_scope.cancel()

        finally:
            tcp_stream_spy.pop_hook(url)

    return _server_factory


@pytest.fixture(scope="session")
def backend_addr(unused_tcp_port):
    return BackendAddr(f"ws://127.0.0.1:{unused_tcp_port}")


@pytest.fixture
def bootstrap_postgresql(url):
    # In theory we should use TrioPG here to do db init, but:
    # - Duck typing and similar api makes `_init_db` compatible with both
    # - AsyncPG should be slightly faster than TrioPG
    # - Most important: a trio loop is potentially already started inside this
    #   thread (i.e. if the test is mark as trio). Hence we would have to spawn
    #   another thread just to run the new trio loop.

    import asyncio
    import asyncpg
    from parsec.backend.drivers.postgresql.handler import _init_db

    async def _bootstrap():
        conn = await asyncpg.connect(url)
        await _init_db(conn, force=True)
        await conn.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_bootstrap())


@pytest.fixture()
def backend_store(request):
    if pytest.config.getoption("--postgresql"):
        if request.node.get_closest_marker("slow"):
            import warnings

            warnings.warn(
                "TODO: trio-asyncio loop currently incompatible with hypothesis tests :'("
            )
            return "MOCKED"

        # TODO: would be better to create a new postgresql cluster for each test
        url = _get_postgresql_url()
        try:
            bootstrap_postgresql(url)
        except asyncpg.exceptions.InvalidCatalogNameError as exc:
            raise RuntimeError(
                "Is `parsec_test` a valid database in PostgreSQL ?\n"
                "Running `psql -c 'CREATE DATABASE parsec_test;'` may fix this"
            ) from exc
        return url

    elif request.node.get_closest_marker("postgresql"):
        pytest.skip("`Test is postgresql-only")

    else:
        return "MOCKED"


@pytest.fixture
def blockstore(request, backend_store):
    blockstore_config = {}
    # TODO: allow to test against swift ?
    if backend_store.startswith("postgresql://"):
        blockstore_type = "POSTGRESQL"
    else:
        blockstore_type = "MOCKED"

    # More or less a hack to be able to to configure this fixture from
    # the test function by adding tags to it
    if request.node.get_closest_marker("raid1_blockstore"):
        blockstore_config["RAID1_0_TYPE"] = blockstore_type
        blockstore_config["RAID1_1_TYPE"] = "MOCKED"
        blockstore_type = "RAID1"
    if request.node.get_closest_marker("raid0_blockstore"):
        blockstore_config["RAID0_0_TYPE"] = blockstore_type
        blockstore_config["RAID0_1_TYPE"] = "MOCKED"
        blockstore_type = "RAID0"

    return blockstore_type, blockstore_config


@pytest.fixture
async def nursery():
    # A word about the nursery fixture:
    # The whole point of trio is to be able to build a graph of coroutines to
    # simplify teardown. Using a single top level nursery kind of mitigate this
    # given unrelated coroutines will end up there and be closed all together.
    # Worst, among those coroutine it could exists a relationship that will be lost
    # in a more or less subtle way (typically using a factory fixture that use the
    # default nursery behind the scene).
    # Bonus points occur if using trio-asyncio that creates yet another hidden
    # layer of relationship that could end up in cryptic dead lock hardened enough
    # to survive ^C.
    # Finally if your still no convinced, factory fixtures not depending on async
    # fixtures (like nursery is) can be used inside the Hypothesis tests.
    # I know you love Hypothesis. Checkmate. You won't use this fixture ;-)
    raise RuntimeError("Bad kitty ! Bad !!!")


@pytest.fixture
def backend_factory(
    asyncio_loop,
    event_bus_factory,
    backend_data_binder_factory,
    coolorg,
    alice,
    alice2,
    bob,
    initial_user_manifest_state,
    blockstore,
    backend_store,
):
    # Given the postgresql driver uses trio-asyncio, any coroutine dealing with
    # the backend should inherit from the one with the asyncio loop context manager.
    # This mean the nursery fixture cannot use the backend object otherwise we
    # can end up in a dead lock if the asyncio loop is torndown before the
    # nursery fixture is done with calling the backend's postgresql stuff.

    blockstore_type, blockstore_config = blockstore

    @asynccontextmanager
    async def _backend_factory(populated=True, config={}, event_bus=None):
        async with trio.open_nursery() as nursery:
            config = backend_config_factory(
                db_url=backend_store,
                blockstore_type=blockstore_type,
                environ={**blockstore_config, **config},
            )
            if not event_bus:
                event_bus = event_bus_factory()
            backend = BackendApp(config, event_bus=event_bus)
            # TODO: backend connection to postgresql will timeout if we use a trio
            # mock clock with autothreshold. We should detect this and do something here...
            await backend.init(nursery)

            if populated:
                with freeze_time("2000-01-01"):
                    binder = backend_data_binder_factory(backend)
                    await binder.bind_organization(coolorg, alice)
                    await binder.bind_device(alice2)
                    await binder.bind_device(bob)

            try:
                yield backend

            finally:
                await backend.teardown()
                # Don't do `nursery.cancel_scope.cancel()` given `backend.teardown()`
                # should have stopped all our coroutines (i.e. if the nursery is
                # hanging, something on top of us should be fixed...)

    return _backend_factory


@pytest.fixture
async def backend(backend_factory, request):
    populate = "backend_not_populated" not in request.keywords
    async with backend_factory(populated=populate) as backend:
        yield backend


@pytest.fixture
def backend_data_binder(backend, backend_data_binder_factory):
    return backend_data_binder_factory(backend)


@pytest.fixture
def running_backend_ready(request):
    # Useful to synchronize other fixtures that need to connect to
    # the backend if it is available
    event = trio.Event()
    # Nothing to wait if current test doesn't use `running_backend` fixture
    if "running_backend" not in request.fixturenames:
        event.set()

    return event


@pytest.fixture
async def running_backend(server_factory, backend_addr, backend, running_backend_ready):
    async with server_factory(backend.handle_client, backend_addr) as server:
        server.backend = backend
        running_backend_ready.set()
        yield server


# TODO: rename to backend_transport_factory
@pytest.fixture
def backend_sock_factory(server_factory, coolorg):
    @asynccontextmanager
    async def _backend_sock_factory(backend, auth_as):
        async with server_factory(backend.handle_client) as server:
            stream = server.connection_factory()
            transport = await Transport.init_for_client(stream, server.addr)
            transport = FreezeTestOnTransportError(transport)

            if auth_as:
                # Handshake
                if isinstance(auth_as, OrganizationID):
                    ch = AnonymousClientHandshake(auth_as)
                elif auth_as == "anonymous":
                    # TODO: for legacy test, refactorise this ?
                    ch = AnonymousClientHandshake(coolorg.organization_id)
                elif auth_as == "administrator":
                    ch = AnonymousClientHandshake(backend.config.administrator_token)
                else:
                    ch = ClientHandshake(
                        auth_as.organization_id,
                        auth_as.device_id,
                        auth_as.signing_key,
                        auth_as.root_verify_key,
                    )
                challenge_req = await transport.recv()
                answer_req = ch.process_challenge_req(challenge_req)
                await transport.send(answer_req)
                result_req = await transport.recv()
                ch.process_result_req(result_req)

            yield transport

    return _backend_sock_factory


@pytest.fixture
async def anonymous_backend_sock(backend_sock_factory, backend):
    async with backend_sock_factory(backend, "anonymous") as sock:
        yield sock


@pytest.fixture
async def administrator_backend_sock(backend_sock_factory, backend):
    async with backend_sock_factory(backend, "administrator") as sock:
        yield sock


@pytest.fixture
async def alice_backend_sock(backend_sock_factory, backend, alice):
    async with backend_sock_factory(backend, alice) as sock:
        yield sock


@pytest.fixture
async def alice2_backend_sock(backend_sock_factory, backend, alice2):
    async with backend_sock_factory(backend, alice2) as sock:
        yield sock


@pytest.fixture
async def bob_backend_sock(backend_sock_factory, backend, bob):
    async with backend_sock_factory(backend, bob) as sock:
        yield sock


@pytest.fixture
def core_config(tmpdir):
    tmpdir = Path(tmpdir)
    return CoreConfig(
        config_dir=tmpdir / "config",
        cache_base_dir=tmpdir / "cache",
        data_base_dir=tmpdir / "data",
        mountpoint_base_dir=tmpdir / "mnt",
    )


@pytest.fixture
async def alice_core(running_backend_ready, event_bus_factory, core_config, alice):
    await running_backend_ready.wait()
    async with logged_core_factory(core_config, alice, event_bus_factory()) as alice_core:
        yield alice_core


@pytest.fixture
async def alice2_core(running_backend_ready, event_bus_factory, core_config, alice2):
    await running_backend_ready.wait()
    async with logged_core_factory(core_config, alice2, event_bus_factory()) as alice2_core:
        yield alice2_core


@pytest.fixture
async def bob_core(running_backend_ready, event_bus_factory, core_config, bob):
    await running_backend_ready.wait()
    async with logged_core_factory(core_config, bob, event_bus_factory()) as bob_core:
        yield bob_core
