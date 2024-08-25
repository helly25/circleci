#!/usr/bin/env python3

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

"""A simple CircleCI client that fetches workflow stats from the CircleCI API
server and writes them as a CSV file.
"""

import argparse
import csv
import http.client
import inspect
import json
import os
import re
import sys
import time
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from circleci.commands import Command
from circleci.commands import Die
from circleci.commands import Log
from circleci.commands import Print

FETCH_WORKFLOW_KEYS = [
    "branch",
    "created_unix",
    "created",
    "credits_used",
    "duration",
    "id",
    "is_approval",
    "status",
    "stopped_unix",
    "stopped",
    "workflow",
]

FETCH_WORKFLOW_DETAIL_EXTRAS = [
    "canceled_by",
    "pipeline_id",
    "pipeline_number",
    "project_slug",
    "started_by",
    "tag",
]

FETCH_WORKFLOW_DETAIL_KEYS = FETCH_WORKFLOW_KEYS + FETCH_WORKFLOW_DETAIL_EXTRAS


class CircleCi:
    """Implementation of a simple CircleCI API client.

    See https://circleci.com/docs/api/v2/index.html
    """

    def __init__(self, circleci_token: str, project_slug: str):
        self.circleci_token = circleci_token
        self.project_slug = project_slug

    def _Request(self, api: str, params: dict[str, str] = {}) -> Any:
        headers = {
            # 'authorization': self.circleci_token,
            "Circle-Token": self.circleci_token,
        }
        conn = http.client.HTTPSConnection("circleci.com")
        parms = "&".join([k + "=" + v for k, v in params.items()])
        url = f"http://circleci.com/{api}?{parms}"
        conn.request("GET", url, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        return json.loads(data)

    def RequestBranches(self, workflow: str) -> list[str]:
        """Returns a list of branches for the given `workflow`."""
        data = self._Request(
            api=f"api/v2/insights/{self.project_slug}/branches",
            params={"workflow-name": workflow},
        )
        branches = data["branches"]
        Log(f"Read {len(branches)} branches.")
        return branches

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
                api=f"/api/v2/insights/{self.project_slug}/workflows", params=params
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
                api=f"/api/v2/insights/{self.project_slug}/workflows/{workflow}",
                params=params,
            )
            next_items = data.get("items")
            if next_items:
                items.extend(next_items)
            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break
            params["page-token"] = next_page_token
        Log(f"Read {len(items)} items from '{workflow}' in {requests} requests.")
        return items
    
    def RequestWorkflowDetails(self, workflow: str) -> dict[str, str]:
        """Returns deaults for the given `workflow`."""
        return self._Request(api=f"api/v2/workflow/{workflow}")


    def ParseTime(self, dt: str) -> datetime:
        if dt.endswith("Z") and dt[len(dt) - 2] in "0123456789":
            dt = dt[:-1] + "UTC"
        return datetime.strptime(dt, r"%Y-%m-%dT%H:%M:%S.%f%Z")


