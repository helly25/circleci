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

"""A simple sub-command framework.

Usage example:

```
#!/bin/env python3

import commands

class HelloDear(commands.Command):
    def __init__(self):
        super(FetchDetails, self).__init__()
        self.parser.add_argument("name", nargs="?")

    def Main(self):
        print(f"Hello, dear {self.args.name}.")

if __name__ == "__main__":
    commands.Command.Run()
```

Assuming the above is saved as `example.py`:

```
./example.py hello_dear me
```

Outputs: `Hello, dear me.`
"""

import argparse
import bz2
import gzip
import inspect
import io
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import OpenTextMode
else:
    OpenTextMode = str


def Die(message: Any):
    print(f"FATAL: {message}", flush=True, file=sys.stderr)
    exit(1)


def Log(message: Any = "", end="\n", flush=True, file=sys.stderr):
    print(message, end=end, flush=flush, file=file)


def Print(message: Any = "", end="\n", flush=False, file=sys.stdout):
    print(message, end=end, flush=flush, file=file)


def SnakeCase(text: str) -> str:
    """Convert `text` to snake_case.

    Replace dashes with spaces, then use regular expressions to split on words
    and acronyms, separate them by space. Then join the words with underscores
    and convert the result to lowercase.
    """
    return "_".join(
        re.sub(
            "([A-Z][a-z]+)", r" \1", re.sub("([A-Z]+)", r" \1", text.replace("-", " "))
        ).split()
    ).lower()


class Command(ABC):
    """Abstract base class to implement programs with sub-commands.

    A sub-command is identified by the first command-line argument which is
    matched against all registered non-abstract `Command` implementations. They
    must override `Main` which actually implements the command functionality
    that gets executed for the sub-command.

    Note that `Prepare` gets called prior to `Main` and provides `self.args`.
    In particular intermediate Command classes that are still abstract as they
    implement shared functionality may override `Parepare` while still providing
    `self.args` by calling `Command.Prepare`.

    All derived Command classes that are not abstract (see above) register
    themselves as a Command. The Command's command-line (sub-command) name is
    the snake_case version of their class name. The Command description is the
    class's document string. In the example below the class `HelloDear` becomes
    sub-command `hello_dear`.

    The base class provides an argument parser `argparse.ArgumentParser` as
    `self.parser`. That parser should be extended in the `__init__` methods of
    derived Command implementations. The parser's description is also taken
    from the class's documentation string.

    The arguments are being parsed through `Prepare` which is always called
    right before `Main` gets invoked.
    """

    _commands: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            cls._commands[cls.name()] = cls

    def __init__(self):
        self.parser = argparse.ArgumentParser(description=self.description())

    @classmethod
    def name(cls):
        return SnakeCase(cls.__name__)

    @classmethod
    def description(cls):
        return cls.__doc__

    def Prepare(self) -> None:
        self.args = self.parser.parse_args()

    @abstractmethod
    def Main(self):
        pass

    def Open(self, filename: Path, mode: OpenTextMode) -> Any:
        """Opens `filename` in `mode`, supporting '.gz' and '.bz2' files."""
        # TODO(helly25): Figure out how to actually return TextIOWrapper or something similar.
        if mode == "r":
            mode = "rt"
        elif mode == "w":
            mode = "wt"
        if filename.suffix == ".gz":
            return gzip.open(filename=filename, mode=mode)
        if filename.suffix == ".bz2":
            return bz2.open(filename=filename, mode=mode)
        return filename.open(mode=mode)

    @staticmethod
    def Run():
        program = sys.argv[0]
        match = re.fullmatch(
            "(?:.*/)?bazel-out/.*/bin/.*[.]runfiles/(?:__main__|_main)/(.*)/([^/]+)[.]py",
            program,
        )
        if match:
            program = f"bazel run //{match.group(1)}:{match.group(2)} --"
        commands: dict[str, Command] = {
            name: c() for name, c in __class__._commands.items()
        }
        if not commands:
            Die("No Commands were implemented.")
        if len(sys.argv) < 2 or sys.argv[1] not in commands.keys():
            Print(f"Usage:\n  {program} <command> [args...]")
            Print()
            Print(
                "Most file based parameters transparently support gzip and bz2 compression when "
                "they have a '.gz' or '.bz2' extension respectively."
            )
            Print()
            Print("Commands:")
            c_len = 3 + max([len(c) for c in commands.keys()])
            for name, command in commands.items():
                name = name + ":"
                Print(f"  {name:{c_len}s}{command.description()}")
            Print()
            Print(f"For help use: {program} <command> --help.")
            exit(1)
        command = commands[sys.argv[1]]
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        command.Prepare()
        command.Main()
