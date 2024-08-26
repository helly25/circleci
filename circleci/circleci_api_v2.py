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

"""A simple CircleCI V2 API client."""

import http.client
import json
from datetime import datetime
from typing import Any


class CircleCiApiV2:
    """Implementation of a simple CircleCI API V2 client.

    See https://circleci.com/docs/api/v2/index.html
    """

    def __init__(self, circleci_server: str, circleci_token: str, project_slug: str):
        self.circleci_server = circleci_server.rstrip(".")
        self.circleci_token = circleci_token
        self.project_slug = project_slug
        if self.circleci_server != "__test__":
            self.conn = http.client.HTTPSConnection("circleci.com")

    def _GetRequest(self, url: str, headers: dict[str, str] = {}) -> str:
        self.conn.request("GET", url, headers=headers)
        return self.conn.getresponse().read().decode("utf-8")

    def _Request(self, api: str, params: dict[str, str] = {}) -> Any:
        headers = {
            "Circle-Token": self.circleci_token,  # authorization
        }
        parms = "&".join([k + "=" + v for k, v in params.items()])
        url = f"{self.circleci_server}/{api}?{parms}"
        data: str = self._GetRequest(url=url, headers=headers)
        return json.loads(data)

    def RequestBranches(self, workflow: str) -> list[str]:
        """Returns a list of branches for the given `workflow`."""
        data = self._Request(
            api=f"api/v2/insights/{self.project_slug}/branches",
            params={"workflow-name": workflow},
        )
        return data["branches"]

    def RequestWorkflows(self) -> list[str]:
        """Returns a list of workflows."""
        workflows: set[str] = set()
        requests = 0
        params: dict[str, str] = {
            "all-branches": "True",
            "reporting-window": "last-90-days",
        }
        projects: set[str] = set()
        while 1:
            requests += 1
            data: Any = self._Request(
                api=f"api/v2/insights/{self.project_slug}/workflows", params=params
            )
            items: list[dict[str, str]] = data["items"]
            for item in items:
                workflows.add(item["name"])
                projects.add(item["project_id"])
            next_page_token: str = data.get("next_page_token", "")
            if not next_page_token:
                break
            params["page-token"] = next_page_token
        return sorted(workflows)

    def RequestWorkflowRuns(
        self, workflow: str, params: dict[str, str]
    ) -> list[dict[str, str]]:
        """Returns a list run data for `workflow` adhering to `params`."""
        items = []
        requests = 0
        while 1:
            requests += 1
            data = self._Request(
                api=f"api/v2/insights/{self.project_slug}/workflows/{workflow}",
                params=params,
            )
            next_items = data.get("items")
            if next_items:
                items.extend(next_items)
            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break
            params["page-token"] = next_page_token
        return items

    def RequestWorkflowDetails(self, workflow: str) -> dict[str, str]:
        """Returns deaults for the given `workflow`."""
        return self._Request(api=f"api/v2/workflow/{workflow}")

    def ParseTime(self, dt: str) -> datetime:
        if dt.endswith("Z") and dt[len(dt) - 2] in "0123456789":
            dt = dt[:-1] + "UTC"
        return datetime.strptime(dt, r"%Y-%m-%dT%H:%M:%S.%f%Z")
