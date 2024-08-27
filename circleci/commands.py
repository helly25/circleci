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

For details read class `Command` documentation. Usage example:

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
from typing import TYPE_CHECKING, Any, Type, cast

if TYPE_CHECKING:
    from _typeshed import OpenTextMode
else:
    OpenTextMode = str


def Die(message: Any):
    print(f"FATAL: {message}", flush=True, file=sys.stderr)
    exit(1)


def Log(message: Any = "", end="\n", flush=True, file=None):
    print(message, end=end, flush=flush, file=file or sys.stderr)


def Print(message: Any = "", end="\n", flush=False, file=None):
    print(message, end=end, flush=flush, file=file or sys.stdout)


def OpenTextFile(
    filename: Path, mode: OpenTextMode, encoding="utf-8"
) -> io.TextIOWrapper:
    """Opens `filename` in `mode`, supporting '.gz' and '.bz2' files.

    Args:
        filename: The `Path` to be opened.
        mode:     The text mode to open the file with (e.g. 'rt, 'wt').
                  Modes `r` and `w` are automatically extended to `rt` and `wt`
                  respectively.
        encoding: The text encoding to use.

    Returns:
        The opened file as a `io.TextIOWrapper`.
    """
    if mode == "r":
        mode = "rt"
    elif mode == "w":
        mode = "wt"
    # Typeshed does not know that GZipFile and Bz2File use `io.TextIOWrapper` in text mode.
    if filename.suffix == ".gz":
        return cast(
            io.TextIOWrapper, gzip.open(filename=filename, mode=mode, encoding=encoding)
        )
    if filename.suffix == ".bz2":
        return cast(
            io.TextIOWrapper, bz2.open(filename=filename, mode=mode, encoding=encoding)
        )
    return filename.open(mode=mode, encoding=encoding)


def SnakeCase(text: str) -> str:
    """Convert `text` to snake_case.

    Replace dashes with spaces, then use regular expressions to split on words
    and acronyms, separate them by space. Then join the words with underscores,
    remove duplicate underscores and convert the result to lowercase.

    Args:
        text:   The inout text to convert.

    Returns:
        The Snake-Case version of `text`.
    """
    text = "_".join(re.sub("([A-Z]+[a-z]*)", r" \1", text.replace("-", " ")).split())
    return re.sub("_+", "_", text).lower()


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
    class's document string. In the example at the top the class `HelloDear`
    becomes sub-command `hello_dear`.

    The base class provides an argument parser `argparse.ArgumentParser` as
    `self.parser`. That parser should be extended in the `__init__` methods of
    derived Command implementations. The parser's description is also taken
    from the class's documentation string.

    The arguments are being parsed through `Prepare` which is always called
    right before `Main` gets invoked.
    """

    _commands: dict[str, Type] = {}

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

    def Prepare(self, argv: list[str]) -> None:
        """Prepare the command for execution by parsing the arguments in `argv`.

        Args:
            argv:  Unlike `Argparse.parse_args` this does not allow to be called
                   without arguments and requires the full `argv` including the
                   program argument at index 0. Effectivly this achieves the
                   same as if `Argparse.parse_args` was passed no argument (in
                   which case it uses `sys.argv`.
        """
        self.args = self.parser.parse_args(argv[1:])

    @abstractmethod
    def Main(self):
        pass

    @staticmethod
    def Run(argv: list[str] = sys.argv):
        program = argv[0] if argv else "-"
        command_name = argv[1] if len(argv) > 1 else ""
        match = re.fullmatch(
            "(?:.*/)?bazel-out/.*/bin/.*[.]runfiles/(?:__main__|_main)/(.*)/([^/]+)[.]py",
            program,
        )
        if match:
            program = f"bazel run //{match.group(1)}:{match.group(2)} --"
        if not Command._commands:
            Die("No Commands were implemented.")
        if command_name in Command._commands.keys():
            command = Command._commands[command_name]()
        else:
            command = None
        if len(argv) < 2 or not command:
            Command.Help(program)
        argv = [argv[0]] + argv[2:]
        command.Prepare(argv)
        try:
            command.Main()
        except Exception as err:
            Die(err)

    @staticmethod
    def Help(program: str):
        Print(f"Usage:\n  {program} <command> [args...]")
        Print()
        Print(
            "Most file based parameters transparently support gzip and bz2 compression when "
            "they have a '.gz' or '.bz2' extension respectively."
        )
        Print()
        Print("Commands:")
        c_len = 3 + max([len(c) for c in Command._commands.keys()])
        for name, command in sorted(Command._commands.items()):
            name = name + ":"
            Print(f"  {name:{c_len}s}{command.description()}")
        Print()
        Print(f"For help use: {program} <command> --help.")
        exit(1)
