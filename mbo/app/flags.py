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
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Callable, Iterable, Optional, cast

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

    Note: In many cases `EnumListAction` provides a better solution for flag parsing.

    Example:
    ```
    parser.add_argument(
        "--myenum",
        default=[MyEnum.MY_DEFAULT],
        type=EnumListParser(enum_type=MyEnum),
        help="Comma separated list of MyEnum {}.".format(set(MyEnum.__members__.keys())),
    )
    args=parser.parse_args({"--nyenum", "my_default,my_other"})
    ```
    """
    return lambda values: [
        enum_type.__getitem__(v.strip().upper()) for v in values.split(",") if v
    ]


class EnumListAction(argparse.Action):
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
        action=EnumListAction,
        allow_empty=False,
        container_type=set,
        help="Comma separated list of MyEnum values.",
    )
    args=parser.parse_args({"--nyenum", "my_default,my_other"})
    ```
    """

    class Choices:
        def __init__(self, action: argparse.Action):
            self._action: EnumListAction = cast(EnumListAction, action)

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
        super(EnumListAction, self).__init__(**kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            values = ",".join(values)
        value = self._container_type(
            [
                self._enum_type.__getitem__(v.strip().upper())
                for v in values.split(",")
                if v
            ]
        )
        setattr(namespace, self.dest, value)


def ParseDateTimeOrDelta(
    arg: str,
    midnight: bool = False,
    default: Optional[datetime] = None,
    reference: Optional[datetime] = None,
    error_prefix: Optional[str] = None,
    error_suffix: Optional[str] = None,
) -> datetime:
    """Parse `arg` as date or time delta in relation to reference.

    If `arg` starts with either `-` or `+`, then it will be parsed as `timedelta`.
    Otherwise `arg` will be parsed as Python [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601).

    Note: The returned type will have its timezone set from (in order precedence)):
          * The input time.
          * The reference time.
          * `datetime.now()`.
          * `timezone.utc`.

    Args:
        arg:          The argument to parse. If this starts with a '-', then
                      the argument will be interpreted as a time delta.
        midnight:     Whether to adjust the date/time to midnight of the day.
        default:      The value to use if `arg` is empty (defaults to `datetime.now`).
        reference:    The reference datetime to use for time deltas (defaults to `datetime.now`).
        error_prefix: An optional error prefix prepended to messages of raised errors. By default
                      this is "Bad timedelta value '". Together with error_suffix which defaults
                      to "'." this allows to provide additional error information.
                      For instance if the function is used to parse flags, then it is a
                      good idea to state which flag cannot be parsed.
        error_suffix: See `error_prefix`.
    """
    result: datetime
    if arg.startswith(("-", "+")):
        seconds: float | None = timeparse(arg)
        if type(seconds) == type(None):
            if error_prefix is None:
                error_prefix = "Bad timedelta value '"
            if error_suffix is None:
                error_suffix = "'."
            raise ValueError(f"{error_prefix}{arg}{error_suffix}")
        result = (reference or datetime.now()) + timedelta(seconds=seconds or 0)
    elif arg:
        result = datetime.fromisoformat(arg)
    else:
        result = default or datetime.now()
    if not result.tzinfo:
        tzinfo = (reference or datetime.now()).tzinfo or timezone.utc
        result = datetime.combine(result.date(), result.time(), tzinfo=tzinfo)
    if midnight:
        return datetime.combine(result.date(), time(), tzinfo=result.tzinfo)
    return result
