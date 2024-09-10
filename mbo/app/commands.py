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
    def __init__(self, parser: argparse.ArgumentParser):
        super(FetchDetails, self).__init__(parser)
        parser.add_argument("name", nargs="?")

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
import dataclasses
import gzip
import inspect
import io
import re
import sys
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Type, cast

from argparse_formatter import ParagraphFormatter

from mbo.app.flags import ActionEnum

if TYPE_CHECKING:
    from _typeshed import OpenTextMode
else:
    OpenTextMode = str


def Die(message: Any, exit_code: int = 1):
    print(f"FATAL: {message}", flush=True, file=sys.stderr)
    exit(exit_code)


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


class HelpOutputMode(Enum):
    TEXT = "text"
    MARKDOWN = "markdown"


class CommandParagraphFormatter(ParagraphFormatter):
    """A Paragraph formatter that can control TEXT and MARKDOWN formatting.

    The formatter is also able to handle '```' markdown correctly in either mode.
    """

    _help_output_mode: HelpOutputMode = HelpOutputMode.TEXT

    @classmethod
    def SetOutputMode(cls, output_mode: HelpOutputMode):
        cls._help_output_mode = output_mode

    def IsOutputMode(self, output_mode: HelpOutputMode) -> bool:
        return self._help_output_mode == output_mode

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        if len(indent) > 4:
            indent = " " * 4
        keep = False
        sub_text = ""
        result = ""
        for line in text.split("\n"):
            if line.startswith("```"):
                if not keep:
                    if sub_text:
                        result += super(CommandParagraphFormatter, self)._fill_text(
                            sub_text, width, indent
                        )
                        result += "\n\n"
                    sub_text = ""
                result += line + "\n"
                keep = not keep
                continue
            if keep:
                result += line + "\n"
            else:
                sub_text += line + "\n"
        if sub_text:
            result += super(CommandParagraphFormatter, self)._fill_text(
                sub_text, width, indent
            )
        return result

    def _format_action_invocation(self, action) -> str:
        result = super(CommandParagraphFormatter, self)._format_action_invocation(
            action
        )
        if self.IsOutputMode(HelpOutputMode.MARKDOWN):
            return "\n`" + result + "`\n\n"
        return result

    def _format_action(self, action) -> str:
        result: str = super(CommandParagraphFormatter, self)._format_action(action)
        if self.IsOutputMode(HelpOutputMode.MARKDOWN):
            text = []
            for r in result.split("\n"):
                if r.startswith("    "):
                    r = ("> " + r.lstrip()).rstrip()
                text.append(r)
            result = "\n".join(text)
        return result

    def _format_usage(self, usage, actions, groups, prefix):
        if self.IsOutputMode(HelpOutputMode.MARKDOWN):
            if not prefix:
                prefix = "### usage:"
        return super(CommandParagraphFormatter, self)._format_usage(
            usage, actions, groups, prefix
        )

    def start_section(self, heading: str | None) -> None:
        if self.IsOutputMode(HelpOutputMode.MARKDOWN):
            if heading:
                heading = f"### {heading}"
        super(CommandParagraphFormatter, self).start_section(heading)

    def add_argument(self, action):
        super(CommandParagraphFormatter, self).add_argument(action)
        if self.IsOutputMode(HelpOutputMode.MARKDOWN):
            self._action_max_length = 4


