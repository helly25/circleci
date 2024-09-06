# SPDX-FileCopyrightText: Copyright (c) The helly25/mbo authors (helly25.com)
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A flag support library.

* `ActionEnum`:                Argument parsing `Action` for enum values.
* `ParseEnumList`:             Parses lists of enum values.
* `ActionEnumList`:            Argument parsing `Action` for enum lists.
* `ParseDateTimeOrTimeDelta`:  Parses `datetime.datetime` and time delta values.
* `ActionDateTimeOrTimeDelta`: Argument parsing `Action` for `datetime` and time deltas.
* `ParseByteSize`:             Parse a size (defaults to byte sizes).
* `ActionByteSize`:            Argument parsing `Action` for size values (default for bytes).
"""

import argparse
import collections
import re
from datetime import datetime, time, timedelta, timezone, tzinfo
from enum import Enum
from typing import Any, Callable, Iterable, Optional, cast

from pytimeparse.timeparse import timeparse


class ActionEnum(argparse.Action):
    """Argparse action that handles single Enum values."""

    def __init__(self, **kwargs):
        enum_type = kwargs.pop("type", None)
        if enum_type is None or not issubclass(enum_type, Enum):
            raise ValueError(f"Type must be an Enum, provided type is '{enum_type}'.")

        kwargs.setdefault("choices", tuple(e.value for e in enum_type))
        super(ActionEnum, self).__init__(**kwargs)
        self._enum = enum_type

    def __call__(self, parser, namespace, values, option_string=None):
        value = self._enum(values)
        setattr(namespace, self.dest, value)


def ParseEnumList(enum_type: type[Enum]) -> Callable[[str], list[Enum]]:
    """Implements flags comma separate lists of enum values.

    In the argument definition default values can be specified as a list of the actual enum values.
    On the command line the values do not have to be upper case (lowercase and mixed case are fine).

    Note: In many cases `ActionEnumList` provides a better solution for flag parsing.

    Example:
    ```
    parser.add_argument(
        "--myenum",
        default=[MyEnum.MY_DEFAULT],
        type=ParseEnumList(enum_type=MyEnum),
        help="Comma separated list of MyEnum {}.".format(set(MyEnum.__members__.keys())),
    )
    args=parser.parse_args(["--nyenum", "my_default,my_other"])
    ```
    """
    return lambda values: [
        enum_type.__getitem__(v.strip().upper()) for v in values.split(",") if v
    ]


class ActionEnumList(argparse.Action):
    """Argparse `action` for comma separated lists of Enum values.

    This action has the additional config:
    * allow_empty:    If False (the default), then an empty list is NOT allowed.
    * container_type: The container type (e.g. list or set).

    NOTE: The `type` is the exact Enum to work with. It will not be available as
          a property of the action.

    The string-ified default is available as `default_str` for consumprtion in
    `help`.

    Example:
    ```
    parser.add_argument(
        "--myenum",
        default=[MyEnum.MY_DEFAULT],
        type=MyEnum,
        action=ActionEnumList,
        allow_empty=True,
        container_type=set,
        help="Comma separated list of MyEnum values (default: %(default_str)s).",
    )
    args=parser.parse_args(["--nyenum", "my_default,my_other"])
    ```
    """

    class Choices:
        def __init__(self, action: argparse.Action):
            self._action: ActionEnumList = cast(ActionEnumList, action)

        def __repr__(self) -> str:
            return self._action._choices_list()

        def __iter__(self):
            yield self._action._choices()

        def __contains__(self, value: Any) -> bool:
            self._action._parse_list(value)
            return True

    def __init__(self, **kwargs):
        self._enum_type = kwargs.pop("type", None)  # NOTE: Not actually setting `type`.
        self._allow_empty = kwargs.pop("allow_empty", False)
        self._container_type = kwargs.pop("container_type", list)
        choices = kwargs.pop("choices", None)
        kwargs.setdefault("choices", self.Choices(action=self))
        super(ActionEnumList, self).__init__(**kwargs)
        if choices:
            raise argparse.ArgumentError(
                self,
                "Cannot (currently) restrict choices.",
            )
        if self._enum_type is None or not issubclass(self._enum_type, Enum):
            raise argparse.ArgumentError(
                self, f"Type must be an Enum, provided type is '{self._enum_type}'."
            )
        self.default = (
            self._parse_list(self.default) if self.default else self._container_type()
        )
        self.default_str = ", ".join([str(v.name) for v in self.default])

    def _choices(self) -> Iterable[str]:
        return sorted(self._enum_type.__members__.keys())

    def _choices_list(self) -> str:
        return ", ".join(self._choices())

    def _parse_list(self, values: str | Iterable[str | Enum] | None) -> Any:
        if values:
            if isinstance(values, str):
                values = values.split(",")
            elif isinstance(values, collections.abc.Iterable):
                strs = []
                enums = []
                for v in values:
                    if isinstance(v, str):
                        strs.extend(v.split(","))
                    elif isinstance(v, Enum):
                        enums.append(v)
                        strs.append(str(v))
                    else:
                        raise argparse.ArgumentError(
                            self,
                            f"Received bad sub value of type `{type(v)}` from values [{values}] of type `{type(values)}`, expected sub values of type `{self._enum_type}.",
                        )
                if enums and len(enums) == len(strs):
                    return self._container_type(enums)
                values = strs
        if not values or [v for v in values if isinstance(v, str) and not v]:
            if values:
                v_str = "sub value"
                given = f", given `{values}`"
            else:
                if self._allow_empty:
                    return self._container_type()
                v_str = "value"
                given = ""
            raise argparse.ArgumentError(
                self,
                f"Empty {v_str} is not allowed, chose at least one of [{self._choices_list()}]{given}.",
            )
        return self._container_type(
            [self._parse(v) for v in values if self._parse(v) is not None]
        )

    def _parse(self, value: str | Enum) -> Enum | None:
        if isinstance(value, self._enum_type):
            return value
        if not isinstance(value, str):
            raise argparse.ArgumentError(
                self,
                f"Sub values must be of type `str` or `{self._enum_type}`, given `{type(value)}`.",
            )
        if not value:
            raise argparse.ArgumentError(
                self,
                "Empty sub values are not allowed (that includes values containing `,,`).",
            )
        try:
            return self._enum_type.__getitem__(value.strip().upper())
        except KeyError as err:
            raise argparse.ArgumentError(
                self,
                f"Sub value '{value}' is not a valid {self._enum_type} value, chose from [{self._choices_list()}].",
            )

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self._parse_list(values))


def _MaybeMidnight(
    value: datetime, midnight: bool = False, tz: tzinfo = timezone.utc
) -> datetime:
    if midnight:
        return datetime.combine(
            value.date(), time(0, 0, 0, 0), tzinfo=value.tzinfo or tz
        )
    else:
        return datetime.combine(value.date(), value.time(), tzinfo=value.tzinfo or tz)


def _ParseDateTime(
    value: Any, midnight: bool = False, tz: tzinfo = timezone.utc
) -> datetime:
    if value is datetime:
        return _MaybeMidnight(cast(datetime, value), midnight=midnight, tz=tz)
    v = str(value)
    try:
        return _MaybeMidnight(datetime.fromisoformat(v), midnight=midnight, tz=tz)
    except ValueError as err:
        raise ValueError(f"Invalid date string: '{v}', {err}")


def ParseDateTimeOrTimeDelta(
    value: str,
    midnight: bool = False,
    default: Optional[datetime] = None,
    reference: Optional[datetime] = None,
    tz: tzinfo = timezone.utc,
    error_prefix: Optional[str] = None,
    error_suffix: Optional[str] = None,
) -> datetime:
    """Parse `value` as date or time delta in relation to reference.

    If `value` starts with either `-` or `+`, then it will be parsed as `timedelta`.
    Otherwise `value` will be parsed as Python [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601).

    Note: The returned type will have its timezone set from (in order precedence)):
          * The input time.
          * The reference time.
          * `datetime.now()`.
          * `tz`.
          * `timezone.utc`.

    Args:
        value:        The argument to parse. If this starts with a '-', then
                      the argument will be interpreted as a time delta.
        default:      The value to use if `value` is empty (defaults to `datetime.now`).
        midnight:     Whether to adjust the date/time to midnight of the day.
        reference:    The reference datetime to use for time deltas (defaults to `datetime.now`).
        tz:           Fallback timezone.
        error_prefix: An optional error prefix prepended to messages of raised errors. By default
                      this is "Bad timedelta value '". Together with error_suffix which defaults
                      to "'." this allows to provide additional error information.
                      For instance if the function is used to parse flags, then it is a
                      good idea to state which flag cannot be parsed.
        error_suffix: See `error_prefix`.
    """
    result: datetime
    if value.startswith(("-", "+")):
        seconds: float | None = timeparse(value)
        if seconds is None:
            if error_prefix is None:
                error_prefix = "Bad `timedelta` value, must be `int` seconds, not '"
            if error_suffix is None:
                error_suffix = "'."
            raise ValueError(f"{error_prefix}{value}{error_suffix}")
        result = (reference or datetime.now(tz=tz)) + timedelta(seconds=seconds or 0)
    elif value:
        result = _ParseDateTime(value, midnight=midnight, tz=tz)
    else:
        result = default or datetime.now(tz=tz)
    if not result.tzinfo:
        result = datetime.combine(
            result.date(),
            result.time(),
            tzinfo=(reference or datetime.now(tz=tz)).tzinfo or tz,
        )
    if midnight:
        return datetime.combine(result.date(), time(), tzinfo=result.tzinfo)
    return result


class ActionDateTimeOrTimeDelta(argparse.Action):
    """Action to parse (or verify) a `datetime` with `timedelta` support.

    If `value` starts with either `-` or `+`, then it will be parsed as `timedelta`.
    Otherwise `value` will be parsed as Python [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601).

    The resulting value is either a `datetime` or a `str` value if `verify_only==True`.

    This action has the additional config:
    * default:      The value to use if `value` is empty (defaults to `datetime.now`).
                    This must be `None` or of type `datetime`, `str`.
    * midnight:     Whether to adjust the date/time to midnight of the day.
    * reference:    The reference datetime to use for time deltas (defaults to `datetime.now`).
                    This must be `None` or of type `datetime`, `str`.
    * tz:           Fallback timezone (defaults to `timezone.utc`).
    * verify_only:  If True (False is default), then the input will only be verified. The resulting
                    value is the input and its type is `str`. The sole purpose is to verify an input
                    but process it later, which allows one flag to provide its value as a reference
                    to other flags. Once the arguments have been parsed, their values can be post
                    processed with `ParseDateTimeOrTimeDelta`. Therefore in this mode all errors
                    will be raied, but no modification will be applied. However, the default value
                    will still be applied.

    Example:
    ```
    parser.add_argument(
        "--time",
        action=ActionDateTimeOrTimeDelta,
        help="Parses flag as a `datetime` value; or a `timedelta` value relative to `reference`.",
    )
    args=parser.parse_args(["--time", "+1week"])
    ```
    """

    def __init__(self, **kwargs) -> None:
        self._verify_only = kwargs.pop("verify_only", False)
        self._midnight = kwargs.pop("midnight", False)
        self._tz = kwargs.pop("tz", timezone.utc)
        self._type = kwargs.pop("type", str if self._verify_only else datetime)
        now = datetime.now(self._tz)
        default_v = kwargs.pop("default", now)
        reference = kwargs.pop("reference", default_v)

        super(ActionDateTimeOrTimeDelta, self).__init__(**kwargs)
        if self._verify_only:
            if self._type != str:
                raise argparse.ArgumentError(
                    self,
                    f"Type (for verification) must be `str`, provided type is `{self._type}`.",
                )
        else:
            if self._type != datetime:
                raise argparse.ArgumentError(
                    self, f"Type must be `datetime`, provided type is `{self._type}`."
                )
        # Property `_default_dt` (DateTime) is required for further parsing.
        self._default_dt: datetime = (
            self._ParseDateTimeStrict(
                name="default",
                value=default_v,
                midnight=self._midnight,
                tz=self._tz,
            )
            or now
        )
        # The actual default must be set to a string value for `verify_only`.
        self.default: datetime | str = (
            str(self._default_dt) if self._verify_only else self._default_dt
        )
        self._reference: datetime = (
            self._ParseDateTimeStrict(
                name="reference",
                value=reference,
                midnight=self._midnight,
                tz=self._tz,
            )
            or now
        )

    def _ParseDateTimeStrict(
        self,
        name: str,
        value: Any,
        midnight: bool = False,
        tz: tzinfo = timezone.utc,
    ) -> datetime | None:
        if value is None or value == "":
            return None
        elif not isinstance(value, str) and not isinstance(value, datetime):
            raise argparse.ArgumentError(
                self,
                f"{name.capitalize()} value must be None or of type `datetime` or `str`, provided is `{type(value)}`.",
            )
        try:
            return _ParseDateTime(value, midnight=self._midnight, tz=self._tz)
        except ValueError as error:
            raise argparse.ArgumentError(
                self,
                f"{name.capitalize()} value `{value}` cannot be parsed as `datetime`.",
            )

    def _parse(self, value: str) -> datetime:
        try:
            return ParseDateTimeOrTimeDelta(
                value=value,
                default=self._default_dt,
                midnight=self._midnight,
                reference=self._reference,
                tz=self._tz,
            )
        except ValueError as error:
            raise argparse.ArgumentError(self, f"{error}")

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        if values is None:
            return setattr(namespace, self.dest, None)
        result: Any
        if isinstance(values, list):
            result = [self._parse(v) for v in values]
        elif isinstance(values, str):
            result = self._parse(values)
        elif isinstance(values, datetime):
            result = values
        else:
            raise argparse.ArgumentError(self, f"Unexpected value type {type(values)}.")
        if self._verify_only:
            setattr(namespace, self.dest, str(values))
        else:
            setattr(namespace, self.dest, result)


def ParseByteSize(
    value: str,
    *,
    suffix_case_sensitive: bool | None = None,
    unit: str = "B",
    unit_case_sensitive: bool = False,
    unit_required: bool = False,
) -> int:
    """Parses size values (default bytes).

    Args:
        * value:                 The value string to parse.
        * suffix_case_sensitive: Whether the suffix (e.g. `Ki`) is case sensitive (defaults to `unit_case_sensitive`).
        * unit_case_sensitive:   Whether the unit is case-sensitive (default is False).
        * unit_required:         Whether the unit is required, this defaults to `True` if `unit` is specified.
        * unit:                  The expected unit (defaults to `B`).
    """
    if not value:
        raise ValueError("value must not be empty.")
    original = value
    value = str(value)  # If not mypy.
    if not unit_case_sensitive and value.lower().endswith(unit.lower()):
        value = value[: -len(unit)]
    elif value.endswith(unit):
        value = value.removesuffix(unit)
    elif unit_required:
        if value.lower().endswith(unit.lower()):
            lower_case = " (found via case insensitive search)"
        else:
            lower_case = ""
        raise ValueError(f"value does not have required unit `{unit}`{lower_case}.")
    _SUFFIXES: dict[str, int] = {
        "": 1,
        "K": 1000**1,  # kilo
        "M": 1000**2,  # mega
        "G": 1000**3,  # giga
        "T": 1000**4,  # tera
        "P": 1000**5,  # peta
        "E": 1000**6,  # exa
        "Z": 1000**7,  # zetta
        "Y": 1000**8,  # yotta
        "X": 1000**9,  # xona"
        "Ki": 1024**1,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "Pi": 1024**5,
        "Ei": 1024**6,
        "Zi": 1024**7,
        "Yi": 1024**8,
        "Xi": 1024**9,
    }
    _REGEX = re.compile(f"([0-9]*[.]?[0-9]*)[ ]?({'|'.join(_SUFFIXES.keys())})?")
    value_str = value
    if value.endswith(("i", "I")):
        value_nc_str = value_str[:-1].upper() + "i"
    else:
        value_nc_str = value_str.upper()
    if value_str and not suffix_case_sensitive:
        value_str = value_nc_str
    match = _REGEX.fullmatch(value_str)
    if not match:
        if _REGEX.fullmatch(value_nc_str) or value_str.endswith(("i", "I")):
            raise ValueError(f"value has bad suffix case, got '{original}'.")
        raise ValueError(
            f"value does not match pattern (not a valid byte size), got '{original}'."
        )
    number = match.group(1)
    if number == ".":
        raise ValueError("value cannot be '.'.")
    result = float(number) if number.find(".") > -1 else int(number)
    if match.group(2):
        factor = _SUFFIXES.get(match.group(2) or "", 0)
        if not factor:
            raise ValueError(
                f"value has unsupported suffix ({match.group(2)}), got '{original}'."
            )
    else:
        factor = 1
    result *= factor
    return int(result)


class ActionByteSize(argparse.Action):
    """Parses arguments as bytes, supporting KB, MB, GB, TB, PB, EB as well as KiB etc. suffixes.

    This action has the additional config:
    * default:               Can be a number of type `int` or `float`.
    * unit:                  The expected unit (defaults to `B`).
    * unit_required:         Whether the unit is required, this defaults to `True` if `unit` is specified.
    * unit_case_sensitive:   Whether the unit is case-sensitive (default is False).
    * suffix_case_sensitive: Whether the suffix (e.g. `Ki`) is case sensitive (defaults to `unit_case_sensitive`).
    """

    def __init__(self, **kwargs) -> None:
        self.unit = kwargs.pop("unit", "B")
        self.unit_required = bool(kwargs.pop("unit_required", self.unit))
        self.unit_case_sensitive = bool(kwargs.pop("unit_case_sensitive", False))
        self.suffix_case_sensitive = bool(
            kwargs.pop("suffix_case_sensitive", self.unit_case_sensitive)
        )
        default: Any = kwargs.pop("default", None)
        if default is None or default == "":
            default = None
        elif isinstance(default, int) or isinstance(default, float):
            default = f"{default}{self.unit}"
        super(ActionByteSize, self).__init__(default=default, **kwargs)
        if default is None:
            self.default = None

    def _parse(self, value: Any) -> int | None:
        if value is int:
            return value
        else:
            try:
                return ParseByteSize(
                    value=str(value),
                    suffix_case_sensitive=self.suffix_case_sensitive,
                    unit=self.unit,
                    unit_case_sensitive=self.unit_case_sensitive,
                    unit_required=self.unit_required,
                )
            except ValueError as error:
                raise argparse.ArgumentError(self, str(error))
            except Exception as error:
                raise error

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        if values is None:
            setattr(namespace, self.dest, None)
        elif isinstance(values, list):
            setattr(namespace, self.dest, [self._parse(str(v)) for v in values])
        else:
            setattr(namespace, self.dest, self._parse(str(values)))
