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

"""Tool to fetch and analyze CircleCI workflows."""

package(default_visibility = ["//visibility:private"])

py_library(
    name = "commands_py",
    srcs = ["commands.py"],
)

py_test(
    name = "commands_test",
    srcs = ["commands_test.py"],
    deps = [":commands_py"],
)

py_binary(
    name = "workflows",
    testonly = True,
    srcs = ["workflows.py"],
    tags = ["manual"],
    deps = ["commands_py"],
)