class CircleCiCommand(Command):
    """Abstract base class for commands that use the CircleCI API."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self):
        super(CircleCiCommand, self).__init__()
        self.parser.add_argument(
            "--circleci_token",
            default="",
            type=str,
            help="CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')",
        )
        self.parser.add_argument(
            "--project_slug",
            default="",
            type=str,
            help="CircleCI project-slug (defaults to environment variable 'CIRCLECI_PROJECT_SLUG').",
        )

    def Prepare(self) -> None:
        super(CircleCiCommand, self).Prepare()
        circleci_token = str(self.args.circleci_token or os.getenv("CIRCLECI_TOKEN"))
        if not circleci_token:
            Die("Must provide `--circleci_token` flag or environment variable 'CIRCLECI_TOKEN'.")
        project_slug = str(self.args.project_slug or os.getenv("CIRCLECI_PROJECT_SLUG"))
        if not project_slug:
            Die("Must provide `--project_slug` flag or environment variable 'CIRCLECI_PROJECT_SLUG'.")
        self.circleci = CircleCi(circleci_token, project_slug=project_slug)


class Branches(CircleCiCommand):
    """Read and display the list of branches for `workflow` from CircleCI API."""

    def __init__(self):
        super(Branches, self).__init__()
        self.parser.add_argument(
            "--workflow",
            default="default_workflow",
            type=str,
            help="The name of the workflow to read. Multiple workflows can be read by separating with comma.",
        )

    def Main(self):
        branches = self.circleci.RequestBranches(workflow=self.args.workflow)
        for branch in branches:
            Print(branch)


class Workflows(CircleCiCommand):
    """Read and display the list of workflows from CircleCI API."""

    def __init__(self):
        super(Workflows, self).__init__()

    def Main(self):
        for workflow in self.circleci.RequestWorkflows():
            Print(workflow)


class Fetch(CircleCiCommand):
    """Fetche workflow stats from the CircleCI API server and writes them as a CSV file."""

    def __init__(self):
        super(Fetch, self).__init__()
        self.parser.add_argument(
            "--workflow",
            default=None,
            type=str,
            help="The name of the workflow(s) to read. Multiple workflows can be read by "
            "separating with comma. If no workflow is set, then fetch all workflows.",
        )
        self.parser.add_argument(
            "--output",
            default="/tmp/circleci.csv",
            type=Path,
            help="Name of the output file.",
        )
        self.parser.add_argument(
            "--end",
            default="",
            type=str,
            help=r"Start Date/time in format `%Y%m%d`, defaults to `now`.",
        )
        self.parser.add_argument(
            "--start",
            default="",
            type=str,
            help=r"Start Date/time in format `%Y%m%d`, defaults to `--end` minus 90 days.",
        )

    def Main(self) -> None:
        if self.args.end:
            end = datetime.strptime(self.args.end, r"%Y%m%d")
        else:
            end = datetime.now()
        if self.args.start:
            start = datetime.strptime(self.args.start, r"%Y%m%d")
        else:
            start = end - timedelta(days=90)
        run_count = 0
        if self.args.workflow:
            workflows = self.args.workflow.split(",")
        else:
            workflows = self.circleci.RequestWorkflows()
        max_created: datetime | None = None
        min_created: datetime | None = None
        with self.Open(filename=self.args.output, mode="w") as csv_file:
            keys = FETCH_WORKFLOW_KEYS
            print(f"{','.join(keys)}", file=csv_file)
            for workflow in workflows:
                runs = self.circleci.RequestWorkflowRuns(
                    workflow=workflow,
                    params={
                        "all-branches": "True",
                        "start-date": start.strftime(r"%Y-%m-%dT%H:%M:%S%Z"),
                        "end-date": end.strftime(r"%Y-%m-%dT%H:%M:%S%Z"),
                    },
                )
                run_count += len(runs)
                for run in runs:
                    run["workflow"] = workflow
                    created: datetime = self.circleci.ParseTime(run["created_at"])
                    stopped: datetime = self.circleci.ParseTime(run["stopped_at"])
                    if not max_created or created > max_created:
                        max_created = created
                    if not min_created or created < min_created:
                        min_created = created
                    # Write spreadsheet compatible format.
                    run["created"] = created.strftime(r"%m/%d/%Y %H:%M:%S")
                    run["stopped"] = stopped.strftime(r"%m/%d/%Y %H:%M:%S")
                    # Write unix timestamps for sorting etc.
                    run["created_unix"] = str(created.timestamp())
                    run["stopped_unix"] = str(stopped.timestamp())
                    data = ",".join([str(run[k]) for k in keys])
                    print(data, file=csv_file)
        Log(f"Read {run_count} items.")
        if max_created:
            Log(f"Max Date: {max_created.strftime(r'%Y.%m.%d')}.")
        if min_created:
            Log(f"Min Date: {min_created.strftime(r'%Y.%m.%d')}.")


class FetchDetails(CircleCiCommand):
    """Given a workflow CSV file, fetch details for each workflow (slow)."""

    def __init__(self):
        super(FetchDetails, self).__init__()
        self.parser.add_argument(
            "--input",
            type=Path,
            help="A CSV file generated from `workflow.py fetch`.",
        )
        self.parser.add_argument(
            "--output",
            default="/tmp/circleci_details.csv.bz2",
            type=Path,
            help="Name of the output file.",
        )
        self.parser.add_argument(
            "--progress",
            type=bool,
            default=True,
            help="Whether to indicate progress."
        )

    def Main(self) -> None:
        Log(f"Read file {self.args.input}...")
        data: dict[str, dict[str, str]] = {}
        if self.args.progress:
            Log("Fetching workflow details:", end="")
        with self.Open(filename=self.args.input, mode="r") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=",", fieldnames=FETCH_WORKFLOW_KEYS)
            headers = next(reader, None)
            for index, row in enumerate(reader, 1):
                if self.args.progress:
                    if not index % 1000:
                        Log(f"{index}")
                        Log("Fetching workflow details:", end="")
                    elif not index % 20:
                        Log(".", end="")
                details = self.circleci.RequestWorkflowDetails(workflow=row["id"])
                d = row
                for k in FETCH_WORKFLOW_DETAIL_EXTRAS:
                    d[k] = details.get(k, "")
                data[row["id"]] = d
        if self.args.progress:
            Log()
        Log(f"Read {len(data)} details.")
        with self.Open(filename=self.args.output, mode="w") as csv_file:
            writer = csv.DictWriter(csv_file, delimiter=",", fieldnames=FETCH_WORKFLOW_DETAIL_KEYS)
            writer.writeheader()
            writer.writerows(sorted(data.values(), key=lambda d: d["created_unix"]))
        Log(f"Wrote {self.args.output}")


class Combine(Command):
    """Read multiple files generated by `workflow.py fetch` and combine them."""

    def __init__(self):
        super(Combine, self).__init__()
        self.parser.add_argument(
            "input",
            type=Path,
            nargs="+",
            help="List of CSV files generated from `workflow.py fetch`.",
        )
        self.parser.add_argument(
            "--output",
            default="/tmp/circleci.csv",
            type=Path,
            help="Name of the output file.",
        )

    def Main(self) -> None:
        if len(self.args.input) < 2:
            Die("Must have at least 2 input files.")
        keys = FETCH_WORKFLOW_KEYS
        data: dict[str, dict[str, str]] = {}
        for filename in self.args.input:
            Log(f"Read file {filename}...")
            with self.Open(filename=filename, mode="r") as csv_file:
                reader = csv.DictReader(csv_file, delimiter=",", fieldnames=keys)
                headers = next(reader, None)
                rows = 0
                for row in reader:
                    rows += 1
                    data[row["id"]] = row
                Log(f"Read file {filename} with {rows} rows.")
        with self.Open(filename=self.args.output, mode="w") as csv_file:
            writer = csv.DictWriter(csv_file, delimiter=",", fieldnames=keys)
            writer.writeheader()
            writer.writerows(sorted(data.values(), key=lambda d: d["created_unix"]))
        Log(f"Wrote file {self.args.output} with {len(data)} rows.")


class Filter(Command):
    """Read CSV files generated from `workflow.py fetch` and filters them."""

    def __init__(self):
        super(Filter, self).__init__()
        self.parser.add_argument(
            "--workflow",
            default=None,
            type=str,
            help="The name of the workflow(s) to accept. Multiple workflows can be userd by "
            "separating with comma. If no workflow is set, then accept all workflows.",
        )
        self.parser.add_argument(
            "--input",
            type=Path,
            help="CSV file generated from `workflow.py fetch`.",
        )
        self.parser.add_argument(
            "--output",
            default="/tmp/circleci.csv",
            type=Path,
            help="Name of the output file.",
        )
        self.parser.add_argument(
            "--min_duration_sec",
            type=int,
            default=600,
            help="Mininum duration to accept row in [sec].",
        )
        self.parser.add_argument(
            "--exclude_branches",
            type=str,
            default="main|master|develop|develop-freeze.*",
            help="Exclude brnaches by full regular expression match.",
        )
        self.parser.add_argument(
            "--exclude_incomplete_reruns",
            type=bool,
            default=True,
            help="If workflow details are available, reject inomplete reruns "
                 "(e.g.: rerun-single-job, rerun-workflow-from-failed)."
        )
        self.parser.add_argument(
            "--only_branches",
            type=str,
            default="",
            help="Accept branches by full regular expression match."
        )
        self.parser.add_argument(
            "--only_status",
            type=str,
            default="success",
            help="Accept only listed status values (multiple separated by comma)."
        )
        self.parser.add_argument(
            "--only_weekdays",
            type=str,
            default="12345",
            help="Accept only the listed days of the week as indexed 1=Monday through 7=Sunday (ISO notation)."
        )

    def ParseTime(self, dt: str) -> datetime:
        return datetime.strptime(dt, r"%m/%d/%Y %H:%M:%S")

    def MaxWithoutOutlier(self, data: list[float]) -> float:
        """Remove up to 10% of data by detecting high outliers."""
        if len(data) < 10:
            return max(data)
        data = sorted(data)
        for x in range(int(len(data) / 10)):
            if (data[-1] / 1.2) > max(data[:-1]):
                data = data[:-1]
            else:
                break
        return max(data)

    def MinWithoutOutlier(self, data: list[float]) -> float:
        """Remove up to 10% of data by detecting low outliers."""
        if len(data) < 10:
            return min(data)
        data = sorted(data)
        for x in range(int(len(data) / 10)):
            if (data[0] * 1.1) < min(data[1:]):
                data = data[1:]
            else:
                break
        return min(data)

    def Main(self) -> None:
        data: dict[str, list[dict[str, str]]] = {}
        has_details = False
        count_rows = 0
        count_pass = 0
        workflows: set[str] = set()
        exclude_branches = re.compile(self.args.exclude_branches) if self.args.exclude_branches else None
        only_branches = re.compile(self.args.only_branches) if self.args.only_branches else None
        only_status = set(self.args.only_status.split(","))
        if [c for c in self.args.only_weekdays if c not in "1234567"]:
            Die("Flag '--only_weekdays' must only contain weekday indices 1=Monday through 7=Sunday (ISO notation).")
        with self.Open(filename=self.args.input, mode="r") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=",")
            if set(reader.fieldnames or []) == set(FETCH_WORKFLOW_KEYS):
                Log("Loading workflow CSV file without workflow details (see command fetch_details).")
            elif set(reader.fieldnames or []) == set(FETCH_WORKFLOW_DETAIL_KEYS):
                Log("Loading workflow-detail CSV file.")
                has_details = True
            else:
                Die("File fieldnames '{reader.fieldnames}' do not match '{keys}'.")
            for row in reader:
                count_rows += 1
                if exclude_branches and exclude_branches.fullmatch(row["branch"]):
                    continue
                if only_branches and not only_branches.fullmatch(row["branch"]):
                    continue
                if only_status and row["status"] not in only_status:
                    continue
                if has_details and self.args.exclude_incomplete_reruns and row["tag"] not in ["", "rerun-workflow-from-beginning"]:
                    continue
                duration = int(row["duration"]) / 60
                if duration * 60 < self.args.min_duration_sec:
                    continue
                workflow = row["workflow"]
                workflows.add(workflow)
                if self.args.workflow and workflow not in self.args.workflow.split(","):
                    continue
                row["duration"] = str(duration)
                row[f"duration.{workflow}"] = str(duration)
                created = self.ParseTime(row["created"])
                if created.strftime("%u") not in self.args.only_weekdays:
                    continue
                date = created.strftime(r"%Y.%m.%d")
                row["date"] = date
                if not date in data:
                    data[date] = [row]
                else:
                    data[date].append(row)
                count_pass += 1
        sorted_data = [data[k] for k in sorted(data)]
        Log(f"Read {count_rows} rows.")
        Log(f"Aggregated {count_pass} rows.")
        Log(f"Workflows: {workflows}.")
        keys = ["date", "avg", "max", "min", "runs"]
        with self.Open(filename=self.args.output, mode="w") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for rows in sorted_data:
                durations = [float(row["duration"]) for row in rows]
                r_cnt = len(durations)
                r_max = self.MaxWithoutOutlier(durations)
                r_min = self.MinWithoutOutlier(durations)
                r_sum = sum(durations)
                writer.writerow(
                    {
                        "date": rows[0]["date"],
                        "avg": str(round(r_sum / r_cnt, 1)),
                        "max": str(round(r_max, 1)),
                        "min": str(round(r_min, 1)),
                        "runs": str(r_cnt),
                    }
                )
        Log(f"First {sorted_data[0][0]['date']}")
        Log(f"Last  {sorted_data[-1][0]['date']}")
        Log(f"Wrote {len(sorted_data)} rows to '{self.args.output}'.")


if __name__ == "__main__":
    Command.Run()
