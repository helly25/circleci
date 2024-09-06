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

_NOW_DATETIME = datetime(2024, 8, 28, 14, 15, 16, 789000, timezone.utc)

_REF_DATETIME = datetime(2023, 7, 28, 20, 21, 23, 456000, timezone.utc)


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
        test: str
        expected: str
        expected_error: type | None = None
        input: str
        midnight: bool = False
        default: str | None = None
        reference: str | None = None
        error_prefix: str | None = None
        error_suffix: str | None = None
        now: datetime = _NOW_DATETIME

    @parameterized.expand(
        [
            ParseDateTimeOrTimeDeltaTest(
                test="Parse and expand.",
                expected="2024-04-02T14:00:00Z",
                input="2024-04-02T14",
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Parse already expanded.",
                expected="2024-04-02T01:02:03.004Z",
                input="2024-04-02T01:02:03.004Z",
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Apply midnight.",
                expected="2024-04-02T00:00:00Z",
                input="2024-04-02T13:14:15.123Z",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Negative time diff, 1 week.",
                expected="2024-08-21T14:15:16.789Z",
                input="-1w",
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Positive time diff, 1 week.",
                expected="2024-08-29T14:15:16.789Z",
                input="+1d",
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Positive time diff, 1 day.",
                expected="2024-08-29T00:00:00Z",
                input="+1d",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Positive time diff 8 hours.",
                expected="2024-08-14 01:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=False,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Positive time diff from reference.",
                expected="2024-08-14 00:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Zero time diff",
                expected="2024-08-14 00:00:00Z",
                input="+0s",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Bad time diff",
                expected="Bad `timedelta` value, must be `int` seconds, not '+0 NOPE'.",
                expected_error=ValueError,
                input="+0 NOPE",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrTimeDeltaTest(
                test="Error prefix and suffix.",
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
        self._testMethodDoc = "TEST: " + test.test
        with freeze_time(_NOW_DATETIME):
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
        now: datetime = _NOW_DATETIME

    def FlagTest(self, test: FlagTestData) -> None:
        self._testMethodDoc = "TEST: " + test.test
        with freeze_time(_NOW_DATETIME):
            try:
                parser = argparse.ArgumentParser(exit_on_error=False)
                name = test.action.pop("name", "flag")
                parser.add_argument(name, **test.action)
                args = parser.parse_args(test.input)
                self.assertEqual(
                    test.expected, args.flag, "Bad value in test: " + test.test
                )
                self.assertIsInstance(args.flag, type(test.expected))
            except argparse.ArgumentError as error:
                self.assertIsNotNone(test.expected_error, error)
                if test.expected_error:
                    self.assertEqual(
                        test.expected,
                        str(error),
                        "Bad error message in test: " + test.test,
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
                test="Setting an empty value requires `allow_empty=True`.",
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
                test="Setting an empty value requires `allow_empty=True` (not False).",
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
                test="Setting an empty default value requires `allow_empty=True`.",
                expected=[],
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.ActionEnumList,
                    allow_empty=True,
                ),
                input=[],
            ),
            FlagTestData(
                test="Setting an empty value requires `allow_empty=True`.",
                expected=[],
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default=[TestEnum.FOR],
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
                test="Default values cannot bypass the type.",
                expected="argument --flag: Sub value 'Something else' is not a valid <enum 'TestEnum'> value, chose from [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    type=TestEnum,
                    default="Something else",
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=[],
            ),
            FlagTestData(
                test="Cannot (currently) restrict choices.",
                expected="argument flag: Cannot (currently) restrict choices.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    action=mbo.app.flags.ActionEnumList,
                    choices=[TestEnum.ONE, TestEnum.TWO],
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
            FlagTestData(
                test="Repeated flag values still disallow empty values by default.",
                expected="argument flag: Empty value is not allowed, chose at least one of [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    default=[TestEnum.TWO],
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=[""],
            ),
            FlagTestData(
                test="Repeated flag values may allow empty values.",
                expected=set(),
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    default=[TestEnum.TWO],
                    allow_empty=True,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=[""],
            ),
            FlagTestData(
                test="Repeated flag values may allow empty values but not empty sub values.",
                expected="argument flag: Empty sub value is not allowed, chose at least one of [FOR, ONE, TRE, TWO], given `['one', '', 'tre']`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    default=[TestEnum.TWO],
                    # allow_empty=True,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["one,,tre"],
            ),
            FlagTestData(
                test="Repeated flag values may not have empty sub values.",
                expected="argument flag: Empty sub value is not allowed, chose at least one of [FOR, ONE, TRE, TWO], given `['one', '', 'tre']`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    default=[TestEnum.TWO],
                    allow_empty=False,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["one,,tre"],
            ),
            FlagTestData(
                test="Repeated flag values may not have empty sub values even if empty values are allowed.",
                expected="argument flag: Empty sub value is not allowed, chose at least one of [FOR, ONE, TRE, TWO], given `['one', '', 'tre']`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    default=[TestEnum.TWO],
                    allow_empty=True,
                    action=mbo.app.flags.ActionEnumList,
                ),
                input=["one,,tre"],
            ),
        ]
    )
    def test_ActionEnumList(self, test: FlagTestData):
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
                test="Verify only: Parse from iso datetime.",
                expected="2024-01-30T13:14:51",
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    verify_only=True,
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
                test="Verify only: Parse from short datetime.",
                expected="20240130",  # Midnight not applied.
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    verify_only=True,
                ),
                input=["20240130"],
            ),
            FlagTestData(
                test="Parse default from short datetime.",
                expected=datetime(year=2024, month=2, day=3, tzinfo=timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    default="20240203",
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Use default from datetime.",
                expected=datetime(year=2024, month=2, day=4, tzinfo=timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    default=datetime(2024, 2, 4),
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Use bad type for default.",
                expected="argument flag: Default value must be None or of type `datetime` or `str`, provided is `<class 'bool'>`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    default=False,
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Verify only: Use bad type for default.",
                expected="argument flag: Default value must be None or of type `datetime` or `str`, provided is `<class 'bool'>`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    default=False,
                    nargs="?",
                    verify_only=True,
                ),
                input=[],
            ),
            FlagTestData(
                test="Use default for default which is now.",
                expected=_NOW_DATETIME,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Verify only: Use default for default which is now.",
                expected=str(_NOW_DATETIME),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    nargs="?",
                    verify_only=True,
                ),
                input=[],
            ),
            FlagTestData(
                test="Non present flag with default.",
                expected=str(_NOW_DATETIME),
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    "--flag",
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    verify_only=True,
                ),
                input=[],
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
                test="Verify only: Parse from short datetime, bad input.",
                expected="argument flag: Invalid date string: '20240230', day is out of range for month",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    verify_only=True,
                ),
                input=["20240230"],
            ),
            FlagTestData(
                test="Parse from time diff.",
                expected=datetime(2023, 8, 4, 20, 21, 23, 456000, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                ),
                input=["+1w"],
            ),
            FlagTestData(
                test="Parse from time diff applying midnight.",
                expected=datetime(2023, 8, 4, 0, 0, 0, 0, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                    midnight=True,
                ),
                input=["+1w"],
            ),
            FlagTestData(
                test="Verify only: Parse from time diff.",
                expected="+1w",
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                    verify_only=True,
                ),
                input=["+1w"],
            ),
            FlagTestData(
                test="Parse flag from negative time diff.",
                expected=datetime(2023, 7, 21, 20, 21, 23, 456000, timezone.utc),
                action=ActionArgs(
                    "--flag",
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                ),
                input=["--flag=-1w"],
            ),
            FlagTestData(
                test="Parse arg from negative time diff to reference datetime.",
                expected=datetime(2023, 7, 21, 20, 21, 23, 456000, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                ),
                input=["--", "-1w"],
            ),
            FlagTestData(
                test="Parse arg from negative time diff to reference str.",
                expected=datetime(2023, 7, 21, 20, 21, 23, 456000, timezone.utc),
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=str(_REF_DATETIME),
                ),
                input=["--", "-1w"],
            ),
            FlagTestData(
                test="Parse from bad time diff value.",
                expected="argument flag: Bad `timedelta` value, must be `int` seconds, not '+1'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                ),
                input=["+1"],
            ),
            FlagTestData(
                test="Verify only: Parse from bad time diff value.",
                expected="argument flag: Bad `timedelta` value, must be `int` seconds, not '+1'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=_REF_DATETIME,
                    verify_only=True,
                ),
                input=["+1"],
            ),
            FlagTestData(
                test="Parse from bad time diff type.",
                expected="argument flag: Reference value must be None or of type `datetime` or `str`, provided is `<class 'bool'>`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=False,
                ),
                input=["+1"],
            ),
            FlagTestData(
                test="Verify only: Parse from bad time diff type.",
                expected="argument flag: Reference value must be None or of type `datetime` or `str`, provided is `<class 'bool'>`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionDateTimeOrTimeDelta,
                    reference=False,
                    verify_only=True,
                ),
                input=["+1"],
            ),
        ]
    )
    def test_ActionDateTimeOrTimeDelta(self, test: FlagTestData):
        self.FlagTest(test)

    @parameterized.expand(
        [
            FlagTestData(
                test="Parse default None.",
                expected=None,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Parse empty.",
                expected="argument flag: value must not be empty.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=[""],
            ),
            FlagTestData(
                test="Parse default value.",
                expected=25,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    default=25,
                    nargs="?",
                ),
                input=[],
            ),
            FlagTestData(
                test="Parse zero.",
                expected="argument flag: value does not have required unit `B`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=["0"],
            ),
            FlagTestData(
                test="Parse zero, no unit required.",
                expected=0,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit_required=False,
                ),
                input=["0"],
            ),
            FlagTestData(
                test="Unit only is invalid.",
                expected="argument flag: value cannot be empty.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=["B"],
            ),
            FlagTestData(
                test="Unit only is invalid.",
                expected="argument flag: value cannot be empty.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="0",
                ),
                input=["0"],
            ),
            FlagTestData(
                test="Parse zero bytes.",
                expected=[0, 0, 0, 0, 0],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                ),
                input=["0B", "0b", "0.b", ".0b", "0.0b"],
            ),
            FlagTestData(
                test="Parse '.' is invalid.",
                expected="argument flag: value cannot be '.'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=[".B"],
            ),
            FlagTestData(
                test="Parse '.ib' is invalid.",
                expected="argument flag: value has bad suffix case, got '.ib'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit_case_sensitive=False,
                    unit_required=True,
                    suffix_case_sensitive=False,
                ),
                input=[".ib"],
            ),
            FlagTestData(
                test="Parse zero X.",
                expected=0,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                ),
                input=["0x"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive, finding z.",
                expected="argument flag: value does not have required unit `X`.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                ),
                input=["0z"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive.",
                expected="argument flag: value does not have required unit `X` (found via case insensitive search).",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                ),
                input=["0x"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive with suffix.",
                expected="argument flag: value has bad suffix case, got '0kX'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                ),
                input=["0kX"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive with i-suffix.",
                expected="argument flag: value has bad suffix case, got '0KIX'.",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                ),
                input=["0KIX"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive with i-suffix (correct case).",
                expected=0,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                ),
                input=["0KiX"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive with suffix (ignore-case).",
                expected=0,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=True,
                    suffix_case_sensitive=False,
                ),
                input=["0kX"],
            ),
            FlagTestData(
                test="Parse zero X, case sensitive, correct case.",
                expected=0,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    unit="X",
                    unit_case_sensitive=False,
                ),
                input=["0X"],
            ),
            FlagTestData(
                test="Parse 2 kilo-bytes.",
                expected=2000,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=["2kb"],
            ),
            FlagTestData(
                test="Parse 2 kibi-bytes.",
                expected=2048,
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                ),
                input=["2kib"],
            ),
            FlagTestData(
                test="Parse list of bytes.",
                expected=[max(1, f) * 1000**f for f in range(10)],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                ),
                input=[
                    "1b",
                    "1kb",
                    "2mb",
                    "3gb",
                    "4tb",
                    "5pb",
                    "6eb",
                    "7zb",
                    "8yb",
                    "9xb",
                ],
            ),
            FlagTestData(
                test="Parse list of bytes (caps).",
                expected=[max(1, f) * 1000**f for f in range(10)],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                    unit_case_sensitive=True,
                    suffix_case_sensitive=True,
                ),
                input=[
                    "1B",
                    "1KB",
                    "2MB",
                    "3GB",
                    "4TB",
                    "5PB",
                    "6EB",
                    "7ZB",
                    "8YB",
                    "9XB",
                ],
            ),
            FlagTestData(
                test="Parse list of i-bytes.",
                expected=[max(1, f) * 1024**f for f in range(10)],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                ),
                input=[
                    "1b",
                    "1kib",
                    "2mib",
                    "3gib",
                    "4tib",
                    "5pib",
                    "6eib",
                    "7zib",
                    "8yib",
                    "9xib",
                ],
            ),
            FlagTestData(
                test="Parse list of bytes (caps).",
                expected=[max(1, f) * 1024**f for f in range(10)],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                    unit_case_sensitive=True,
                    suffix_case_sensitive=True,
                ),
                input=[
                    "1B",
                    "1KiB",
                    "2MiB",
                    "3GiB",
                    "4TiB",
                    "5PiB",
                    "6EiB",
                    "7ZiB",
                    "8YiB",
                    "9XiB",
                ],
            ),
            FlagTestData(
                test="Parse fraction and space.",
                expected=[0, 1234, 1325606222],
                action=ActionArgs(
                    action=mbo.app.flags.ActionByteSize,
                    nargs="+",
                    unit_case_sensitive=True,
                    suffix_case_sensitive=True,
                ),
                input=["0.7 B", "1.2345 KB", "1.234567 GiB"],
            ),
        ]
    )
    def test_ActionByteSize(self, test: FlagTestData):
        self.FlagTest(test)


if __name__ == "__main__":
    unittest.main()