def DocOutdent(text: str) -> str:
    if not text:
        return text
    result = []
    lines = text.strip("\n").rstrip().split("\n")
    if text.startswith("\n") and not lines[0].startswith(" "):
        result.append(lines[0])
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

    The `__init__` function for all registered Commands will always be executed
    and thus should not contain expensive initialization.

    However, the commands may override `Prepare` which gets called prior to
    `Main`. Unline `__init__` the `Prepare` method will only be executed if the
    command is actually being executed. When `Prepare` gets executed `self.args`
    contains all parsed arguments. The `Prepare` method thus is the correct
    place for expensive initialization. Further, intermediate Command classes
    that are still abstract as they implement shared functionality may override
    `Parepare` while still invoking `Command.Prepare`. In `self.args.command`
    they can check the anem of the executed command.

    All derived Command classes that are not abstract (see above) register
    themselves as a Command. The Command's command-line (sub-command) name is
    the snake_case version of their class name. The Command description is the
    class's document string. In the example at the top the class `HelloDear`
    becomes sub-command `hello_dear`.

    The `__init__` method receives an argument parser `argparse.ArgumentParser`
    which must be forwarded to the base classes `__init__`. The base class then
    sets the parser's description to the class's documentation string. This
    `parser` can be used to add sub-command specific arguments.

    The arguments are being parsed prior to calling `Prepare` which is always
    called right before `Main` gets invoked.
    """

    @dataclasses.dataclass
    class CommandData:
        command_type: Any
        command: Any = None
        sub_parser: argparse.ArgumentParser | None = None

    _commands: dict[str, CommandData] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            cls._commands[cls.name()] = Command.CommandData(command_type=cls)

    def __init__(self, parser: argparse.ArgumentParser):
        parser.description = self.description()
        self.args: argparse.Namespace

    @classmethod
    def name(cls):
        return SnakeCase(cls.__name__)

    @classmethod
    def description(cls):
        return DocOutdent(cls.__doc__)

    def Prepare(self) -> None:
        """Prepare the command for execution after parsing the command line.

        Args:
            None

        Note: At the time of calling the commandline is parsed into `self.args`.
        """
        pass

    @abstractmethod
    def Main(self):
        pass

    @staticmethod
    def Run(argv: list[str] = sys.argv):
        program = argv[0] if argv else "-"
        match = re.fullmatch(
            "(?:.*/)?bazel-out/.*/bin/.*[.]runfiles/(?:__main__|_main)/(.*)/([^/]+)[.]py",
            program,
        )
        if match:
            program = f"bazel run //{match.group(1)}:{match.group(2)} --"
        else:
            match = re.fullmatch(
                ".*/unzipped_pexes/[0-9a-zA-Z]*/([^/]+)[.]py",
                program,
            )
            if match:
                program = f"{match.group(1)}.pex"

        parser = argparse.ArgumentParser(
            prog=program,
            formatter_class=CommandParagraphFormatter,
        )
        parser.add_argument(
            "--mbo_app_swallow_exceptions",
            action=argparse.BooleanOptionalAction,
            help="Whether to swollow details from exceptions and only show their error message.",
        )
        parser.add_argument(
            "--help_output_mode",
            "--help-output-mode",
            dest="help_output_mode",
            type=HelpOutputMode,
            action=ActionEnum,
            help="Output mode for help.",
        )

        # Initialize all commands and set their argument parsers.
        subparsers = parser.add_subparsers(
            dest="command",
            title="COMMAND",
            metavar="COMMAND",
            help=(
                f"The sub-command: {{{', '.join(Command._commands.keys())}}}.\n\n"
                f"Use `{program} help` to get an overview of all commands."
            ),
        )
        for command_name, command_data in Command._commands.items():
            command_data.sub_parser = subparsers.add_parser(
                name=command_name,
                formatter_class=CommandParagraphFormatter,
            )
            command_data.command = command_data.command_type(
                parser=command_data.sub_parser
            )

        # Parse the command line.
        args = parser.parse_args(argv[1:])

        # Check for a valid command.
        if not args.command or not args.command in Command._commands:
            # Reparse using just the arg "help", so we get that command.
            args = parser.parse_args(["help"], args)
            args.command = None

        # Get command and prepare for execution.
        command = Command._commands[args.command or "help"].command
        command.args = args
        command.Prepare()
        CommandParagraphFormatter.SetOutputMode(args.help_output_mode)

        # Execute sub-`command`.
        try:
            command.Main()
        except KeyboardInterrupt:
            Die(message="Interrupted!", exit_code=130)
        except Exception as err:
            if command.args.mbo_app_swallow_exceptions:
                Die(err)
            raise err


class Help(Command):
    """Provides help for the program."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        super(Help, self).__init__(parser)
        self.parser = parser
        self.exit_code = 0
        self.seq_empty_lines: int = 0
        parser.add_argument(
            "--all_commands",
            action=argparse.BooleanOptionalAction,
            help="Whether to show all commands",
        )
        parser.add_argument(
            "--show_usage",
            action=argparse.BooleanOptionalAction,
            help="Whether to show generated command useage (aka synopsis).",
        )
        parser.add_argument(
            "--prefix_file",
            type=Path,
            help="A file that should be used as a prefix on output.",
        )
        parser.add_argument(
            "--header_level",
            default=0,
            type=int,
            help="The current header level which gets added to the generated headers.",
        )

    def Print(self, text: str = "") -> None:
        # Deal with links...
        if self.args.help_output_mode == HelpOutputMode.TEXT:
            # In text mode replace replace images and links with their targets.
            img_re = re.compile(r"\[!\[([^\]]+)\]\([^\)]+\)\]\(([^\)]+)\)")
            lnk_re = re.compile(r"\[!?([^\]]+)\]\([^\)]+\)")
            while True:
                (text, n_img) = img_re.subn("\\1 (\\2)", text)
                (text, n_lnk) = lnk_re.subn("\\1", text)
                if not n_img and not n_lnk:
                    break
        # Allow at most 2 sequential empty lines. If there were some on the last
        # call to `Print`, then push at most two empty lines onto `result`.
        # Then loop over the lines and if there are empty lines count them.
        # For non empty lines print at most two empty lines if some empty lines
        # preceeded.
        max_empty_lines = 1
        self.seq_empty_lines = min(max_empty_lines, self.seq_empty_lines)
        text = "\n" * self.seq_empty_lines + text
        self.seq_empty_lines = 0
        for t in text.split("\n"):
            if t.count(" ") == len(t):
                t = ""
            if not t:
                self.seq_empty_lines = min(max_empty_lines, self.seq_empty_lines + 1)
            else:
                while self.seq_empty_lines > 0:
                    globals()["Print"]("")
                    self.seq_empty_lines -= 1
                self.seq_empty_lines = 0
                globals()["Print"](t)

    def _header(self, text: str, level: int = 1):
        if self.args.help_output_mode == HelpOutputMode.MARKDOWN:
            self.Print(f"{'#'*(level+self.args.header_level)} {text.rstrip(':')}")
        else:
            self.Print(f"{text}\n")

    def H1(self, text: str):
        self._header(text=text, level=1)

    def H2(self, text: str):
        self._header(text=text, level=2)

    def Code(self, text: str):
        if self.args.help_output_mode == HelpOutputMode.MARKDOWN:
            self.Print(f"```\n{text}\n```")
        else:
            self.Print(f"  {text}")

    def ListItem(self, text: str):
        if self.args.help_output_mode == HelpOutputMode.MARKDOWN:
            self.Print(f"* {text}")
        else:
            self.Print(f"  {text}")

    def Main(self) -> None:
        self.args.command = None
        if not self.args.command:
            self.parser.prog = self.parser.prog.removesuffix("help").removesuffix(" ")
        if self.args.prefix_file:
            self.Print(self.args.prefix_file.open("rt").read())
        first_line, program_doc = DocOutdent(
            str(sys.modules["__main__"].__doc__).strip()
        ).split("\n\n", 1)
        if first_line:
            self.Print(first_line)
            self.Print()
        self.H1(f"Usage:")
        self.Code(f"{self.parser.prog} <command> [args...]")
        self.Print()
        self.H2("Commands:")
        c_len = 3 + max([len(c) for c in Command._commands.keys()])
        for name, command_data in sorted(Command._commands.items()):
            name = name + ":"
            description = command_data.command_type.description().split("\n\n")[0]
            self.ListItem(f"{name:{c_len}s}{description}")
        self.Print()
        if program_doc:
            self.Print(program_doc)
            self.Print()
        self.H2(f"For command specific help use:")
        self.Code(f"{self.parser.prog} <command> --help.")
        if self.args.all_commands:
            for name, command_data in sorted(Command._commands.items()):
                if command_data.command_type.description().find("\n\n") == -1:
                    continue
                self.Print()
                self.H2(f"Command {name}")
                self.Print()
                if self.args.help_output_mode == HelpOutputMode.TEXT:
                    self.Print(command_data.command_type.description())
                else:
                    sub_parser = command_data.sub_parser
                    if sub_parser:
                        sub_parser.usage = argparse.SUPPRESS
                        self.Print(sub_parser.format_help())
        exit(self.exit_code)
