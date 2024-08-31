#!/bin/bash

ROOT="$(realpath "$(dirname "${0}")/..")"

bazel run //circleci:workflows --color=yes -- help --help_output_mode=markdown --all_commands --prefix="${ROOT}/README.header.txt" > "${ROOT}/README.md"
