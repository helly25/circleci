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

"""Python application support library."""

load("@my_pip_deps//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "commands_py",
    srcs = ["commands.py"],
    deps = [
        ":flags_py",
        requirement("argparse-formatter"),
    ],
)

py_test(
    name = "commands_test",
    srcs = ["commands_test.py"],
    deps = [
        ":commands_py",
        requirement("parameterized"),
    ],
)

py_library(
    name = "flags_py",
    srcs = ["flags.py"],
    deps = [
        requirement("argparse-formatter"),
        requirement("pytimeparse"),
    ],
)

py_test(
    name = "flags_test",
    srcs = ["flags_test.py"],
    deps = [
        ":flags_py",
        requirement("freezegun"),
        requirement("parameterized"),
    ],
)
