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

"""A collection of CircleCI API commands."""

import argparse
import csv
import inspect
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from _typeshed import SupportsWrite
else:
    SupportsWrite = IO

import humanize

from circleci.circleci_api_v2 import CircleCiApiV2, CircleCiApiV2Opts, LogRequestDetail
from mbo.app.commands import Command, Die, DocOutdent, Log, OpenTextFile, Print
from mbo.app.flags import (
    ActionDateTimeOrTimeDelta,
    ActionEnumList,
    ParseDateTimeOrTimeDelta,
)

# Keys used by the `fetch` command.
# Instead of `created_at` and `stopped_at` we provide `created`/`created_unix`
# and `stopped`/`stopped_unix` respectively.
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

# Keys used by the `fetch_details` command.
# The `name` field is dropped since it is already available as `workflow`.
# Otherwise the `fetch_details` command provides a superset of fields.
FETCH_WORKFLOW_DETAIL_EXTRAS = [
    "canceled_by",
    "errored_by",
    "pipeline_id",
    "pipeline_number",
    "project_slug",
    "started_by",
    "tag",
]

FETCH_WORKFLOW_DETAIL_KEYS = FETCH_WORKFLOW_KEYS + FETCH_WORKFLOW_DETAIL_EXTRAS


def TimeRangeStr(start: datetime, end: datetime) -> str:
    if (start.tzinfo is None) != (end.tzinfo is None):
        if start.tzinfo:
            end = datetime.combine(end.date(), end.time(), tzinfo=start.tzinfo)
        else:
            start = datetime.combine(start.date(), start.time(), tzinfo=end.tzinfo)
    return f"Time range: [{start} .. {end}] ({humanize.precisedelta(end - start)})."


