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

import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from parameterized import parameterized

import circleci.workflows_lib
from circleci.circleci_api_v2 import CircleCiApiV2
from mbo.app.commands import Command, Print, SnakeCase


class WorkflowsTest(unittest.TestCase):
    """Tests for the workflows sub commands."""

    def test_CommandList(self):
        self.assertTrue(
            set(Command._commands.keys()).issuperset(
                {
                    "combine",
                    "fetch_details",
                    "fetch",
                    "filter",
                    "request_branches",
                    "request_workflow",
                    "request_workflows",
                }
            )
        )

    def test_Workflows(self):
        """Lower level mocking to prove the pieces work together.

        Here we bypass the CircleCiApiV2 almost completey as we mock the highest level function we
        call there. That function `RequestBranches` will be mocked, by injection, through mocking
        the `CircleCiCommand._InitCircleCiClient`.

        Now we can call the `branches` sub-command normally by providing an appropriate argv to
        `Command.Run`. The mocked return_value for the `RequestBranches` will be our result.
        """
        with open(os.devnull, "w") as err:
            with redirect_stderr(err):
                with redirect_stdout(io.StringIO()) as capture:
                    with patch.object(
                        CircleCiApiV2, "RequestBranches", return_value=["b1", "b2"]
                    ) as mock_request_branches:
                        mock_client = CircleCiApiV2(
                            circleci_server="__test__",
                            circleci_token="TOKEN",
                            project_slug="project",
                        )
                        with patch(
                            "circleci.workflows_lib.CircleCiCommand._InitCircleCiClient",
                            return_value=mock_client,
                        ) as mock_init:
                            Command.Run(["program", "request_branches"])
        self.assertEqual("b1\nb2\n", capture.getvalue())


if __name__ == "__main__":
    unittest.main()
