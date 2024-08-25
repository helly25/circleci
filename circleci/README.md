# //circleci:workflows

A simple program to fetch and analyze CircleCI workflow stats.

## List of commands

```
bazel run //circleci:workflows
```

## List workflows

```
bazel run //circleci:workflows -- workflows
```

## List branches

```
bazel run //circleci:workflows -- branches
```

## Fetch workflow data

```
bazel run //circleci:workflows -- fetch --output "${PWD}/circleci/stats/data/circleci_workflows_$(date +"%Y%m%d").csv.bz2"
```

## Combine workflow data

```
bazel run //circleci:workflows -- combine --output=/tmp/circleci.csv "${PWD}/circleci/stats/data/circleci_workflows*.csv*"
```

## Filter workflow data

```
bazel run //circleci:workflows -- filter --workflow default_workflow,pre_merge --input /tmp/circleci.csv --output "${HOME}/circleci_filtered_workflows.csv"
```
