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

import requests
import responses
from parameterized import parameterized

from circleci.circleci_api_v2 import (
    CircleCiApiError,
    CircleCiApiV2,
    CircleCiRequestError,
)


class CircleCiApiV2Test(unittest.TestCase):
    """Tests for the CircleCI API V2 client."""

    def setUp(self):
        self.circleci = CircleCiApiV2(
            circleci_server="__test__",
            circleci_token="TOKEN",
            project_slug="my_project",
        )

    @responses.activate
    def test_CircleCiApiError_RequestWorkflowDetails(self):
        responses.get(
            url="https://__test__/api/v2/workflow/123",
            headers={"Circle-Token": "TOKEN"},
            status=200,
            body='{:message "The Error"}',
        )
        with self.assertRaises(Exception) as context:
            data = self.circleci.RequestWorkflowDetails(workflow_id="123")
        self.assertEqual("CircleCI API Error: 'The Error'", str(context.exception))
        self.assertEqual(CircleCiApiError, type(context.exception))

    @responses.activate
    def test_RequestError_RequestWorkflowDetails(self):
        """Test an error from a bad request (simulated by an injected timeout)."""
        responses.get(
            url="https://__test__/api/v2/workflow/123",
            headers={"Circle-Token": "TOKEN"},
            body=requests.exceptions.Timeout("timeout"),
        )
        with self.assertRaises(Exception) as context:
            data = self.circleci.RequestWorkflowDetails(workflow_id="123")
        self.assertEqual("CircleCI Request Error: 'timeout'", str(context.exception))
        self.assertEqual(CircleCiRequestError, type(context.exception))

    @responses.activate
    def test_RequestBranches(self):
        responses.get(
            url="https://__test__/api/v2/insights/my_project/branches?workflow-name=my_work",
            headers={"Circle-Token": "TOKEN"},
            status=200,
            body='{"org_id": "hex-id", "branches": ["b1", "b2", "b2"]}',
        )
        self.assertEqual(
            self.circleci.RequestBranches(workflow="my_work"), ["b1", "b2", "b2"]
        )

    @parameterized.expand(
        [
            (
                [
                    (
                        {
                            "all-branches": "True",
                            "reporting-window": "last-90-days",
                        },
                        """{"next_page_token": "", "items": [
                            {"name": "w1"},
                            {"name": "w2"},
                            {"name": "w3"}
                        ]}
                        """,
                    )
                ],
                ["w1", "w2", "w3"],
            ),
            (
                [
                    (
                        {
                            "all-branches": "True",
                            "reporting-window": "last-90-days",
                        },
                        """{"next_page_token": "123", "items": [
                            {"name": "w1"},
                            {"name": "w2"},
                            {"name": "w3"}
                        ]}
                        """,
                    ),
                    (
                        {
                            "all-branches": "True",
                            "reporting-window": "last-90-days",
                            "page-token": "123",
                        },
                        """{"next_page_token": "", "items": [
                            {"name": "w4"},
                            {"name": "w5"},
                            {"name": "w6"}
                        ]}
                        """,
                    ),
                ],
                ["w1", "w2", "w3", "w4", "w5", "w6"],
            ),
        ]
    )
    @responses.activate
    def test_RequestWorkflows(
        self, requests: list[tuple[dict[str, str], str]], expected: list[str]
    ):
        # Setup:
        for params, json_response in requests:
            responses.add(
                responses.GET,
                url="https://__test__/api/v2/insights/my_project/workflows?"
                + "&".join(f"{k}={v}" for k, v in params.items()),
                headers={"Circle-Token": "TOKEN"},
                status=200,
                body=json_response,
            )
        # Actual call:
        self.assertEqual(self.circleci.RequestWorkflows(), expected)

    @parameterized.expand(
        [
            (
                # Single request with all fields returned in the response.
                [
                    (
                        {
                            "a": "1",
                            "b": "2",
                        },
                        """{"next_page_token": "", "items": [{
                            "id": "12345",
                            "branch": "main",
                            "duration": "42",
                            "created_at": "2019-08-24T14:15:22Z",
                            "stopped_at": "2019-08-24T14:15:22Z",
                            "credits_used": "0",
                            "status": "success",
                            "is_approval": "False"
                        }]}""",
                    )
                ],
                [
                    {
                        "id": "12345",
                        "branch": "main",
                        "duration": "42",
                        "created_at": "2019-08-24T14:15:22Z",
                        "stopped_at": "2019-08-24T14:15:22Z",
                        "credits_used": "0",
                        "status": "success",
                        "is_approval": "False",
                    },
                ],
            ),
            (
                # Request in 3 pages. Data is mocked, we only care for the id for demonstration purposes.
                [
                    (
                        {
                            "a": "1",
                            "b": "2",
                        },
                        """{"next_page_token": "25", "items": [{"id": "1"}, {"id": "2"}]}""",
                    ),
                    (
                        {
                            "a": "1",
                            "b": "2",
                            "page-token": "25",
                        },
                        """{"next_page_token": "42", "items": [{"id": "3"}, {"id": "4"}]}""",
                    ),
                    (
                        {
                            "a": "1",
                            "b": "2",
                            "page-token": "42",
                        },
                        """{"next_page_token": "", "items": [{"id": "5"}, {"id": "6"}]}""",
                    ),
                ],
                [
                    {"id": "1"},
                    {"id": "2"},
                    {"id": "3"},
                    {"id": "4"},
                    {"id": "5"},
                    {"id": "6"},
                ],
            ),
        ]
    )
    @responses.activate
    def test_RequestWorkflowRuns(
        self, requests: list[tuple[dict[str, str], str]], expected: list[str]
    ):
        # Setup:
        for params, json_response in requests:
            responses.add(
                responses.GET,
                url="https://__test__/api/v2/insights/my_project/workflows/my_workflow?"
                + "&".join(f"{k}={v}" for k, v in params.items()),
                headers={"Circle-Token": "TOKEN"},
                status=200,
                body=json_response,
                content_type="application/json",
            )
        # Actual call:
        self.assertEqual(
            self.circleci.RequestWorkflowRuns(
                workflow="my_workflow", params=requests[0][0]
            ),
            expected,
        )

    @responses.activate
    def test_RequestWorkflowDetails(self):
        expected = {
            "id": "12345",
            "branch": "main",
            "duration": "42",
            "created_at": "2019-08-24T14:15:22Z",
            "stopped_at": "2019-08-24T14:15:22Z",
            "credits_used": "0",
            "status": "success",
            "is_approval": "False",
        }
        response_text = str(expected).replace("'", '"')
        responses.add(
            responses.GET,
            url="https://__test__/api/v2/workflow/123",
            headers={"Circle-Token": "TOKEN"},
            json=expected,
            status=200,
        )
        self.assertEqual(
            self.circleci.RequestWorkflowDetails(workflow_id="123"), expected
        )


if __name__ == "__main__":
    unittest.main()
