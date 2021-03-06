import re
from urllib.parse import urlsplit, urlunsplit, parse_qs

from parsec.crypto_types import VerifyKey, export_root_verify_key, import_root_verify_key


__all__ = (
    "OrganizationID",
    "BackendOrganizationBootstrapAddr",
    "BackendOrganizationAddr",
    "UserID",
    "DeviceName",
    "DeviceID",
)


class FrozenDict(dict):
    def __repr__(self):
        return f"{self.__class__.__name__}({dict.__repr__(self)})"

    def _ro_guard(*args, **kwargs):
        raise AttributeError("FrozenDict doesn't allow modifications")

    __setitem__ = _ro_guard
    __delitem__ = _ro_guard
    pop = _ro_guard
    clear = _ro_guard
    popitem = _ro_guard
    setdefault = _ro_guard
    update = _ro_guard

    def evolve(self, **data):
        return FrozenDict(**self, **data)


class OrganizationID(str):
    __slots__ = ()
    regex = re.compile(r"^\w{1,32}$")

    def __init__(self, raw):
        if not isinstance(raw, str) or not self.regex.match(raw):
            raise ValueError("Invalid organization ID")

    def __repr__(self):
        return f"<OrganizationID {super().__repr__()}>"


class BackendAddr(str):
    __slots__ = ("_split",)

    def __init__(self, raw: str):
        if not isinstance(raw, str):
            raise ValueError("Invalid backend address.")

        self._split = urlsplit(raw)

        if self._split.scheme not in ("ws", "wss"):
            raise ValueError("Backend addr must start with ws:// or wss://")

    @property
    def scheme(self):
        return self._split.scheme

    @property
    def hostname(self):
        return self._split.hostname

    @property
    def port(self):
        port = self._split.port
        if port:
            return port
        else:
            return 80 if self._split.scheme == "ws" else 443


class BackendOrganizationAddr(BackendAddr):
    __slots__ = ("_root_verify_key", "_organization_id")

    @classmethod
    def build(
        cls, backend_addr: str, name: str, root_verify_key: VerifyKey
    ) -> "BackendOrganizationAddr":
        scheme, netloc, _, _, fragment = urlsplit(backend_addr)
        rvk = export_root_verify_key(root_verify_key)
        query = f"rvk={rvk}"
        return cls(urlunsplit((scheme, netloc, name, query, fragment)))

    def __init__(self, raw: str):
        super().__init__(raw)

        self._organization_id = OrganizationID(self._split.path[1:])

        query = parse_qs(self._split.query)
        try:
            self._root_verify_key = import_root_verify_key(query["rvk"][0])

        except (KeyError, IndexError) as exc:
            raise ValueError("Backend organization address must contains `rvk` params.") from exc

    @property
    def organization_id(self) -> OrganizationID:
        return self._organization_id

    @property
    def root_verify_key(self) -> VerifyKey:
        return self._root_verify_key


class BackendOrganizationBootstrapAddr(BackendAddr):
    __slots__ = ("_bootstrap_token", "_organization_id")

    @classmethod
    def build(
        cls, backend_addr: str, name: str, bootstrap_token: str
    ) -> "BackendOrganizationBootstrapAddr":
        scheme, netloc, _, _, fragment = urlsplit(backend_addr)
        query = f"bootstrap-token={bootstrap_token}"
        return cls(urlunsplit((scheme, netloc, name, query, fragment)))

    def __init__(self, raw: str):
        super().__init__(raw)

        self._organization_id = OrganizationID(self._split.path[1:])

        query = parse_qs(self._split.query)
        try:
            self._bootstrap_token = query["bootstrap-token"][0]

        except (KeyError, IndexError) as exc:
            raise ValueError(
                "Backend domain address must contains a `bootstrap-token` param."
            ) from exc

    @property
    def organization_id(self) -> OrganizationID:
        return self._organization_id

    @property
    def bootstrap_token(self) -> str:
        return self._bootstrap_token

    def generate_organization_addr(self, root_verify_key: VerifyKey) -> BackendOrganizationAddr:
        scheme, netloc, path, _, fragment = urlsplit(self)
        query = f"rvk={export_root_verify_key(root_verify_key)}"
        return BackendOrganizationAddr.build(
            urlunsplit((scheme, netloc, "", "", fragment)), self.organization_id, root_verify_key
        )
        return BackendOrganizationAddr(urlunsplit((scheme, netloc, path, query, fragment)))


class UserID(str):
    __slots__ = ()
    regex = re.compile(r"^\w{1,32}$")

    def __init__(self, raw):
        if not isinstance(raw, str) or not self.regex.match(raw):
            raise ValueError("Invalid user name")

    def __repr__(self):
        return f"<UserID {super().__repr__()}>"


class DeviceName(str):
    __slots__ = ()
    regex = re.compile(r"^\w{1,32}$")

    def __init__(self, raw):
        if not isinstance(raw, str) or not self.regex.match(raw):
            raise ValueError("Invalid device name")

    def __repr__(self):
        return f"<DeviceName {super().__repr__()}>"


class DeviceID(str):
    __slots__ = ()
    regex = re.compile(r"^\w{1,32}@\w{1,32}$")

    def __init__(self, raw):
        if not isinstance(raw, str) or not self.regex.match(raw):
            raise ValueError("Invalid device ID")

    def __repr__(self):
        return f"<DeviceID {super().__repr__()}>"

    @property
    def user_id(self) -> UserID:
        return UserID(self.split("@")[0])

    @property
    def device_name(self) -> DeviceName:
        return DeviceName(self.split("@")[1])
