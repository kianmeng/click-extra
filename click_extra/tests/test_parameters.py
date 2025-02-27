# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

from __future__ import annotations

from os.path import sep
from pathlib import Path
from textwrap import dedent

import click
import pytest
from pytest_cases import parametrize
from tabulate import tabulate

from click_extra import command, echo, get_app_dir, option, pass_context
from click_extra.decorators import extra_command, extra_group, show_params_option
from click_extra.parameters import ShowParamsOption, extend_envvars, normalize_envvar
from click_extra.platforms import is_windows

from .conftest import command_decorators


@pytest.mark.parametrize(
    ("envvars_1", "envvars_2", "result"),
    (
        ("MY_VAR", "MY_VAR", ("MY_VAR",)),
        (None, "MY_VAR", ("MY_VAR",)),
        ("MY_VAR", None, ("MY_VAR",)),
        (["MY_VAR"], "MY_VAR", ("MY_VAR",)),
        (["MY_VAR"], None, ("MY_VAR",)),
        ("MY_VAR", ["MY_VAR"], ("MY_VAR",)),
        (None, ["MY_VAR"], ("MY_VAR",)),
        (["MY_VAR"], ["MY_VAR"], ("MY_VAR",)),
        (["MY_VAR1"], ["MY_VAR2"], ("MY_VAR1", "MY_VAR2")),
        (["MY_VAR1", "MY_VAR2"], ["MY_VAR2"], ("MY_VAR1", "MY_VAR2")),
        (["MY_VAR1"], ["MY_VAR1", "MY_VAR2"], ("MY_VAR1", "MY_VAR2")),
        (["MY_VAR1"], ["MY_VAR2", "MY_VAR2"], ("MY_VAR1", "MY_VAR2")),
        (["MY_VAR1", "MY_VAR1"], ["MY_VAR2"], ("MY_VAR1", "MY_VAR2")),
    ),
)
def test_extend_envvars(envvars_1, envvars_2, result):
    assert extend_envvars(envvars_1, envvars_2) == result


@pytest.mark.parametrize(
    ("env_name", "normalized_env"),
    (
        ("show-params-cli_VERSION", "SHOW_PARAMS_CLI_VERSION"),
        ("show---params-cli___VERSION", "SHOW_PARAMS_CLI_VERSION"),
        ("__show-__params-_-_-", "SHOW_PARAMS"),
    ),
)
def test_normalize_envvar(env_name, normalized_env):
    assert normalize_envvar(env_name) == normalized_env


@pytest.mark.parametrize(
    ("cmd_decorator", "option_help"),
    (
        # Click does not show the auto-generated envvar in the help screen.
        (click.command, "  --flag / --no-flag  [env var: custom]\n"),
        # Click Extra always adds the auto-generated envvar to the help screen
        # (and show the defaults).
        (
            extra_command,
            "  --flag / --no-flag        "
            "[env var: custom, yo_FLAG; default: no-flag]\n",
        ),
    ),
)
def test_show_auto_envvar_help(invoke, cmd_decorator, option_help):
    """Check that the auto-generated envvar appears in the help screen with the extra
    variants.

    Checks that https://github.com/pallets/click/issues/2483 is addressed.
    """

    @cmd_decorator(context_settings={"auto_envvar_prefix": "yo"})
    @option("--flag/--no-flag", envvar=["custom"], show_envvar=True)
    def envvar_help():
        pass

    result = invoke(envvar_help, "--help")
    assert result.exit_code == 0
    assert not result.stderr
    assert option_help in result.stdout


