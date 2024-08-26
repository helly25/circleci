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
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import call, patch

from parameterized import parameterized

from circleci.circleci_api_v2 import CircleCiApiV2


class CircleCiApiV2Test(unittest.TestCase):
    """Tests for the CircleCI API V2 client."""

    def test_RequestBranche(self):
        response = '{"org_id": "hex-id", "branches": ["b1", "b2", "b2"]}'
        with patch.object(
            CircleCiApiV2, "_GetRequest", return_value=response
        ) as mock_method:
            circleci = CircleCiApiV2(
                circleci_server="__test__",
                circleci_token="TOKEN",
                project_slug="my_project",
            )
            data = circleci.RequestBranches(workflow="my_work")
            self.assertEqual(data, ["b1", "b2", "b2"])
            mock_method.assert_called_once_with(
                url="__test__/api/v2/insights/my_project/branches?workflow-name=my_work",
                headers={"Circle-Token": "TOKEN"},
            )

    @parameterized.expand(
        [
            (
                [
                    {
                        "all-branches": "True",
                        "reporting-window": "last-90-days",
                    }
                ],
                [
                    """
                {"next_page_token": "", "items": [
                    {"name": "w1", "project_id": "p1"},
                    {"name": "w2", "project_id": "p2"},
                    {"name": "w3", "project_id": "p3"}
                ]}
                """
                ],
                ["w1", "w2", "w3"],
            ),
            (
                [
                    {
                        "all-branches": "True",
                        "reporting-window": "last-90-days",
                    },
                    {
                        "all-branches": "True",
                        "reporting-window": "last-90-days",
                        "page-token": "123",
                    },
                ],
                [
                    """
                {"next_page_token": "123", "items": [
                    {"name": "w1", "project_id": "p1"},
                    {"name": "w2", "project_id": "p2"},
                    {"name": "w3", "project_id": "p3"}
                ]}
                """,
                    """
                {"next_page_token": "", "items": [
                    {"name": "w4", "project_id": "p1"},
                    {"name": "w5", "project_id": "p2"},
                    {"name": "w6", "project_id": "p3"}
                ]}
                """,
                ],
                ["w1", "w2", "w3", "w4", "w5", "w6"],
            ),
        ]
    )
    def test_RequestWorkflows(
        self, call_params: list[dict[str, str]], responses: list[str], result: list[str]
    ):
        with patch.object(
            CircleCiApiV2, "_GetRequest", side_effect=responses
        ) as mock_method:
            circleci = CircleCiApiV2(
                circleci_server="__test__",
                circleci_token="TOKEN",
                project_slug="my_project",
            )
            data = circleci.RequestWorkflows()
            self.assertEqual(data, result)
            expected_calls = [
                call.do_work(
                    url="__test__/api/v2/insights/my_project/workflows?"
                    + "&".join(f"{k}={v}" for k, v in params.items()),
                    headers={"Circle-Token": "TOKEN"},
                )
                for params in call_params
            ]
            mock_method.assert_has_calls(expected_calls)


if __name__ == "__main__":
    unittest.main()
