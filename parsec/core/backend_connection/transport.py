import os
import trio
from async_generator import asynccontextmanager
from structlog import get_logger
from typing import Optional, Union

from parsec.types import (
    DeviceID,
    BackendAddr,
    BackendOrganizationAddr,
    BackendOrganizationBootstrapAddr,
)
from parsec.crypto import SigningKey
from parsec.api.transport import Transport, TransportError, TransportClosedByPeer
from parsec.api.protocole import (
    ProtocoleError,
    HandshakeRevokedDevice,
    AnonymousClientHandshake,
    ClientHandshake,
)
from parsec.core.backend_connection.exceptions import (
    BackendNotAvailable,
    BackendHandshakeError,
    BackendDeviceRevokedError,
)


__all__ = (
    "authenticated_transport_factory",
    "anonymous_transport_factory",
    "administrator_transport_factory",
    "transport_pool_factory",
    "TransportPool",
)


logger = get_logger()


async def _connect(
    addr: Union[BackendAddr, BackendOrganizationBootstrapAddr, BackendOrganizationAddr],
    device_id: Optional[DeviceID] = None,
    signing_key: Optional[SigningKey] = None,
    administrator_token: Optional[str] = None,
):
    try:
        stream = await trio.open_tcp_stream(addr.hostname, addr.port)

    except OSError as exc:
        logger.debug("Impossible to connect to backend", reason=exc)
        raise BackendNotAvailable(exc) from exc

    if addr.scheme == "wss":
        stream = _upgrade_stream_to_ssl(stream, addr.hostname)

    try:
        transport = await Transport.init_for_client(stream, addr.hostname)
    except TransportError as exc:
        logger.debug("Connection lost during transport creation", reason=exc)
        raise BackendNotAvailable(exc) from exc

    if administrator_token:
        ch = AnonymousClientHandshake(administrator_token)

    elif not device_id:
        if isinstance(addr, BackendOrganizationBootstrapAddr):
            ch = AnonymousClientHandshake(addr.organization_id)
        else:
            assert isinstance(addr, BackendOrganizationAddr)
            ch = AnonymousClientHandshake(addr.organization_id, addr.root_verify_key)

    else:
        assert isinstance(addr, BackendOrganizationAddr)
        assert signing_key
        ch = ClientHandshake(addr.organization_id, device_id, signing_key, addr.root_verify_key)

    try:
        await _do_handshade(transport, ch)

    except Exception as exc:
        transport.logger.debug("Connection lost during handshake", reason=exc)
        await transport.aclose()
        raise

    return transport


def _upgrade_stream_to_ssl(raw_stream, hostname):
    # The ssl context should be generated once and stored into the config
    # however this is tricky (should ssl configuration be stored per device ?)
    keyfile = os.environ.get("SSL_KEYFILE")
    certfile = os.environ.get("SSL_CERTFILE")

    ssl_context = trio.ssl.create_default_context(trio.ssl.Purpose.CLIENT_AUTH)
    if certfile:
        ssl_context.load_cert_chain(certfile, keyfile)
    else:
        ssl_context.load_default_certs()

    return trio.ssl.SSLStream(raw_stream, ssl_context, server_hostname=hostname)


async def _do_handshade(transport: Transport, ch):
    try:
        challenge_req = await transport.recv()
        answer_req = ch.process_challenge_req(challenge_req)
        await transport.send(answer_req)
        result_req = await transport.recv()
        ch.process_result_req(result_req)
        transport.logger.debug("Handshake done")

    except TransportError as exc:
        raise BackendNotAvailable(exc) from exc

    except HandshakeRevokedDevice as exc:
        transport.logger.warning("Handshake failed", reason=exc)
        raise BackendDeviceRevokedError(exc) from exc

    except ProtocoleError as exc:
        transport.logger.warning("Handshake failed", reason=exc)
        raise BackendHandshakeError(exc) from exc


@asynccontextmanager
async def authenticated_transport_factory(
    addr: BackendOrganizationAddr, device_id: DeviceID, signing_key: SigningKey
) -> Transport:
    transport = await _connect(addr, device_id, signing_key)
    transport.logger = transport.logger.bind(device_id=device_id)
    try:
        yield transport

    finally:
        await transport.aclose()


@asynccontextmanager
async def anonymous_transport_factory(addr: BackendOrganizationAddr) -> Transport:
    transport = await _connect(addr)
    transport.logger = transport.logger.bind(auth="<anonymous>")
    try:
        yield transport

    finally:
        await transport.aclose()


@asynccontextmanager
async def administrator_transport_factory(addr: BackendAddr, token: str) -> Transport:
    transport = await _connect(addr, administrator_token=token)
    transport.logger = transport.logger.bind(auth="<anonymous>")
    try:
        yield transport

    finally:
        await transport.aclose()


class TransportPool:
    def __init__(self, addr, device_id, signing_key, max):
        self.addr = addr
        self.device_id = device_id
        self.signing_key = signing_key
        self.transports = []
        self._closed = False
        self._lock = trio.Semaphore(max)

    @asynccontextmanager
    async def acquire(self, force_fresh=False):
        async with self._lock:
            transport = None
            if not force_fresh:
                try:
                    transport = self.transports.pop()
                except IndexError:
                    pass

            if not transport:
                if self._closed:
                    raise trio.ClosedResourceError()

                transport = await _connect(self.addr, self.device_id, self.signing_key)
                transport.logger = transport.logger.bind(device_id=self.device_id)

            try:
                yield transport

            except TransportClosedByPeer:
                raise

            except Exception:
                await transport.aclose()
                raise

            else:
                self.transports.append(transport)


@asynccontextmanager
async def transport_pool_factory(
    addr: BackendOrganizationAddr, device_id: DeviceID, signing_key: SigningKey, max: int = 4
) -> TransportPool:
    pool = TransportPool(addr, device_id, signing_key, max)
    try:
        yield pool

    finally:
        pool._closed = True
        async with trio.open_nursery() as nursery:
            for transport in pool.transports:
                nursery.start_soon(transport.aclose)
