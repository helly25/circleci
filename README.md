# CircleCI tools

Continuous integration: [![Test](https://github.com/helly25/circleci/actions/workflows/main.yml/badge.svg)](https://github.com/helly25/circleci/actions/workflows/main.yml).

WIP

A simple [CircleCI API](https://circleci.com) client that fetches workflow
stats from the CircleCI API server and writes them as a CSV file.

# Usage
```
bazel run //circleci:workflows -- <command> [args...]
```

## Commands
* combine:            Read multiple files generated by `workflow.py fetch` and combine them.
* fetch:              Fetch workflow data from the CircleCI API server and writes them as a CSV file.
* fetch_details:      Given a workflow CSV file, fetch details for each workflow (slow).
* filter:             Read CSV files generated from `workflow.py fetch` and filters them.
* help:               Provides help for the program.
* request_branches:   Read and display the list of branches for `workflow` from CircleCI API.
* request_workflow:   Given a workflow ID return its details.
* request_workflows:  Read and display the list of workflow names from CircleCI API.

Most file based parameters transparently support gzip and bz2 compression when
they have a '.gz' or '.bz2' extension respectively.

## For command specific help use
```
bazel run //circleci:workflows -- <command> --help.
```

## Command combine

Read multiple files generated by `workflow.py fetch` and combine them.

```
bazel run //circleci:workflows -- combine --output=/tmp/circleci.csv "${PWD}/data/circleci_workflows*.csv*"
```

### positional arguments:

input

      List of CSV files generated from `workflow.py fetch`.

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.

--output OUTPUT

      Name of the output file.

--fetch_workflow_details, --no-fetch_workflow_details

      Whether workflow details should automatically be added (if not present).

--progress, --no-progress

      Whether to indicate progress (defaults to True if
      `--fetch_workflow_details` is active).


## Command fetch

Fetch workflow data from the CircleCI API server and writes them as a CSV
file.

The time range to fetch runs for can be specified using flags `--start`,
`--end` and `--midnight`. By default fetch will retrieve the data for the past
89 complete days starting at midnight.

The easiest and intended way to manually control the time range is to speficy
`--start` as an offset to the current time. For instance, using `--start=1w`
will fetch runs for the past week.

In many cases it is preferably to fetch data for complete days. That can be
achieved by with the `--midnight` flag.

After fetching general workflow information, the command will fetch all
details if flag `fetch_workflow_details` if True (default).

```
bazel run //circleci:workflows -- fetch --output "${PWD}/data/circleci_workflows_$(date +"%Y%m%d").csv.bz2"
```

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.

--workflow WORKFLOW

      The name of the workflow(s) to read. Multiple workflows can be read by
      separating with comma. If no workflow is set, then fetch all workflows.

--output OUTPUT

      Name of the output file.

--end END

      End (newest) date/time in Python [ISO
      8601](https://en.wikipedia.org/wiki/ISO_8601) format, e.g. `200241224`
      or as a negative time difference, e.g. `-10days` (for details see
      [pytimeparse](https://github.com/wroberts/pytimeparse)).

      This defaults to `now`.

--start START

      Start (oldest) date/time in Python [ISO
      8601](https://en.wikipedia.org/wiki/ISO_8601) format, e.g. `200241224`
      or as a negative time difference, e.g. `-10days` (for details see
      [pytimeparse](https://github.com/wroberts/pytimeparse)).

      This defaults to `-90days` (or `-89days` if --midnight is active).

--midnight, --no-midnight

      Adjust start and end date/time to midnight of the same day.

--progress, --no-progress

      Whether to indicate progress (defaults to True if
      `--fetch_workflow_details` is active).

--fetch_workflow_details, --no-fetch_workflow_details

      Whether workflow details should automatically be added.


## Command fetch_details

Given a workflow CSV file, fetch details for each workflow (slow).

```
bazel run //circleci:workflows -- fetch_details --input "${PWD}/data/circleci_workflows_IN.csv.bz2" --output "${PWD}/data/circleci_workflows_OUT.csv.bz2"
```

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.

--input INPUT

      A CSV file generated from `workflow.py fetch`.

--output OUTPUT

      Name of the output file.

--progress, --no-progress

      Whether to indicate progress.


## Command filter

Read CSV files generated from `workflow.py fetch` and filters them.

```
bazel run //circleci:workflows -- filter --workflow default_workflow,pre_merge --input /tmp/circleci.csv --output "${HOME}/circleci_filtered_workflows.csv"
```

### options:

-h, --help

      show this help message and exit

--workflow WORKFLOW

      The name of the workflow(s) to accept. Multiple workflows can be userd
      by separating with comma. If no workflow is set, then accept all
      workflows.

--input INPUT

      CSV file generated from `workflow.py fetch`.

--output OUTPUT

      Name of the output file.

--min_duration_sec MIN_DURATION_SEC

      Mininum duration to accept row in [sec].

--output_duration_as_mins, --no-output_duration_as_mins

      Whether to report duration values in minutes.

--exclude_branches EXCLUDE_BRANCHES

      Exclude branches by full regular expression match.

--exclude_incomplete_reruns, --no-exclude_incomplete_reruns

      If workflow details are available, reject inomplete reruns (e.g.: rerun-
      single-job, rerun-workflow-from-failed).

--only_branches ONLY_BRANCHES

      Accept branches by full regular expression match.

--only_status ONLY_STATUS

      Accept only listed status values (multiple separated by comma).

--only_weekdays ONLY_WEEKDAYS

      Accept only the listed days of the week as indexed 1=Monday through
      7=Sunday (ISO notation).


## Command request_branches

Read and display the list of branches for `workflow` from CircleCI API.

By default this fetches branches for the workflow `default_workflow`. The
workflow can be specified with the `--workflow` flag.

```
bazel run //circleci:workflows -- request_branches
```

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.

--workflow WORKFLOW

      The name of the workflow to read. Multiple workflows can be read by
      separating with comma.


## Command request_workflow

Given a workflow ID return its details.

```
bazel run //circleci:workflows -- request_workflow --workflow_id <ID>
```

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.

--workflow_id WORKFLOW_ID

      Workflow ID to request.


## Command request_workflows

Read and display the list of workflow names from CircleCI API.

```
bazel run //circleci:workflows -- request_workflows
```

### options:

-h, --help

      show this help message and exit

--circleci_server CIRCLECI_SERVER

      The circleci server url including protocol (defaults to environment
      variable 'CIRCLECI_SERVER' which defaults to 'https://circleci.com').

--circleci_token CIRCLECI_TOKEN

      CircleCI Auth Token (defaults to environment variable 'CIRCLECI_TOKEN')

--circleci_project_slug CIRCLECI_PROJECT_SLUG

      CircleCI project-slug (defaults to environment variable
      'CIRCLECI_PROJECT_SLUG').

--log_requests_to_file LOG_REQUESTS_TO_FILE

      Whether to log all requests for debugging purposes.

--log_requests_details {['REQUEST', 'RESPONSE_TEXT', 'STATUS_CODE']}

      Comma separated list of LogRequestDetails.
