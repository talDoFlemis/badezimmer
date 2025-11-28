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
UNKNOWN_KIND: DeviceKind
SENSOR_KIND: DeviceKind
ACTUATOR_KIND: DeviceKind
UNKNOWN_DEVICE_STATUS: DeviceStatus
OFFLINE_DEVICE_STATUS: DeviceStatus
ONLINE_DEVICE_STATUS: DeviceStatus
ERROR_DEVICE_STATUS: DeviceStatus

class ConnectedDevice(_message.Message):
    __slots__ = ()
    class PropertiesEntry(_message.Message):
        __slots__ = ()
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
    id: str
    device_name: str
    kind: DeviceKind
    status: DeviceStatus
    ips: _containers.RepeatedScalarFieldContainer[str]
    port: int
    properties: _containers.ScalarMap[str, str]
    def __init__(self, id: _Optional[str] = ..., device_name: _Optional[str] = ..., kind: _Optional[_Union[DeviceKind, str]] = ..., status: _Optional[_Union[DeviceStatus, str]] = ..., ips: _Optional[_Iterable[str]] = ..., port: _Optional[int] = ..., properties: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ListConnectedDevicesRequest(_message.Message):
    __slots__ = ()
    FILTER_KIND_FIELD_NUMBER: _ClassVar[int]
    FILTER_NAME_FIELD_NUMBER: _ClassVar[int]
    filter_kind: DeviceKind
    filter_name: str
    def __init__(self, filter_kind: _Optional[_Union[DeviceKind, str]] = ..., filter_name: _Optional[str] = ...) -> None: ...

class ListConnectedDevicesResponse(_message.Message):
    __slots__ = ()
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    devices: _containers.RepeatedCompositeFieldContainer[ConnectedDevice]
    def __init__(self, devices: _Optional[_Iterable[_Union[ConnectedDevice, _Mapping]]] = ...) -> None: ...

class SendActuatorCommandRequest(_message.Message):
    __slots__ = ()
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    LIGHT_ACTION_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    light_action: LightLampActionRequest
    def __init__(self, device_id: _Optional[str] = ..., light_action: _Optional[_Union[LightLampActionRequest, _Mapping]] = ...) -> None: ...

class SendActuatorCommandResponse(_message.Message):
    __slots__ = ()
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class SensorData(_message.Message):
    __slots__ = ()
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    LIGHT_DATA_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    kind: DeviceKind
    light_data: LightSensorData
    def __init__(self, device_id: _Optional[str] = ..., kind: _Optional[_Union[DeviceKind, str]] = ..., light_data: _Optional[_Union[LightSensorData, _Mapping]] = ...) -> None: ...

class Color(_message.Message):
    __slots__ = ()
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class LightLampActionRequest(_message.Message):
    __slots__ = ()
    TURN_ON_FIELD_NUMBER: _ClassVar[int]
    BRIGHTNESS_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    turn_on: bool
    brightness: int
    color: Color
    def __init__(self, turn_on: _Optional[bool] = ..., brightness: _Optional[int] = ..., color: _Optional[_Union[Color, _Mapping]] = ...) -> None: ...

class LightSensorData(_message.Message):
    __slots__ = ()
    IS_ON_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    BRIGHTNESS_PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    is_on: bool
    color: Color
    brightness_percentage: float
    def __init__(self, is_on: _Optional[bool] = ..., color: _Optional[_Union[Color, _Mapping]] = ..., brightness_percentage: _Optional[float] = ...) -> None: ...
