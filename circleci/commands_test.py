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

import unittest

from circleci.commands import SnakeCase


class Test(unittest.TestCase):
    def test_snake_case(self):
        self.assertEqual(SnakeCase(""), "")
        self.assertEqual(SnakeCase("-"), "")
        self.assertEqual(SnakeCase("---"), "")
        self.assertEqual(SnakeCase("Ab"), "ab")
        self.assertEqual(SnakeCase("aB"), "a_b")
        self.assertEqual(SnakeCase("AB"), "ab")
        self.assertEqual(SnakeCase("ABC"), "abc")
        self.assertEqual(SnakeCase("AbC"), "ab_c")
        self.assertEqual(SnakeCase("ABcD"), "abc_d")
        self.assertEqual(SnakeCase("aBCD"), "a_bcd")
        self.assertEqual(SnakeCase("aBCdE"), "a_bcd_e")
        self.assertEqual(SnakeCase("aB.CD"), "a_b._cd")
        self.assertEqual(SnakeCase("aB-CD"), "a_b_cd")
        self.assertEqual(SnakeCase("FooBar"), "foo_bar")
        self.assertEqual(SnakeCase("Foo_Bar"), "foo_bar")
        self.assertEqual(SnakeCase("Foo__Bar"), "foo_bar")
        self.assertEqual(SnakeCase("Foo___Bar"), "foo_bar")
        self.assertEqual(SnakeCase("_"), "_")
        self.assertEqual(SnakeCase("_FooBar_"), "_foo_bar_")


if __name__ == "__main__":
    unittest.main()
