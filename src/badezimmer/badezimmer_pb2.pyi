import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DeviceKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_KIND: _ClassVar[DeviceKind]
    SENSOR_KIND: _ClassVar[DeviceKind]
    ACTUATOR_KIND: _ClassVar[DeviceKind]

class DeviceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_DEVICE_STATUS: _ClassVar[DeviceStatus]
    OFFLINE_DEVICE_STATUS: _ClassVar[DeviceStatus]
    ONLINE_DEVICE_STATUS: _ClassVar[DeviceStatus]
    ERROR_DEVICE_STATUS: _ClassVar[DeviceStatus]

class DeviceCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_CATEGORY: _ClassVar[DeviceCategory]
    LIGHT_LAMP: _ClassVar[DeviceCategory]
    FART_DETECTOR: _ClassVar[DeviceCategory]
    TOILET: _ClassVar[DeviceCategory]
    SINK: _ClassVar[DeviceCategory]
    WATER_LEAK: _ClassVar[DeviceCategory]

class TransportProtocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_PROTOCOL: _ClassVar[TransportProtocol]
    TCP_PROTOCOL: _ClassVar[TransportProtocol]
    UDP_PROTOCOL: _ClassVar[TransportProtocol]

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_ERROR: _ClassVar[ErrorCode]
    DEVICE_NOT_FOUND: _ClassVar[ErrorCode]
    INVALID_COMMAND: _ClassVar[ErrorCode]
    DEVICE_OFFLINE: _ClassVar[ErrorCode]
    VALIDATION_ERROR: _ClassVar[ErrorCode]

class MDNSType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MDNS_A: _ClassVar[MDNSType]
    MDNS_PTR: _ClassVar[MDNSType]
    MDNS_SRV: _ClassVar[MDNSType]
    MDNS_TXT: _ClassVar[MDNSType]
UNKNOWN_KIND: DeviceKind
SENSOR_KIND: DeviceKind
ACTUATOR_KIND: DeviceKind
UNKNOWN_DEVICE_STATUS: DeviceStatus
OFFLINE_DEVICE_STATUS: DeviceStatus
ONLINE_DEVICE_STATUS: DeviceStatus
ERROR_DEVICE_STATUS: DeviceStatus
UNKNOWN_CATEGORY: DeviceCategory
LIGHT_LAMP: DeviceCategory
FART_DETECTOR: DeviceCategory
TOILET: DeviceCategory
SINK: DeviceCategory
WATER_LEAK: DeviceCategory
UNKNOWN_PROTOCOL: TransportProtocol
TCP_PROTOCOL: TransportProtocol
UDP_PROTOCOL: TransportProtocol
UNKNOWN_ERROR: ErrorCode
DEVICE_NOT_FOUND: ErrorCode
INVALID_COMMAND: ErrorCode
DEVICE_OFFLINE: ErrorCode
VALIDATION_ERROR: ErrorCode
MDNS_A: MDNSType
MDNS_PTR: MDNSType
MDNS_SRV: MDNSType
MDNS_TXT: MDNSType

class ConnectedDevice(_message.Message):
    __slots__ = ("id", "device_name", "kind", "status", "ips", "port", "properties", "category", "transport_protocol")
    class PropertiesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    IPS_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TRANSPORT_PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    id: str
    device_name: str
    kind: DeviceKind
    status: DeviceStatus
    ips: _containers.RepeatedScalarFieldContainer[str]
    port: int
    properties: _containers.ScalarMap[str, str]
    category: DeviceCategory
    transport_protocol: TransportProtocol
    def __init__(self, id: _Optional[str] = ..., device_name: _Optional[str] = ..., kind: _Optional[_Union[DeviceKind, str]] = ..., status: _Optional[_Union[DeviceStatus, str]] = ..., ips: _Optional[_Iterable[str]] = ..., port: _Optional[int] = ..., properties: _Optional[_Mapping[str, str]] = ..., category: _Optional[_Union[DeviceCategory, str]] = ..., transport_protocol: _Optional[_Union[TransportProtocol, str]] = ...) -> None: ...