def envvars_test_cases():
    params = []

    matrix = {
        (command, "command"): {
            "working_envvar": (
                # User-defined envvars are recognized as-is.
                "Magic",
                "sUper",
                # XXX Uppercased auto-generated envvar is recognized but should not be.
                "YO_FLAG",
            ),
            "unknown_envvar": (
                # Uppercased user-defined envvar is not recognized.
                "MAGIC",
                # XXX Literal auto-generated is not recognized but should be.
                "yo_FLAG",
                # Mixed-cased auto-generated envvat is not recognized.
                "yo_FlAg",
            ),
        },
        (extra_command, "extra_command"): {
            "working_envvar": (
                # User-defined envvars are recognized as-is.
                "Magic",
                "sUper",
                # Literal auto-generated is properly recognized but is not in vanilla
                # Click (see above).
                "yo_FLAG",
                # XXX Uppercased auto-generated envvar is recognized but should not be.
                "YO_FLAG",
            ),
            "unknown_envvar": (
                # Uppercased user-defined envvar is not recognized.
                "MAGIC",
                # Mixed-cased auto-generated envvat is not recognized.
                "yo_FlAg",
            ),
        },
    }

    # Windows is automaticcaly normalizing any env var to upper-case, see:
    # https://github.com/python/cpython/blob/e715da6/Lib/os.py#L748-L749
    # https://docs.python.org/3/library/os.html?highlight=environ#os.environ
    # So Windows needs its own test case.
    if is_windows():
        all_envvars = (
            "Magic",
            "MAGIC",
            "sUper",
            "yo_FLAG",
            "YO_FLAG",
            "yo_FlAg",
        )
        matrix = {
            (command, "command"): {
                "working_envvar": all_envvars,
                "unknown_envvar": (),
            },
            (extra_command, "extra_command"): {
                "working_envvar": all_envvars,
                "unknown_envvar": (),
            },
        }

    # If properly recognized, these envvar values should be passed to the flag.
    working_value_map = {
        "True": True,
        "true": True,
        "tRuE": True,
        "1": True,
        "": False,  # XXX: Should be True?
        "False": False,
        "false": False,
        "fAlsE": False,
        "0": False,
    }
    # No envvar value will have an effect on the flag if the envvar is not recognized.
    broken_value_map = {k: False for k in working_value_map}

    for (cmd_decorator, decorator_name), envvar_cases in matrix.items():
        for case_name, envvar_names in envvar_cases.items():
            value_map = (
                working_value_map if case_name == "working_envvar" else broken_value_map
            )

            for envvar_name in envvar_names:
                for envar_value, expected_flag in value_map.items():
                    envvar = {envvar_name: envar_value}
                    params.append(
                        pytest.param(
                            cmd_decorator,
                            envvar,
                            expected_flag,
                            id=f"{decorator_name}|{case_name}={envvar}|expected_flag={expected_flag}",
                        ),
                    )

    return params


@parametrize("cmd_decorator, envvars, expected_flag", envvars_test_cases())
def test_auto_envvar_parsing(invoke, cmd_decorator, envvars, expected_flag):
    """This test highlights the way Click recognize and parse envvars.

    It shows that the default behavior is not ideal, and covers how ``extra_command``
    improves the situation by normalizing the envvar name.
    """

    @cmd_decorator(context_settings={"auto_envvar_prefix": "yo"})
    @option("--flag/--no-flag", envvar=["Magic", "sUper"])
    def my_cli(flag):
        echo(f"Flag value: {flag}")

    registered_envvars = ["Magic", "sUper"]
    # @extra_command forces registration of auto-generated envvar.
    if cmd_decorator == extra_command:
        registered_envvars = (*registered_envvars, "yo_FLAG")
    assert my_cli.params[0].envvar == registered_envvars

    result = invoke(my_cli, env=envvars)
    assert result.exit_code == 0
    assert not result.stderr
    assert result.stdout == f"Flag value: {expected_flag}\n"


def test_raw_args(invoke):
    """Raw args are expected to be scoped in subcommands."""

    @extra_group
    @option("--dummy-flag/--no-flag")
    @pass_context
    def my_cli(ctx, dummy_flag):
        echo("-- Group output --")
        echo(f"dummy_flag is {dummy_flag!r}")
        echo(f"Raw parameters: {ctx.meta.get('click_extra.raw_args', [])}")

    @my_cli.command()
    @pass_context
    @option("--int-param", type=int, default=10)
    def subcommand(ctx, int_param):
        echo("-- Subcommand output --")
        echo(f"int_parameter is {int_param!r}")
        echo(f"Raw parameters: {ctx.meta.get('click_extra.raw_args', [])}")

    result = invoke(my_cli, "--dummy-flag", "subcommand", "--int-param", "33")
    assert result.exit_code == 0
    assert not result.stderr
    assert result.stdout == dedent(
        """\
        -- Group output --
        dummy_flag is True
        Raw parameters: ['--dummy-flag', 'subcommand', '--int-param', '33']
        -- Subcommand output --
        int_parameter is 33
        Raw parameters: ['--int-param', '33']
        """,
    )


