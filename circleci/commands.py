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
from enum import Enum
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


def DocOutdent(text: str) -> str:
    if not text:
        return text
    result = []
    lines = text.strip("\n").rstrip().split("\n")
    if text.startswith("\n") and not lines[0].startswith(" "):
        result.append("XXX" + lines[0])
        lines.pop(0)
    max_indent = -1
    for line in lines:
        if line:
            indent = len(line) - len(line.lstrip())
            if indent and (max_indent == -1 or indent < max_indent):
                max_indent = indent
    if max_indent < 1:
        result.extend(lines)
    else:
        prefix = " " * max_indent
        for line in lines:
            if line.startswith(prefix):
                result.append(line.removeprefix(prefix))
            else:
                result.append(line)
    return "\n".join(result)


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
        return DocOutdent(cls.__doc__)

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
        command_name = argv[1] if len(argv) > 1 else ""
        if not Command._commands:
            Die("No Commands were implemented.")
        if command_name in Command._commands.keys():
            command = Command._commands[command_name]()
        else:
            command = None
        if len(argv) < 2 or not command:
            command = Command._commands["help"]()
        argv = [argv[0]] + argv[2:]
        command.Prepare(argv)
        try:
            command.Main()
        except Exception as err:
            Die(err)


class HelpOutputMode(Enum):
    TEXT = "text"
    MARKDOWN = "markdown"


class Help(Command):
    """Provides help for the program."""

    def __init__(self):
        super(Help, self).__init__()
        self.parser.add_argument(
            "--mode",
            type=HelpOutputMode,
            default=HelpOutputMode.TEXT,
            help="The output mode for printing help.",
        )
        self.parser.add_argument(
            "--all_commands",
            action="store_true",
            help="Whether to show all commands",
        )
        self.parser.add_argument(
            "--prefix",
            type=Path,
            default="",
            help="A file that should be used as a prefix on output.",
        )

    def Prepare(self, argv: list[str]) -> None:
        super(Help, self).Prepare(argv)
        self.program = argv[0] if argv else "-"
        match = re.fullmatch(
            "(?:.*/)?bazel-out/.*/bin/.*[.]runfiles/(?:__main__|_main)/(.*)/([^/]+)[.]py",
            self.program,
        )
        if match:
            self.program = f"bazel run //{match.group(1)}:{match.group(2)} --"

    def Print(self, text: str = ""):
        if self.args.mode == HelpOutputMode.TEXT:
            # In text mode replace replace images and links with their targets.
            img_re = re.compile(r"\[!\[([^\]]+)\]\([^\)]+\)\]\(([^\)]+)\)")
            lnk_re = re.compile(r"\[!?([^\]]+)\]\([^\)]+\)")
            while True:
                (text, n_img) = img_re.subn("\\1 (\\2)", text)
                (text, n_lnk) = lnk_re.subn("\\1", text)
                if not n_img and not n_lnk:
                    break
        globals()["Print"](text)

    def H1(self, text: str):
        if self.args.mode == HelpOutputMode.MARKDOWN:
            self.Print(f"# {text.rstrip(':')}")
        else:
            self.Print(f"{text}\n")

    def H2(self, text: str):
        if self.args.mode == HelpOutputMode.MARKDOWN:
            self.Print(f"## {text.rstrip(':')}")
        else:
            self.Print(f"{text}\n")

    def Code(self, text: str):
        if self.args.mode == HelpOutputMode.MARKDOWN:
            self.Print(f"```\n{text}\n```")
        else:
            self.Print(f"  {text}")

    def ListItem(self, text: str):
        if self.args.mode == HelpOutputMode.MARKDOWN:
            self.Print(f"* {text}")
        else:
            self.Print(f"  {text}")

    def Main(self) -> None:
        if self.args.prefix:
            self.Print(self.args.prefix.open("rt").read())
        first_line, program_doc = DocOutdent(
            str(sys.modules["__main__"].__doc__).strip()
        ).split("\n\n", 1)
        if first_line:
            self.Print(first_line)
            self.Print()
        self.H1(f"Usage:")
        self.Code(f"{self.program} <command> [args...]")
        self.Print()
        self.H2("Commands:")
        c_len = 3 + max([len(c) for c in Command._commands.keys()])
        for name, command in sorted(Command._commands.items()):
            name = name + ":"
            description = command.description().split("\n\n")[0]
            self.ListItem(f"{name:{c_len}s}{description}")
        self.Print()
        if program_doc:
            self.Print(program_doc)
            self.Print()
        self.H2(f"For command specific help use:")
        self.Code(f"{self.program} <command> --help.")
        if self.args.all_commands:
            for name, command in sorted(Command._commands.items()):
                if command.description().find("\n\n") == -1:
                    continue
                self.Print()
                self.H2(f"Command {name}")
                self.Print()
                self.Print(command.description())
        exit(1)