class CircleCiCommand(Command):
    """Abstract base class for commands that use the CircleCI API."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self) -> None:
        super(CircleCiCommand, self).__init__()
        self.log_requests_to_file: Optional[SupportsWrite[str]] = None
        self.parser.add_argument(
            "--circleci_server",
            default="",
            type=str,
            help=(
                "The circleci server url including protocol (defaults to environment variable "
                "'CIRCLECI_SERVER' which defaults to 'https://circleci.com')."
            ),
        )
        self.parser.add_argument(
            "--circleci_token",
            default="",
            type=str,
            help="CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')",
        )
        self.parser.add_argument(
            "--circleci_project_slug",
            default="",
            type=str,
            help="CircleCI project-slug (defaults to environment variable 'CIRCLECI_PROJECT_SLUG').",
        )
        self.parser.add_argument(
            "--log_requests_to_file",
            type=Path,
            default=None,
            help="Whether to log all requests for debugging purposes.",
        )
        self.parser.add_argument(
            "--log_requests_details",
            default=[LogRequestDetail.REQUEST],
            type=LogRequestDetail,
            allow_empty=False,
            container_type=set,
            action=ActionEnumList,
            help="Comma separated list of LogRequestDetails.",
        )

    def Prepare(self, argv: list[str]) -> None:
        super(CircleCiCommand, self).Prepare(argv)
        self.log_requests_to_file = None
        if self.args.log_requests_to_file:
            self.log_requests_to_file = OpenTextFile(
                self.args.log_requests_to_file, "wt"
            )
        self.circleci = self._InitCircleCiClient(
            options=CircleCiApiV2Opts(
                circleci_server=self.args.circleci_server,
                circleci_token=self.args.circleci_token,
                project_slug=self.args.circleci_project_slug,
                log_requests_to_file=self.log_requests_to_file,  # Not from args!
                log_requests_details=self.args.log_requests_details,
            )
        )

    @staticmethod
    def _InitCircleCiClient(options: CircleCiApiV2Opts) -> CircleCiApiV2:
        options.circleci_server = str(
            options.circleci_server
            or os.getenv("CIRCLECI_SERVER", "https://circleci.com")
        )
        if not options.circleci_server:
            Die(
                "Must provide non empty `--circleci_server` flag or environment variable 'CIRCLECI_SERVER'."
            )
        options.circleci_token = str(
            options.circleci_token or os.getenv("CIRCLECI_TOKEN")
        )
        if not options.circleci_token:
            Die(
                "Must provide non empty `--circleci_token` flag or environment variable 'CIRCLECI_TOKEN'."
            )
        options.project_slug = str(
            options.project_slug or os.getenv("CIRCLECI_PROJECT_SLUG")
        )
        if not options.project_slug:
            Die(
                "Must provide non empty `--circleci_project_slug` flag or environment variable 'CIRCLECI_PROJECT_SLUG'."
            )
        return options.CreateClient()

    def AddDetails(self, row: dict[str, str]) -> dict[str, str]:
        """Fetches details for `row`, combines the row with the details and returns the result."""
        details: dict[str, str] = self.circleci.RequestWorkflowDetails(
            workflow_id=row["id"]
        )
        result: dict[str, str] = {
            k: v for k, v in row.items() if k in FETCH_WORKFLOW_DETAIL_KEYS
        }
        for k in FETCH_WORKFLOW_DETAIL_EXTRAS:
            if not row.get(k, ""):
                result[k] = details.get(k, "")
        return result

    def LogRowProgress(self, row_index: int) -> None:
        if self.args.progress:
            if not row_index % 1000:
                Log(f"{row_index}")
            elif not row_index % 20:
                Log(".", end="")

    def LogRowProgressEnd(self, row_index: int) -> None:
        if self.args.progress:
            if (row_index % 1000) < 20:
                Log(f".{row_index}")
            else:
                Log(f"{row_index}")


class RequestBranches(CircleCiCommand):
    """Read and display the list of branches for `workflow` from CircleCI API.

    By default this fetches branches for the workflow `default_workflow`. The workflow can be
    specified with the `--workflow` flag.

    ```
    bazel run //circleci:workflows -- request_branches
    ```
    """

    def __init__(self):
        super(RequestBranches, self).__init__()
        self.parser.add_argument(
            "--workflow",
            default="default_workflow",
            type=str,
            help="The name of the workflow to read. Multiple workflows can be read by separating with comma.",
        )

    def Main(self):
        branches = self.circleci.RequestBranches(workflow=self.args.workflow)
        Log(f"Read {len(branches)} branches.")
        for branch in branches:
            Print(branch)


class RequestWorkflows(CircleCiCommand):
    """Read and display the list of workflow names from CircleCI API.

    ```
    bazel run //circleci:workflows -- request_workflows
    ```
    """

    def __init__(self):
        super(RequestWorkflows, self).__init__()

    def Main(self):
        for workflow in self.circleci.RequestWorkflows():
            Print(workflow)


class RequestWorkflow(CircleCiCommand):
    """Given a workflow ID return its details.

    ```
    bazel run //circleci:workflows -- request_workflow --workflow_id <ID>
    ```
    """

    def __init__(self):
        super(RequestWorkflow, self).__init__()
        self.parser.add_argument(
            "--workflow_id",
            type=str,
            help="Workflow ID to request.",
        )

    def Main(self) -> None:
        Log(f"Request workflow {self.args.workflow_id}...")
        Print(self.circleci.RequestWorkflowDetails(workflow_id=self.args.workflow_id))


class Fetch(CircleCiCommand):
    """Fetch workflow data from the CircleCI API server and writes them as a CSV file.

    The time range to fetch runs for can be specified using flags `--start`, `--end` and `--midnight`.
    By default fetch will retrieve the data for the past 89 complete days starting at midnight.

    The easiest and intended way to manually control the time range is to speficy `--start` as an
    offset to the current time. For instance, using `--start=1w` will fetch runs for the past week.

    In many cases it is preferably to fetch data for complete days. That can be achieved by with the
    `--midnight` flag.

    After fetching general workflow information, the command will fetch all details if flag
    `fetch_workflow_details` if True (default).

    ```
    bazel run //circleci:workflows -- fetch --output "${PWD}/data/circleci_workflows_$(date +"%Y%m%d").csv.bz2"
    ```
    """

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
            action=ActionDateTimeOrTimeDelta,
            verify_only=True,
            help="""End (newest) date/time in Python [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601)
                format, e.g. `200241224` or as a negative time difference,
                e.g. `-10days` (for details see [pytimeparse](https://github.com/wroberts/pytimeparse)).

                This defaults to `now`.
            """,
        )
        self.parser.add_argument(
            "--start",
            default="",
            action=ActionDateTimeOrTimeDelta,
            verify_only=True,
            help="""Start (oldest) date/time in Python [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601)
                format, e.g. `200241224` or as a negative time difference,
                e.g. `-10days` (for details see [pytimeparse](https://github.com/wroberts/pytimeparse)).

                This defaults to `-90days` (or `-89days` if --midnight is active).
            """,
        )
        self.parser.add_argument(
            "--midnight",
            default=True,
            action=argparse.BooleanOptionalAction,
            help="""Adjust start and end date/time to midnight of the same day.
            """,
        )
        self.parser.add_argument(
            "--progress",
            action=argparse.BooleanOptionalAction,
            help="Whether to indicate progress (defaults to True if `--fetch_workflow_details` is active).",
        )
        self.parser.add_argument(
            "--fetch_workflow_details",
            default=True,
            action=argparse.BooleanOptionalAction,
            help="Whether workflow details should automatically be added.",
        )

    def Main(self) -> None:
        if self.args.fetch_workflow_details and self.args.progress == None:
            self.args.progress = True
        now = datetime.now(timezone.utc)
        end = ParseDateTimeOrTimeDelta(
            value=self.args.end,
            midnight=self.args.midnight,
            default=now,
            reference=now,
            error_prefix="Bad flag `--end` value '",
            error_suffix="'.",
        )
        start = ParseDateTimeOrTimeDelta(
            value=self.args.start,
            midnight=self.args.midnight,
            default=end - timedelta(days=90),
            reference=end,
            error_prefix="Bad flag `--start` value '",
            error_suffix="'.",
        )
        if (now - start) > timedelta(days=90):
            if self.args.start:
                Log("Specified start is more than the maximum of 90 days ago.")
            if self.args.midnight:
                if self.args.start:
                    Log("Adjusting to midnight from 89 days ago.")
                start = datetime.now(timezone.utc) - timedelta(days=89)
                start = datetime(
                    start.year,
                    start.month,
                    start.day,
                    tzinfo=start.tzinfo or timezone.utc,
                )
            else:
                if self.args.start:
                    Log("Adjusting to 90 days ago.")
                start = datetime.now(timezone.utc) - timedelta(days=90)
                start = datetime.combine(
                    start.date(), start.time(), tzinfo=start.tzinfo or timezone.utc
                )
        if start >= end:
            Die(f"Specified start time {start} must be before end time {end}!")
        Log(TimeRangeStr(start, end))
        Log(f"Fetching details: {self.args.fetch_workflow_details}")
        if self.args.workflow:
            workflows = self.args.workflow.split(",")
        else:
            workflows = self.circleci.RequestWorkflows()
        max_created: datetime | None = None
        min_created: datetime | None = None
        run_count = 0
        with OpenTextFile(filename=self.args.output, mode="w") as csv_file:
            keys = FETCH_WORKFLOW_KEYS
            print(f"{','.join(keys)}", file=csv_file)
            for workflow in sorted(workflows):
                Log(f"Fetching workflow runs for '{workflow}'.")
                runs = self.circleci.RequestWorkflowRuns(
                    workflow=workflow,
                    params={
                        "all-branches": "True",
                        "start-date": self.circleci.FormatTime(start),
                        "end-date": self.circleci.FormatTime(end),
                    },
                )
                if self.args.fetch_workflow_details:
                    Log(f"Fetching {len(runs)} workflow run details for '{workflow}'.")
                run_count += len(runs)
                for run_index, run in enumerate(runs, 1):
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
                    if self.args.fetch_workflow_details:
                        self.LogRowProgress(row_index=run_index)
                        run = self.AddDetails(run)
                    data = ",".join([str(run[k]) for k in keys])
                    print(data, file=csv_file)
                self.LogRowProgressEnd(row_index=run_index)
        if min_created and max_created:
            Log(TimeRangeStr(min_created, max_created))
        Log(f"Wrote {run_count} items to '{self.args.output}'.")


class FetchDetails(CircleCiCommand):
    """Given a workflow CSV file, fetch details for each workflow (slow).

    ```
    bazel run //circleci:workflows -- fetch_details --input "${PWD}/data/circleci_workflows_IN.csv.bz2" --output "${PWD}/data/circleci_workflows_OUT.csv.bz2"
    ```
    """

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
            default=True,
            action=argparse.BooleanOptionalAction,
            help="Whether to indicate progress.",
        )

    def Main(self) -> None:
        Log(f"Read file {self.args.input}...")
        data: dict[str, dict[str, str]] = {}
        if self.args.progress:
            Log("Fetching workflow details:", end="")
        with OpenTextFile(filename=self.args.input, mode="r") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=",")
            headers = set(reader.fieldnames or [])
            if not "id" in headers:
                Die(f"Bad field names [{headers}] does not have required 'id'.")
            if not headers.issubset(set(FETCH_WORKFLOW_DETAIL_KEYS)):
                Die(
                    f"Bad field names [{headers}], expected subset of [{FETCH_WORKFLOW_DETAIL_KEYS}]"
                )
            for index, row in enumerate(reader, 1):
                self.LogRowProgress(row_index=index)
                data[row["id"]] = self.AddDetails(row)
        self.LogRowProgressEnd(row_index=index)
        Log(f"Read {len(data)} details.")
        with OpenTextFile(filename=self.args.output, mode="w") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                delimiter=",",
                fieldnames=FETCH_WORKFLOW_DETAIL_KEYS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(sorted(data.values(), key=lambda d: d["created_unix"]))
        Log(f"Wrote {self.args.output}")


class Combine(CircleCiCommand):
    """Read multiple files generated by `workflow.py fetch` and combine them.

    ```
    bazel run //circleci:workflows -- combine --output=/tmp/circleci.csv "${PWD}/data/circleci_workflows*.csv*"
    ```
    """

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
        self.parser.add_argument(
            "--fetch_workflow_details",
            default=True,
            action=argparse.BooleanOptionalAction,
            help="Whether workflow details should automatically be added (if not present).",
        )
        self.parser.add_argument(
            "--progress",
            action=argparse.BooleanOptionalAction,
            help="Whether to indicate progress (defaults to True if `--fetch_workflow_details` is active).",
        )

    def Main(self) -> None:
        if len(self.args.input) < 2:
            Die("Must have at least 2 input files.")
        if self.args.fetch_workflow_details and self.args.progress == None:
            self.args.progress = True
        data: dict[str, dict[str, str]] = {}
        for filename in self.args.input:
            Log(f"Read file {filename}")
            with OpenTextFile(filename=filename, mode="r") as csv_file:
                reader = csv.DictReader(csv_file, delimiter=",")
                headers = set(reader.fieldnames or [])
                if not "id" in headers:
                    Die(f"Bad field names [{headers}] does not have required 'id'.")
                if not headers.issubset(set(FETCH_WORKFLOW_DETAIL_KEYS)):
                    Die(
                        f"Bad field names [{headers}], expected subset of [{FETCH_WORKFLOW_DETAIL_KEYS}]"
                    )
                rows = 0
                for row in reader:
                    rows += 1
                    if self.args.fetch_workflow_details:
                        row = self.AddDetails(row)
                    data[row["id"]] = row
                    self.LogRowProgress(row_index=rows)
                self.LogRowProgressEnd(row_index=rows)
                Log(f"Read file {filename} with {rows} rows.")
        with OpenTextFile(filename=self.args.output, mode="w") as csv_file:
            writer = csv.DictWriter(
                csv_file, delimiter=",", fieldnames=FETCH_WORKFLOW_DETAIL_KEYS
            )
            writer.writeheader()
            writer.writerows(sorted(data.values(), key=lambda d: d["created_unix"]))
        Log(f"Wrote file {self.args.output} with {len(data)} rows.")


class Filter(Command):
    """Read CSV files generated from `workflow.py fetch` and filters them.

    ```
    bazel run //circleci:workflows -- filter --workflow default_workflow,pre_merge --input /tmp/circleci.csv --output "${HOME}/circleci_filtered_workflows.csv"
    ```
    """

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
            "--min_duration_sec",  # TODO(helly25): Use a duration parser
            type=int,
            default=600,
            help="Mininum duration to accept row in [sec].",
        )
        self.parser.add_argument(
            "--output_duration_as_mins",
            default=True,
            action=argparse.BooleanOptionalAction,
            help="Whether to report duration values in minutes.",
        )
        self.parser.add_argument(
            "--exclude_branches",
            type=str,
            default="main|master|develop|develop-freeze.*",
            help="Exclude branches by full regular expression match.",
        )
        self.parser.add_argument(
            "--exclude_incomplete_reruns",
            default=True,
            action=argparse.BooleanOptionalAction,
            help="If workflow details are available, reject inomplete reruns "
            "(e.g.: rerun-single-job, rerun-workflow-from-failed).",
        )
        self.parser.add_argument(
            "--only_branches",
            type=str,
            default="",
            help="Accept branches by full regular expression match.",
        )
        self.parser.add_argument(
            "--only_status",
            type=str,
            default="success",
            help="Accept only listed status values (multiple separated by comma).",
        )
        self.parser.add_argument(
            "--only_weekdays",
            type=str,
            default="12345",
            help="Accept only the listed days of the week as indexed 1=Monday through 7=Sunday (ISO notation).",
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
        exclude_branches = (
            re.compile(self.args.exclude_branches)
            if self.args.exclude_branches
            else None
        )
        only_branches = (
            re.compile(self.args.only_branches) if self.args.only_branches else None
        )
        only_status = set(self.args.only_status.split(","))
        if [c for c in self.args.only_weekdays if c not in "1234567"]:
            Die(
                "Flag '--only_weekdays' must only contain weekday indices 1=Monday through 7=Sunday (ISO notation)."
            )
        with OpenTextFile(filename=self.args.input, mode="r") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=",")
            if not set(reader.fieldnames or []).issubset(
                set(FETCH_WORKFLOW_DETAIL_KEYS)
            ):
                Die(
                    f"File fieldnames '{reader.fieldnames}' not a subset of '{FETCH_WORKFLOW_DETAIL_KEYS}'."
                )
            if set(reader.fieldnames or []) == set(FETCH_WORKFLOW_DETAIL_KEYS):
                Log("Loading workflow CSV file with all details.")
                has_details = True
            elif set(reader.fieldnames or []) == set(FETCH_WORKFLOW_KEYS):
                Log(
                    "Loading workflow CSV file without workflow details (see command fetch_details)."
                )
            else:
                Log(
                    "Loading workflow CSV file with additional fields (see command fetch_details)."
                )
            for row in reader:
                count_rows += 1
                if exclude_branches and exclude_branches.fullmatch(row["branch"]):
                    continue
                if only_branches and not only_branches.fullmatch(row["branch"]):
                    continue
                if only_status and row["status"] not in only_status:
                    continue
                if (
                    has_details
                    and self.args.exclude_incomplete_reruns
                    and row["tag"] not in ["", "rerun-workflow-from-beginning"]
                ):
                    continue
                duration = float(row["duration"])
                if duration < self.args.min_duration_sec:
                    continue
                if self.args.output_duration_as_mins:
                    duration /= 60
                workflow = row["workflow"]
                workflows.add(workflow)
                if self.args.workflow and workflow not in self.args.workflow.split(","):
                    continue
                row["duration"] = str(duration)
                row[f"duration.{workflow}"] = str(duration)
                created = self.ParseTime(row["created"])
                if created.strftime("%u") not in self.args.only_weekdays:
                    continue
                # NOT detected by gsheets as date/time!
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
        with OpenTextFile(filename=self.args.output, mode="w") as csv_file:
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
        if sorted_data:
            Log(
                TimeRangeStr(
                    datetime.strptime(sorted_data[0][0]["date"], r"%Y.%m.%d"),
                    datetime.strptime(sorted_data[-1][0]["date"], r"%Y.%m.%d"),
                )
            )
        Log(f"Wrote {len(sorted_data)} rows to '{self.args.output}'.")
