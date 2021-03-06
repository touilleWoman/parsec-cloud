import attr
import pendulum
from typing import Tuple, Dict, Union

from parsec.types import DeviceID, UserID, FrozenDict
from parsec.serde import UnknownCheckedSchema, OneOfSchema, fields, validate, post_load
from parsec.core.types import local_manifests
from parsec.core.types.base import EntryName, EntryNameField, serializer_factory
from parsec.core.types.access import (
    BlockAccess,
    ManifestAccess,
    BlockAccessSchema,
    ManifestAccessSchema,
)


__all__ = (
    "FileManifest",
    "FolderManifest",
    "WorkspaceManifest",
    "UserManifest",
    "RemoteManifest",
    "remote_manifest_dumps",
    "remote_manifest_loads",
)


# File manifest


@attr.s(slots=True, frozen=True, auto_attribs=True)
class FileManifest:
    author: DeviceID
    version: int
    created: pendulum.Pendulum
    updated: pendulum.Pendulum
    size: int
    blocks: Tuple[BlockAccess] = attr.ib(converter=tuple)

    def evolve(self, **data) -> "FileManifest":
        return attr.evolve(self, **data)

    def to_local(self) -> "local_manifests.LocalFileManifest":
        return local_manifests.LocalFileManifest(
            author=self.author,
            base_version=self.version,
            created=self.created,
            updated=self.updated,
            size=self.size,
            blocks=self.blocks,
            is_placeholder=False,
            need_sync=False,
        )


class FileManifestSchema(UnknownCheckedSchema):
    format = fields.CheckedConstant(1, required=True)
    type = fields.CheckedConstant("file_manifest", required=True)
    author = fields.DeviceID(required=True)
    version = fields.Integer(required=True, validate=validate.Range(min=1))
    created = fields.DateTime(required=True)
    updated = fields.DateTime(required=True)
    size = fields.Integer(required=True, validate=validate.Range(min=0))
    blocks = fields.List(fields.Nested(BlockAccessSchema), required=True)

    @post_load
    def make_obj(self, data):
        data.pop("type")
        data.pop("format")
        return FileManifest(**data)


file_manifest_serializer = serializer_factory(FileManifestSchema)


# Folder manifest


@attr.s(slots=True, frozen=True, auto_attribs=True)
class FolderManifest:
    author: DeviceID
    version: int
    created: pendulum.Pendulum
    updated: pendulum.Pendulum
    children: Dict[EntryName, ManifestAccess] = attr.ib(converter=FrozenDict)

    def evolve(self, **data) -> "FolderManifest":
        return attr.evolve(self, **data)

    def to_local(self) -> "local_manifests.LocalFolderManifest":
        return local_manifests.LocalFolderManifest(
            author=self.author,
            base_version=self.version,
            created=self.created,
            updated=self.updated,
            children=self.children,
            is_placeholder=False,
            need_sync=False,
        )


class FolderManifestSchema(UnknownCheckedSchema):
    format = fields.CheckedConstant(1, required=True)
    type = fields.CheckedConstant("folder_manifest", required=True)
    author = fields.DeviceID(required=True)
    version = fields.Integer(required=True, validate=validate.Range(min=1))
    created = fields.DateTime(required=True)
    updated = fields.DateTime(required=True)
    children = fields.Map(
        EntryNameField(validate=validate.Length(min=1, max=256)),
        fields.Nested(ManifestAccessSchema),
        required=True,
    )

    @post_load
    def make_obj(self, data):
        data.pop("type")
        data.pop("format")
        return FolderManifest(**data)


folder_manifest_serializer = serializer_factory(FolderManifestSchema)


# Workspace manifest


@attr.s(slots=True, frozen=True, auto_attribs=True)
class WorkspaceManifest(FolderManifest):
    creator: UserID
    participants: Tuple[UserID]

    def to_local(self) -> "local_manifests.LocalFolderManifest":
        return local_manifests.LocalWorkspaceManifest(
            author=self.author,
            base_version=self.version,
            created=self.created,
            updated=self.updated,
            children=self.children,
            creator=self.creator,
            participants=self.participants,
            is_placeholder=False,
            need_sync=False,
        )


class WorkspaceManifestSchema(FolderManifestSchema):
    type = fields.CheckedConstant("workspace_manifest", required=True)
    creator = fields.UserID(required=True)
    participants = fields.List(fields.UserID(), required=True)

    @post_load
    def make_obj(self, data):
        data.pop("type")
        data.pop("format")
        return WorkspaceManifest(**data)


workspace_manifest_serializer = serializer_factory(WorkspaceManifestSchema)


# User manifest


@attr.s(slots=True, frozen=True, auto_attribs=True)
class UserManifest(FolderManifest):
    last_processed_message: int

    def to_local(self) -> "local_manifests.LocalFolderManifest":
        return local_manifests.LocalUserManifest(
            author=self.author,
            base_version=self.version,
            created=self.created,
            updated=self.updated,
            children=self.children,
            last_processed_message=self.last_processed_message,
            is_placeholder=False,
            need_sync=False,
        )


class UserManifestSchema(FolderManifestSchema):
    type = fields.CheckedConstant("user_manifest", required=True)
    last_processed_message = fields.Integer(required=True, validate=validate.Range(min=0))

    @post_load
    def make_obj(self, data):
        data.pop("type")
        data.pop("format")
        return UserManifest(**data)


user_manifest_serializer = serializer_factory(UserManifestSchema)


class TypedRemoteManifestSchema(OneOfSchema):
    type_field = "type"
    type_field_remove = False
    type_schemas = {
        "workspace_manifest": WorkspaceManifestSchema,
        "user_manifest": UserManifestSchema,
        "folder_manifest": FolderManifestSchema,
        "file_manifest": FileManifestSchema,
    }

    def get_obj_type(self, obj):
        if isinstance(obj, WorkspaceManifest):
            return "workspace_manifest"
        elif isinstance(obj, UserManifest):
            return "user_manifest"
        elif isinstance(obj, FolderManifest):
            return "folder_manifest"
        elif isinstance(obj, FileManifest):
            return "file_manifest"
        else:
            raise RuntimeError(f"Unknown object {obj}")


remote_manifest_serializer = serializer_factory(TypedRemoteManifestSchema)


RemoteManifest = Union[UserManifest, FolderManifest, WorkspaceManifest, UserManifest]


def remote_manifest_dumps(manifest: RemoteManifest) -> bytes:
    """
    Raises:
        SerdeError
    """
    return remote_manifest_serializer.dumps(manifest)


def remote_manifest_loads(raw: bytes) -> RemoteManifest:
    """
    Raises:
        SerdeError
    """
    return remote_manifest_serializer.loads(raw)
