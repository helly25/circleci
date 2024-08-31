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

"""A flag support library."""

import argparse
import collections
from datetime import datetime, time, timedelta, timezone, tzinfo
from enum import Enum
from typing import Any, Callable, Iterable, Optional, cast

from pytimeparse.timeparse import timeparse


class EnumAction(argparse.Action):
    """Argparse action that handles single Enum values."""

    def __init__(self, **kwargs):
        enum_type = kwargs.pop("type", None)
        if enum_type is None or not issubclass(enum_type, Enum):
            raise ValueError(f"Type must be an Enum, provided type is '{enum_type}'.")

        kwargs.setdefault("choices", tuple(e.value for e in enum_type))
        super(EnumAction, self).__init__(**kwargs)
        self._enum = enum_type

    def __call__(self, parser, namespace, values, option_string=None):
        value = self._enum(values)
        setattr(namespace, self.dest, value)


def EnumListParser(enum_type: type[Enum]) -> Callable[[str], list[Enum]]:
    """Implements flags comma separate lists of enum values.

    In the argument definition default values can be specified as a list of the actual enum values.
    On the command line the values do not have to be upper case (lowercase and mixed case are fine).

    Note: In many cases `ActionEnumList` provides a better solution for flag parsing.

    Example:
    ```
    parser.add_argument(
        "--myenum",
        default=[MyEnum.MY_DEFAULT],
        type=EnumListParser(enum_type=MyEnum),
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

    Example:
    ```
    parser.add_argument(
        "--myenum",
        default=[MyEnum.MY_DEFAULT],
        type=MyEnum,
        action=ActionEnumList,
        allow_empty=False,
        container_type=set,
        help="Comma separated list of MyEnum values.",
    )
    args=parser.parse_args(["--nyenum", "my_default,my_other"])
    ```
    """

    class Choices:
        def __init__(self, action: argparse.Action):
            self._action: ActionEnumList = cast(ActionEnumList, action)

        def choices(self) -> Iterable[str]:
            return sorted(self._action._enum_type.__members__.keys())

        def choices_list(self) -> str:
            return ", ".join(self.choices())

        def __repr__(self) -> str:
            return self.choices_list()

        def __iter__(self):
            yield self.choices()

        def __contains__(self, value: str) -> bool:
            if value == "":
                if self._action._allow_empty:
                    return True
                raise argparse.ArgumentError(
                    self._action,
                    f"Empty value is not allowed, chose at least one of [{self.choices_list()}].",
                )
            for v in value.split(","):
                v = v.strip()
                if not v:
                    raise argparse.ArgumentError(
                        self._action,
                        "Empty sub values are not allowed (that means values containing `,,`).",
                    )
                if v.upper() not in self.choices():
                    raise argparse.ArgumentError(
                        self._action,
                        f"Sub value '{v}' is not a valid {self._action._enum_type} value, chose from [{self.choices_list()}].",
                    )
            return True

    def __init__(self, **kwargs):
        self._enum_type = kwargs.pop("type", None)
        self._allow_empty = kwargs.pop("allow_empty", False)
        self._container_type = kwargs.pop("container_type", list)

        if self._enum_type is None or not issubclass(self._enum_type, Enum):
            raise ValueError(
                f"Type must be an Enum, provided type is '{self._enum_type}'."
            )

        kwargs.setdefault("choices", self.Choices(action=self))
        super(ActionEnumList, self).__init__(**kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        if isinstance(values, list):
            values_str = ",".join(values)
        elif type(values) == str:
            values_str = values
        else:
            raise argparse.ArgumentError(self, "Unexpected value type {type(values)}.")
        value = self._container_type(
            [
                self._enum_type.__getitem__(v.strip().upper())
                for v in values_str.split(",")
                if v
            ]
        )
        setattr(namespace, self.dest, value)


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
    value: str | datetime, midnight: bool = False, tz: tzinfo = timezone.utc
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
        if type(seconds) == type(None):
            if error_prefix is None:
                error_prefix = "Bad timedelta value '"
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

    This action has the additional config:
    * default:      The value to use if `value` is empty (defaults to `datetime.now`).
    * midnight:     Whether to adjust the date/time to midnight of the day.
    * reference:    The reference datetime to use for time deltas (defaults to `datetime.now`).
    * tz:           Fallback timezone.
    * verify_only:  If True (False is default), then the input will only be verified. The resulting
                    value is the input and its type is `str`.

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
        try:
            if default_v:
                default = _ParseDateTime(
                    default_v, midnight=self._midnight, tz=self._tz
                )
            else:
                default = None
        except ValueError as error:
            raise argparse.ArgumentError(
                self, f"Default value `{default_v}` cannot be parsed as `datetime`."
            )
        if self._verify_only:
            self.default = str(default or default_v)
        elif type(default) == datetime:
            self.default = default
        else:
            raise argparse.ArgumentError(
                self,
                f"Default value must be of type datetime, provided is `{type(default)}`.",
            )
        try:
            self._reference: datetime = _ParseDateTime(
                reference or now, midnight=self._midnight, tz=self._tz
            )
        except ValueError as error:
            raise argparse.ArgumentError(
                self, f"Reference value `{reference}` cannot be parsed as `datetime`."
            )

    def _parse(self, value) -> datetime:
        try:
            return ParseDateTimeOrTimeDelta(
                value=value,
                default=self.default,
                midnight=self._midnight,
                reference=self._reference,
                tz=self._tz,
            )
        except ValueError as error:
            raise argparse.ArgumentError(self, f"{error}")

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        result: Any
        if values is list:
            result = [self._parse(v) for v in values]
        elif type(values) == str:
            result = self._parse(values)
        else:
            raise argparse.ArgumentError(self, "Unexpected value type {type(values)}.")
        if self._verify_only:
            setattr(namespace, self.dest, values)
        else:
            setattr(namespace, self.dest, result)