class ListConnectedDevicesRequest(_message.Message):
    __slots__ = ("filter_kind", "filter_name")
    FILTER_KIND_FIELD_NUMBER: _ClassVar[int]
    FILTER_NAME_FIELD_NUMBER: _ClassVar[int]
    filter_kind: DeviceKind
    filter_name: str
    def __init__(self, filter_kind: _Optional[_Union[DeviceKind, str]] = ..., filter_name: _Optional[str] = ...) -> None: ...

class ListConnectedDevicesResponse(_message.Message):
    __slots__ = ("devices",)
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    devices: _containers.RepeatedCompositeFieldContainer[ConnectedDevice]
    def __init__(self, devices: _Optional[_Iterable[_Union[ConnectedDevice, _Mapping]]] = ...) -> None: ...

class SendActuatorCommandRequest(_message.Message):
    __slots__ = ("device_id", "light_action", "sink_action")
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    LIGHT_ACTION_FIELD_NUMBER: _ClassVar[int]
    SINK_ACTION_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    light_action: LightLampActionRequest
    sink_action: SinkActionRequest
    def __init__(self, device_id: _Optional[str] = ..., light_action: _Optional[_Union[LightLampActionRequest, _Mapping]] = ..., sink_action: _Optional[_Union[SinkActionRequest, _Mapping]] = ...) -> None: ...

class ErrorDetails(_message.Message):
    __slots__ = ("code", "message", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    message: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., message: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class BadezimmerRequest(_message.Message):
    __slots__ = ("empty", "list_devices", "send_actuator_command")
    EMPTY_FIELD_NUMBER: _ClassVar[int]
    LIST_DEVICES_FIELD_NUMBER: _ClassVar[int]
    SEND_ACTUATOR_COMMAND_FIELD_NUMBER: _ClassVar[int]
    empty: _empty_pb2.Empty
    list_devices: ListConnectedDevicesRequest
    send_actuator_command: SendActuatorCommandRequest
    def __init__(self, empty: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., list_devices: _Optional[_Union[ListConnectedDevicesRequest, _Mapping]] = ..., send_actuator_command: _Optional[_Union[SendActuatorCommandRequest, _Mapping]] = ...) -> None: ...

class BadezimmerResponse(_message.Message):
    __slots__ = ("empty", "error", "list_devices_response", "send_actuator_command_response")
    EMPTY_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LIST_DEVICES_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    SEND_ACTUATOR_COMMAND_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    empty: _empty_pb2.Empty
    error: ErrorDetails
    list_devices_response: ListConnectedDevicesResponse
    send_actuator_command_response: SendActuatorCommandResponse
    def __init__(self, empty: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., error: _Optional[_Union[ErrorDetails, _Mapping]] = ..., list_devices_response: _Optional[_Union[ListConnectedDevicesResponse, _Mapping]] = ..., send_actuator_command_response: _Optional[_Union[SendActuatorCommandResponse, _Mapping]] = ...) -> None: ...

class SendActuatorCommandResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class Color(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class LightLampActionRequest(_message.Message):
    __slots__ = ("turn_on", "brightness", "color")
    TURN_ON_FIELD_NUMBER: _ClassVar[int]
    BRIGHTNESS_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    turn_on: bool
    brightness: int
    color: Color
    def __init__(self, turn_on: bool = ..., brightness: _Optional[int] = ..., color: _Optional[_Union[Color, _Mapping]] = ...) -> None: ...

class SinkActionRequest(_message.Message):
    __slots__ = ("turn_on",)
    TURN_ON_FIELD_NUMBER: _ClassVar[int]
    turn_on: bool
    def __init__(self, turn_on: bool = ...) -> None: ...

class MDNSQuestion(_message.Message):
    __slots__ = ("name", "type")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: MDNSType
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[MDNSType, str]] = ...) -> None: ...

