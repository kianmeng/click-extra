# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
# All Rights Reserved.
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

import sys
from operator import itemgetter
from pathlib import Path

import pygments
from boltons.strutils import camel2under
from pygments.lexers.shell import (
    BashSessionLexer,
    MSDOSSessionLexer,
    PowerShellSessionLexer,
    ShellSessionBaseLexer,
    TcshSessionLexer,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .. import pygments as extra_pygments
from ..pygments import shell_lexers

PROJECT_ROOT = Path(__file__).parent.parent.parent


all_shell_session_lexers = (
    lexer
    for lexer in pygments.lexers._iter_lexerclasses()
    if ShellSessionBaseLexer in lexer.__bases__
)


def test_all_shell_session_lexers_have_ansi_variant():
    assert set(all_shell_session_lexers) == {
        BashSessionLexer,
        MSDOSSessionLexer,
        PowerShellSessionLexer,
        TcshSessionLexer,
    }


def test_registered_lexers():
    entry_points = {}
    for lexer in shell_lexers:

        # Check an ANSI lexer variant is available in Click Extra.
        ansi_lexer_id = f"Ansi{lexer.__name__}"
        assert ansi_lexer_id in extra_pygments.__dict__

        # Transform ANSI lexer class ID into entry point ID.
        entry_id = "-".join(
            w for w in camel2under(ansi_lexer_id).split("_") if w != "lexer"
        )

        # Generate the lexer entry point.
        lexer_path = f"click_extra.pygments:{ansi_lexer_id}"
        entry_points[entry_id] = lexer_path

    entry_points = dict(sorted(entry_points.items(), key=itemgetter(0)))

    toml_path = PROJECT_ROOT.joinpath("pyproject.toml").resolve()
    toml_config = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    toml_entry_points = toml_config["tool"]["poetry"]["plugins"]["pygments.lexers"]
    assert toml_entry_points == entry_points
