# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: parsec/volume/volume.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='parsec/volume/volume.proto',
  package='volume',
  syntax='proto3',
  serialized_pb=_b('\n\x1aparsec/volume/volume.proto\x12\x06volume\"\x91\x01\n\x07Request\x12)\n\x04type\x18\x01 \x01(\x0e\x32\x1b.volume.Request.RequestType\x12\x0b\n\x03vid\x18\x02 \x01(\x05\x12\x0f\n\x07\x63ontent\x18\x03 \x01(\x0c\"=\n\x0bRequestType\x12\r\n\tREAD_FILE\x10\x00\x12\x0e\n\nWRITE_FILE\x10\x01\x12\x0f\n\x0b\x44\x45LETE_FILE\x10\x02\"\xb1\x01\n\x08Response\x12\x34\n\x0bstatus_code\x18\x01 \x01(\x0e\x32\x1f.volume.Response.StatusCodeType\x12\x11\n\terror_msg\x18\x02 \x01(\t\x12\x0f\n\x07\x63ontent\x18\x03 \x01(\x0c\x12\x0c\n\x04size\x18\x04 \x01(\x03\"=\n\x0eStatusCodeType\x12\x06\n\x02OK\x10\x00\x12\x0f\n\x0b\x42\x41\x44_REQUEST\x10\x01\x12\x12\n\x0e\x46ILE_NOT_FOUND\x10\x02\x62\x06proto3')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)



_REQUEST_REQUESTTYPE = _descriptor.EnumDescriptor(
  name='RequestType',
  full_name='volume.Request.RequestType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='READ_FILE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='WRITE_FILE', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DELETE_FILE', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=123,
  serialized_end=184,
)
_sym_db.RegisterEnumDescriptor(_REQUEST_REQUESTTYPE)

_RESPONSE_STATUSCODETYPE = _descriptor.EnumDescriptor(
  name='StatusCodeType',
  full_name='volume.Response.StatusCodeType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='OK', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BAD_REQUEST', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FILE_NOT_FOUND', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=303,
  serialized_end=364,
)
_sym_db.RegisterEnumDescriptor(_RESPONSE_STATUSCODETYPE)


_REQUEST = _descriptor.Descriptor(
  name='Request',
  full_name='volume.Request',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='type', full_name='volume.Request.type', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='vid', full_name='volume.Request.vid', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='content', full_name='volume.Request.content', index=2,
      number=3, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _REQUEST_REQUESTTYPE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=39,
  serialized_end=184,
)


_RESPONSE = _descriptor.Descriptor(
  name='Response',
  full_name='volume.Response',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='status_code', full_name='volume.Response.status_code', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='error_msg', full_name='volume.Response.error_msg', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='content', full_name='volume.Response.content', index=2,
      number=3, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='size', full_name='volume.Response.size', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _RESPONSE_STATUSCODETYPE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=187,
  serialized_end=364,
)

_REQUEST.fields_by_name['type'].enum_type = _REQUEST_REQUESTTYPE
_REQUEST_REQUESTTYPE.containing_type = _REQUEST
_RESPONSE.fields_by_name['status_code'].enum_type = _RESPONSE_STATUSCODETYPE
_RESPONSE_STATUSCODETYPE.containing_type = _RESPONSE
DESCRIPTOR.message_types_by_name['Request'] = _REQUEST
DESCRIPTOR.message_types_by_name['Response'] = _RESPONSE

Request = _reflection.GeneratedProtocolMessageType('Request', (_message.Message,), dict(
  DESCRIPTOR = _REQUEST,
  __module__ = 'parsec.volume.volume_pb2'
  # @@protoc_insertion_point(class_scope:volume.Request)
  ))
_sym_db.RegisterMessage(Request)

Response = _reflection.GeneratedProtocolMessageType('Response', (_message.Message,), dict(
  DESCRIPTOR = _RESPONSE,
  __module__ = 'parsec.volume.volume_pb2'
  # @@protoc_insertion_point(class_scope:volume.Response)
  ))
_sym_db.RegisterMessage(Response)


# @@protoc_insertion_point(module_scope)