class MDNSQueryRequest(_message.Message):
    __slots__ = ("questions",)
    QUESTIONS_FIELD_NUMBER: _ClassVar[int]
    questions: _containers.RepeatedCompositeFieldContainer[MDNSQuestion]
    def __init__(self, questions: _Optional[_Iterable[_Union[MDNSQuestion, _Mapping]]] = ...) -> None: ...

class MDNSPointerRecord(_message.Message):
    __slots__ = ("name", "domain_name")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    domain_name: str
    def __init__(self, name: _Optional[str] = ..., domain_name: _Optional[str] = ...) -> None: ...

class MDNSSRVRecord(_message.Message):
    __slots__ = ("name", "port", "target", "protocol", "service", "instance")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    name: str
    port: int
    target: str
    protocol: TransportProtocol
    service: str
    instance: str
    def __init__(self, name: _Optional[str] = ..., port: _Optional[int] = ..., target: _Optional[str] = ..., protocol: _Optional[_Union[TransportProtocol, str]] = ..., service: _Optional[str] = ..., instance: _Optional[str] = ...) -> None: ...

class MDNSTextRecord(_message.Message):
    __slots__ = ("name", "entries")
    class EntriesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    name: str
    entries: _containers.ScalarMap[str, str]
    def __init__(self, name: _Optional[str] = ..., entries: _Optional[_Mapping[str, str]] = ...) -> None: ...

class MDNSARecord(_message.Message):
    __slots__ = ("name", "address")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    name: str
    address: str
    def __init__(self, name: _Optional[str] = ..., address: _Optional[str] = ...) -> None: ...

class MDNSRecord(_message.Message):
    __slots__ = ("name", "ttl", "cache_flush", "ptr_record", "srv_record", "txt_record", "a_record")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    CACHE_FLUSH_FIELD_NUMBER: _ClassVar[int]
    PTR_RECORD_FIELD_NUMBER: _ClassVar[int]
    SRV_RECORD_FIELD_NUMBER: _ClassVar[int]
    TXT_RECORD_FIELD_NUMBER: _ClassVar[int]
    A_RECORD_FIELD_NUMBER: _ClassVar[int]
    name: str
    ttl: int
    cache_flush: bool
    ptr_record: MDNSPointerRecord
    srv_record: MDNSSRVRecord
    txt_record: MDNSTextRecord
    a_record: MDNSARecord
    def __init__(self, name: _Optional[str] = ..., ttl: _Optional[int] = ..., cache_flush: bool = ..., ptr_record: _Optional[_Union[MDNSPointerRecord, _Mapping]] = ..., srv_record: _Optional[_Union[MDNSSRVRecord, _Mapping]] = ..., txt_record: _Optional[_Union[MDNSTextRecord, _Mapping]] = ..., a_record: _Optional[_Union[MDNSARecord, _Mapping]] = ...) -> None: ...

class MDNSQueryResponse(_message.Message):
    __slots__ = ("answers", "additional_records")
    ANSWERS_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_RECORDS_FIELD_NUMBER: _ClassVar[int]
    answers: _containers.RepeatedCompositeFieldContainer[MDNSRecord]
    additional_records: _containers.RepeatedCompositeFieldContainer[MDNSRecord]
    def __init__(self, answers: _Optional[_Iterable[_Union[MDNSRecord, _Mapping]]] = ..., additional_records: _Optional[_Iterable[_Union[MDNSRecord, _Mapping]]] = ...) -> None: ...

class MDNS(_message.Message):
    __slots__ = ("transaction_id", "timestamp", "query_request", "query_response")
    TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    QUERY_REQUEST_FIELD_NUMBER: _ClassVar[int]
    QUERY_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    transaction_id: int
    timestamp: _timestamp_pb2.Timestamp
    query_request: MDNSQueryRequest
    query_response: MDNSQueryResponse
    def __init__(self, transaction_id: _Optional[int] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., query_request: _Optional[_Union[MDNSQueryRequest, _Mapping]] = ..., query_response: _Optional[_Union[MDNSQueryResponse, _Mapping]] = ...) -> None: ...
