#!/bin/bash

ROOT="$(realpath "$(dirname "${0}")/..")"

bazel run //circleci:workflows --color=yes -- help \
  --all_commands \
  --header_level=1 \
  --help_output_mode=markdown \
  --prefix="${ROOT}/README.header.txt" \
  > "${ROOT}/README.md"
