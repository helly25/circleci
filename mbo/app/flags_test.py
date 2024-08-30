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
from datetime import datetime
from enum import Enum
from typing import Any

from freezegun import freeze_time
from parameterized import param, parameterized

import mbo.app.flags

_NOW = "2024-08-28T14:15:16.123Z"


def ActionArgs(name: str = "--flag", **kwargs) -> dict[str, Any]:
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
    class ParseDateTimeOrDeltaTest:
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
            ParseDateTimeOrDeltaTest(
                expected="2024-04-02T14:00:00Z",
                input="2024-04-02T14",
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-04-02T01:02:03.004Z",
                input="2024-04-02T01:02:03.004Z",
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-04-02T00:00:00Z",
                input="2024-04-02T13:14:15.123Z",
                midnight=True,
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-21T14:15:16.123Z",
                input="-1w",
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-29T14:15:16.123Z",
                input="+1d",
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-29T00:00:00Z",
                input="+1d",
                midnight=True,
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-14 01:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=False,
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-14 00:00:00Z",
                input="+8h",
                reference="2024-08-13 17",
                midnight=True,
            ),
            ParseDateTimeOrDeltaTest(
                expected="2024-08-14 00:00:00Z",
                input="+0s",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrDeltaTest(
                expected="Bad timedelta value '+0 NOPE'.",
                expected_error=ValueError,
                input="+0 NOPE",
                reference="2024-08-14 17",
                midnight=True,
            ),
            ParseDateTimeOrDeltaTest(
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
    def test_ParseDateTimeOrDelta(self, test: ParseDateTimeOrDeltaTest):
        with freeze_time(datetime.fromisoformat(test.now)):
            try:
                self.assertEqual(
                    (
                        datetime.fromisoformat(test.expected)
                        if not test.expected_error
                        else None
                    ),
                    mbo.app.flags.ParseDateTimeOrDelta(
                        arg=test.input,
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
    class EnumListActionTest:
        test: str
        expected: Any
        expected_error: type | None = None
        action: dict[str, Any]
        input: list[str]

    @parameterized.expand(
        [
            EnumListActionTest(
                test="Set a single value to a list.",
                expected=[TestEnum.ONE],
                action=ActionArgs(
                    type=TestEnum,
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["--flag=one"],
            ),
            EnumListActionTest(
                test="Setting an empty vlaue requires `allow_empty=True`.",
                expected="argument --flag: Empty value is not allowed, chose at least one of [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["--flag="],
            ),
            EnumListActionTest(
                test="Setting an empty vlaue requires `allow_empty=True` (not False).",
                expected="argument --flag: Empty value is not allowed, chose at least one of [FOR, ONE, TRE, TWO].",
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.EnumListAction,
                    allow_empty=False,
                ),
                input=["--flag="],
            ),
            EnumListActionTest(
                test="Setting an empty vlaue requires with `allow_empty=True` works.",
                expected=[],
                expected_error=argparse.ArgumentError,
                action=ActionArgs(
                    type=TestEnum,
                    default=[],
                    action=mbo.app.flags.EnumListAction,
                    allow_empty=True,
                ),
                input=["--flag="],
            ),
            EnumListActionTest(
                test="Default values work.",
                expected=[TestEnum.TWO],
                action=ActionArgs(
                    type=TestEnum,
                    default=[TestEnum.TWO],
                    action=mbo.app.flags.EnumListAction,
                ),
                input=[],
            ),
            EnumListActionTest(
                test="Default values work: They can even bypass the type.",
                expected="Something else",
                action=ActionArgs(
                    type=TestEnum,
                    default="Something else",
                    action=mbo.app.flags.EnumListAction,
                ),
                input=[],
            ),
            EnumListActionTest(
                test="Multile, possible repeated values and mixed case.",
                expected=[TestEnum.TWO, TestEnum.ONE, TestEnum.TWO],
                action=ActionArgs(
                    type=TestEnum,
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["--flag=two,oNe,TWO"],
            ),
            EnumListActionTest(
                test="Multile values in a set.",
                expected=set([TestEnum.ONE, TestEnum.TWO]),
                action=ActionArgs(
                    type=TestEnum,
                    container_type=set,
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["--flag=two,oNe,TWO"],
            ),
            EnumListActionTest(
                test="Repeated flag for list.",
                expected=[
                    TestEnum.TWO,
                    TestEnum.FOR,
                    TestEnum.ONE,
                    TestEnum.TRE,
                    TestEnum.TWO,
                ],
                action=ActionArgs(
                    "flag",
                    nargs="+",
                    type=TestEnum,
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["two,for", "one,tre", "TWO"],
            ),
            EnumListActionTest(
                test="Repeated flag for list.",
                expected={TestEnum.TWO, TestEnum.FOR, TestEnum.ONE, TestEnum.TRE},
                action=ActionArgs(
                    "flag",
                    nargs="+",
                    type=TestEnum,
                    container_type=set,
                    action=mbo.app.flags.EnumListAction,
                ),
                input=["two,for", "one,tre", "TWO"],
            ),
        ]
    )
    def test_EnumListAction(self, test: EnumListActionTest):
        try:
            parser = argparse.ArgumentParser(exit_on_error=False)
            name = test.action.pop("name", "--flag")
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


if __name__ == "__main__":
    unittest.main()