@parametrize(
    "cmd_decorator",
    # Skip click extra's commands, as show_params option is already part of the default.
    command_decorators(no_groups=True, no_extra=True),
)
@parametrize("option_decorator", (show_params_option, show_params_option()))
def test_standalone_show_params_option(invoke, cmd_decorator, option_decorator):
    @cmd_decorator
    @option_decorator
    def show_params():
        echo("It works!")

    result = invoke(show_params, "--show-params")
    assert result.exit_code == 0

    table = [
        (
            "show-params.show_params",
            "click_extra.parameters.ShowParamsOption",
            "--show-params",
            "bool",
            "",
            "✘",
            "",
            False,
            "",
            "COMMANDLINE",
        ),
    ]
    output = tabulate(
        table,
        headers=ShowParamsOption.TABLE_HEADERS,
        tablefmt="rounded_outline",
        disable_numparse=True,
    )
    assert result.stdout == f"{output}\n"

    assert result.stderr.endswith(
        "warning: Cannot extract parameters values: "
        "<Command show-params> does not inherits from ExtraCommand.\n",
    )


def test_integrated_show_params_option(invoke, create_config):
    @extra_command
    @option("--int-param1", type=int, default=10)
    @option("--int-param2", type=int, default=555)
    def show_params_cli(int_param1, int_param2):
        echo(f"int_param1 is {int_param1!r}")
        echo(f"int_param2 is {int_param2!r}")

    conf_file = """
        [show-params-cli]
        int_param1 = 3
        extra_value = "unallowed"
        """
    conf_path = create_config("show-params-cli.toml", conf_file)

    raw_args = [
        "--verbosity",
        "DeBuG",
        "--config",
        str(conf_path),
        "--int-param1",
        "9999",
        "--show-params",
        "--help",
    ]
    result = invoke(show_params_cli, *raw_args, color=False)

    assert result.exit_code == 0
    assert f"debug: click_extra.raw_args: {raw_args!r}\n" in result.stderr

    table = [
        (
            "show-params-cli.color",
            "click_extra.colorize.ColorOption",
            "--color, --ansi / --no-color, --no-ansi",
            "bool",
            "✓",
            "✘",
            "SHOW_PARAMS_CLI_COLOR",
            True,
            True,
            "DEFAULT",
        ),
        (
            "show-params-cli.config",
            "click_extra.config.ConfigOption",
            "-C, --config CONFIG_PATH",
            "str",
            "✘",
            "✘",
            "SHOW_PARAMS_CLI_CONFIG",
            f"{Path(get_app_dir('show-params-cli')).resolve()}{sep}*.{{toml,yaml,yml,json,ini,xml}}",
            str(conf_path),
            "COMMANDLINE",
        ),
        (
            "show-params-cli.help",
            "click_extra.colorize.HelpOption",
            "-h, --help",
            "bool",
            "✘",
            "✘",
            "SHOW_PARAMS_CLI_HELP",
            False,
            True,
            "COMMANDLINE",
        ),
        (
            "show-params-cli.int_param1",
            "cloup._params.Option",
            "--int-param1 INTEGER",
            "int",
            "✓",
            "✓",
            "SHOW_PARAMS_CLI_INT_PARAM1",
            3,
            9999,
            "COMMANDLINE",
        ),
        (
            "show-params-cli.int_param2",
            "cloup._params.Option",
            "--int-param2 INTEGER",
            "int",
            "✓",
            "✓",
            "SHOW_PARAMS_CLI_INT_PARAM2",
            555,
            555,
            "DEFAULT",
        ),
        (
            "show-params-cli.show_params",
            "click_extra.parameters.ShowParamsOption",
            "--show-params",
            "bool",
            "✘",
            "✘",
            "SHOW_PARAMS_CLI_SHOW_PARAMS",
            False,
            True,
            "COMMANDLINE",
        ),
        (
            "show-params-cli.time",
            "click_extra.timer.TimerOption",
            "--time / --no-time",
            "bool",
            "✓",
            "✘",
            "SHOW_PARAMS_CLI_TIME",
            False,
            False,
            "DEFAULT",
        ),
        (
            "show-params-cli.verbosity",
            "click_extra.logging.VerbosityOption",
            "-v, --verbosity LEVEL",
            "str",
            "✓",
            "✘",
            "SHOW_PARAMS_CLI_VERBOSITY",
            "WARNING",
            "DeBuG",
            "COMMANDLINE",
        ),
        (
            "show-params-cli.version",
            "click_extra.version.VersionOption",
            "--version",
            "bool",
            "✘",
            "✘",
            "SHOW_PARAMS_CLI_VERSION",
            False,
            False,
            "DEFAULT",
        ),
    ]
    output = tabulate(
        table,
        headers=ShowParamsOption.TABLE_HEADERS,
        tablefmt="rounded_outline",
        disable_numparse=True,
    )
    assert result.stdout == f"{output}\n"

    assert f"debug: click_extra.raw_args: {raw_args}" in result.stderr
