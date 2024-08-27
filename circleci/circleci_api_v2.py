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

from datetime import datetime
from typing import Any

import requests


class CircleCiError(Exception):
    """Based exception for all Exceptions raied by the client."""

    pass


class CircleCiRequestError(CircleCiError):
    """Exception raised by client if the request fails."""

    pass


class CircleCiApiError(CircleCiError):
    """Exception raised by the client if the Api reports an error."""

    pass


class CircleCiDataError(CircleCiError):
    """Exception raied by the client if there is a data error (e.g. JSON decoding failed)."""

    pass


class CircleCiApiV2:
    """Implementation of a simple CircleCI API V2 client.

    See https://circleci.com/docs/api/v2/index.html
    """

    def __init__(self, circleci_server: str, circleci_token: str, project_slug: str):
        if not circleci_server.startswith(("https://", "http://")):
            circleci_server = "https://" + circleci_server
        self.circleci_server = circleci_server
        self.circleci_token = circleci_token
        self.project_slug = project_slug

    def _GetRequestJson(self, api: str, params: dict[str, str] = {}) -> Any:
        headers = {
            "Circle-Token": self.circleci_token,  # authorization
        }
        url = f"{self.circleci_server}/{api}"
        if params:
            url += "?" + "&".join([k + "=" + v for k, v in params.items()])
        try:
            response = requests.get(url=url, headers=headers)
        except Exception as err:
            raise CircleCiRequestError(f"CircleCI Request Error: '{err}'")
        if response.status_code != 200:
            raise CircleCiRequestError(
                f"CirecleCI Request Error: Bad reponse {response.status_code}: {response.reason}"
            )
        error_message_prefix = '{:message "'
        if str(response.text).startswith(error_message_prefix):
            error = response.text.lstrip(error_message_prefix).rstrip('"}')
            raise CircleCiApiError(f"CircleCI API Error: '{error}'")
        try:
            return response.json()
        except Exception as err:
            raise CircleCiDataError(
                f"CircleCI Data Error: {err}: data='{response.text}'"
            )

    def RequestBranches(self, workflow: str) -> list[str]:
        """Returns a list of branches for the given `workflow`."""
        data = self._GetRequestJson(
            api=f"api/v2/insights/{self.project_slug}/branches",
            params={"workflow-name": workflow},
        )
        return data["branches"]

    def RequestWorkflows(self) -> list[str]:
        """Returns a list of workflows."""
        # TODO(helly25): Should this do something with `item["project_id"]`?
        workflows: set[str] = set()
        requests = 0
        params: dict[str, str] = {
            "all-branches": "True",
            "reporting-window": "last-90-days",
        }
        while 1:
            requests += 1
            data: Any = self._GetRequestJson(
                api=f"api/v2/insights/{self.project_slug}/workflows", params=params
            )
            items: list[dict[str, Any]] = data["items"]
            for item in items:
                workflows.add(str(item["name"]))
            next_page_token = str(data.get("next_page_token", ""))
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
            data = self._GetRequestJson(
                api=f"api/v2/insights/{self.project_slug}/workflows/{workflow}",
                params=params,
            )
            next_items = data.get("items")
            if next_items:
                for item in next_items:
                    next_item: dict[str, str] = {}
                    for k in item.keys():
                        next_item[k] = str(item[k])
                    items.append(next_item)
            next_page_token = str(data.get("next_page_token", ""))
            if not next_page_token:
                break
            params["page-token"] = next_page_token
        return items

    def RequestWorkflowDetails(self, workflow_id: str) -> dict[str, str]:
        """Returns details for the given `workflow`."""
        data = self._GetRequestJson(api=f"api/v2/workflow/{workflow_id}")
        if not data:
            return {}
        result: dict[str, str] = {}
        for k, v in data.items():
            result[str(k)] = str(v)
        return result

    def ParseTime(self, dt: str) -> datetime:
        if dt.endswith("Z") and dt[len(dt) - 2] in "0123456789":
            dt = dt[:-1] + "UTC"
        return datetime.strptime(dt, r"%Y-%m-%dT%H:%M:%S.%f%Z")
