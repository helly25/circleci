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

"""Tests for flags.py."""

import argparse
import unittest
from dataclasses import dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from freezegun import freeze_time
from parameterized import param, parameterized

import mbo.app.flags

_NOW = "2024-08-28T14:15:16.123Z"


def ActionArgs(name: str = "flag", **kwargs) -> dict[str, Any]:
    kwargs["name"] = name
    return kwargs


class TestEnum(Enum):
    ONE = 1
    TWO = 2
    TRE = 3
    FOR = 4


def dataclass_as_param(cls):
    def iter_as_param(self):
        if not is_dataclass(self):
            raise TypeError(
                f"Decorator 'dataclass_as_param' only works with dataclasses, {type(self)} is not."
            )
        return iter([self])

    return type(cls.__name__, (cls,), {"__iter__": iter_as_param})


class FlagsTest(unittest.TestCase):
    """Tests for flags.py."""

    @dataclass_as_param
    @dataclass(kw_only=True)
    class ParseDateTimeOrTimeDeltaTest:
        expected: str
        expected_error: type | None = None
        input: str
        midnight: bool = False
        default: str | None = None
        reference: str | None = None
        error_prefix: str | None = None
        error_suffix: str | None = None
        now: str = _NOW

    @parameterized.expand(
        [
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-04-02T14:00:00Z",
                input="2024-04-02T14",
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-04-02T01:02:03.004Z",
                input="2024-04-02T01:02:03.004Z",
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-04-02T00:00:00Z",
                input="2024-04-02T13:14:15.123Z",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-21T14:15:16.123Z",
                input="-1w",
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-29T14:15:16.123Z",
                input="+1d",
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-29T00:00:00Z",
                input="+1d",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-14 01:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=False,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-14 00:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="2024-08-14 00:00:00Z",
                input="+0s",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="Bad timedelta value '+0 NOPE'.",
                expected_error=ValueError,
                input="+0 NOPE",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                expected="<prefix>+0 NOPE<suffix>",
                expected_error=ValueError,
                input="+0 NOPE",
                reference="2024-08-14 17",
                midnight=True,
                error_prefix="<prefix>",
                error_suffix="<suffix>",
            ),
        ]
    )
    def test_ParseDateTimeOrTimeDelta(self, test: ParseDateTimeOrTimeDeltaTest):
        with freeze_time(datetime.fromisoformat(test.now)):
            try:
                self.assertEqual(
                    (
                        datetime.fromisoformat(test.expected)
                        if not test.expected_error
                        else None
                    ),
                    mbo.app.flags.ParseDateTimeOrTimeDelta(
                        value=test.input,
                        midnight=test.midnight,
                        default=(
                            datetime.fromisoformat(test.default)
                            if test.default
                            else None
                        ),
                        reference=(
                            datetime.fromisoformat(test.reference)
                            if test.reference
                            else None
                        ),
                        error_prefix=test.error_prefix,
                        error_suffix=test.error_suffix,
                    ),
                )
            except Exception as error:
                self.assertIsNotNone(test.expected_error, error)
                if test.expected_error:
                    self.assertEqual(test.expected, str(error))
                    self.assertEqual(type(error), test.expected_error)

    @dataclass_as_param
    @dataclass(kw_only=True)
    class FlagTestData:
        test: str
        expected: Any
        expected_error: type | None = None
        action: dict[str, Any]
        input: list[str]

    def FlagTest(self, test: FlagTestData) -> None:
        try:
            parser = argparse.ArgumentParser(exit_on_error=False)
            name = test.action.pop("name", "flag")
            parser.add_argument(name, **test.action)
            args = parser.parse_args(test.input)
            self.assertEqual(
                test.expected, args.flag, "Bad value in test: " + test.test
            )
        except argparse.ArgumentError as error:
            self.assertIsNotNone(test.expected_error, error)
            if test.expected_error:
                self.assertEqual(
                    test.expected, str(error), "Bad error message in test: " + test.test
                )
                self.assertEqual(
                    type(error),
                    test.expected_error,
                    "Bad error type in test: " + test.test,
                )

    @parameterized.expand(
        [
            FlagTestData(
                test="Set a single value to a list.",
                expected=[TestEnum.ONE],
                action=ActionArgs(
                    type=TestEnum,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["one"],
            ),
            FlagTestData(
                test="Setting an empty vlaue requires `allow_empty=True`.",
                expected="argument --flag: Empty value is not allowed, chose at least one of [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["--flag="],
            ),
            FlagTestData(
                test="Setting an empty vlaue requires `allow_empty=True` (not False).",
                expected="argument --flag: Empty value is not allowed, chose at least one of [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.ActionEnumList,
                    allow_empty=False,
                ),
                input=["--flag="],
            ),
            FlagTestData(
                test="Setting an empty vlaue requires with `allow_empty=True` works.",
                expected=[],
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.ActionEnumList,
                    allow_empty=True,
                ),
                input=["--flag="],
            ),
            FlagTestData(
                test="Default values work.",
                expected=[TestEnum.TWO],
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[TestEnum.TWO],
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=[],
            ),
            FlagTestData(
                test="Default values work: They can even bypass the type.",
                expected="Something else",
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default="Something else",
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=[],
            ),
            FlagTestData(
                test="Multile, possible repeated values and mixed case.",
                expected=[TestEnum.TWO, TestEnum.ONE, TestEnum.TWO],
                action=ActionArgs(
                    type=TestEnum,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["two,oNe,TWO"],
            ),
            FlagTestData(
                test="Multile values in a set.",
                expected=set([TestEnum.ONE, TestEnum.TWO]),
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["two,oNe,TWO"],
            ),
            FlagTestData(
                test="Repeated flag for list.",
                expected=[
                    TestEnum.TWO,
                    TestEnum.FOR,
                    TestEnum.ONE,
                    TestEnum.TRE,
                    TestEnum.TWO,
                ],
                action=ActionArgs(
                    nargs="+",
                    type=TestEnum,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["two,for", "one,tre", "TWO"],
            ),
            FlagTestData(
                test="Repeated flag for list.",
                expected={TestEnum.TWO, TestEnum.FOR, TestEnum.ONE, TestEnum.TRE},
                action=ActionArgs(
                    nargs="+",
                    type=TestEnum,
                    container_type=set,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["two,for", "one,tre", "TWO"],
            ),
        ]
    )
    def test_EnumListAction(self, test: FlagTestData):
        self.FlagTest(test)

    @parameterized.expand(
        [
            FlagTestData(
                test="Parse from iso datetime.",
                expected=datetime(
                    year=2024,
                    month=1,
                    day=30,
                    hour=13,
                    minute=14,
                    second=51,
                    tzinfo=timezone.utc,
                ),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                ),
                input=["2024-01-30T13:14:51"],
            ),
            FlagTestData(
                test="Parse from iso datetime applying midnight.",
                expected=datetime(year=2024, month=1, day=30, tzinfo=timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    midnight=True,
                ),
                input=["2024-01-30T13:14:51"],
            ),
            FlagTestData(
                test="Parse from short datetime.",
                expected=datetime(year=2024, month=1, day=30, tzinfo=timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                ),
                input=["20240130"],
            ),
            FlagTestData(
                test="Parse from short datetime, bad input.",
                expected="argument flag: Invalid date string: '20240230', day is out of range for month",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                ),
                input=["20240230"],
            ),
            FlagTestData(
                test="Parse from timedelta.",
                expected=datetime(2024, 9, 4, 14, 15, 16, 123000, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_NOW,
                ),
                input=["+1w"],
            ),
            FlagTestData(
                test="Parse from timedelta applying midnight.",
                expected=datetime(2024, 9, 4, 0, 0, 0, 0, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_NOW,
                    midnight=True,
                ),
                input=["+1w"],
            ),
            FlagTestData(
                test="Parse from negative timedelta.",
                expected=datetime(2024, 8, 21, 14, 15, 16, 123000, timezone.utc),
                action=ActionArgs(
                    "--flag",
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_NOW,
                ),
                input=["--flag=-1w"],
            ),
        ]
    )
    def test_DateTimeOrTimeDeltaAction(self, test: FlagTestData):
        self.FlagTest(test)


if __name__ == "__main__":
    unittest.main()
