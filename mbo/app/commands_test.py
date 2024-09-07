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

"""Tests for commands.py."""

import argparse
import io
import sys
import unittest
from contextlib import redirect_stdout

from parameterized import parameterized

from mbo.app.commands import Command, Print, SnakeCase


class HelloDear(Command):
    """Hello Dear test command."""

    def __init__(self, parser: argparse.ArgumentParser):
        super(HelloDear, self).__init__(parser=parser)
        parser.add_argument("name", nargs="?")

    def Main(self):
        print(
            f"Hello, dear{' ' if self.args.name else ''}{self.args.name}.", flush=True
        )


class Test(unittest.TestCase):
    """Tests for the Command framework."""

    @parameterized.expand(
        [
            ("", ""),
            ("-", ""),
            ("---", ""),
            ("Ab", "ab"),
            ("aB", "a_b"),
            ("AB", "ab"),
            ("ABC", "abc"),
            ("AbC", "ab_c"),
            ("ABcD", "abc_d"),
            ("aBCD", "a_bcd"),
            ("aBCdE", "a_bcd_e"),
            ("aB.CD", "a_b._cd"),
            ("aB-CD", "a_b_cd"),
            ("FooBar", "foo_bar"),
            ("Foo_Bar", "foo_bar"),
            ("Foo__Bar", "foo_bar"),
            ("Foo___Bar", "foo_bar"),
            ("_", "_"),
            ("_FooBar_", "_foo_bar_"),
        ]
    )
    def test_snake_case(self, text: str, expected):
        self.assertEqual(expected, SnakeCase(text))

    @parameterized.expand(
        [
            ([], "Hello, dearNone.\n"),
            ([""], "Hello, dear.\n"),
            (["me"], "Hello, dear me.\n"),
        ]
    )
    def test_hello_dear(self, argv: list[str], expected: str):
        self.assertIn("hello_dear", Command._commands)
        capture = io.StringIO()
        with redirect_stdout(capture):
            Command.Run(["program", "hello_dear"] + argv)
            self.assertEqual(expected, capture.getvalue())


if __name__ == "__main__":
    unittest.main()
