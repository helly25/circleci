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

"""A simple [CircleCI API](https://circleci.com) client that fetches workflow
stats from the CircleCI API server and writes them as a CSV file.

Most file based parameters transparently support gzip and bz2 compression when
they have a '.gz' or '.bz2' extension respectively.
"""

import circleci.workflows_lib
from circleci.commands import Command

if __name__ == "__main__":
    Command.Run()
