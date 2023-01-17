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

"""Automation to keep click-extra documentation up-to-date.

.. tip::

    When the module is called directly, it will update all documentation files in-place:

    .. code-block:: shell-session

        $ run python -m click_extra.docs_update

    See how it is `used in .github/workflows/docs.yaml workflow
    <https://github.com/kdeldycke/click-extra/blob/a978bd07bbc3f760e82fee17ce6281c5790065ae/.github/workflows/docs.yaml#L35-L37>`_.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path
from textwrap import indent

import graphviz
from tabulate import tabulate

from . import __version__
from .platforms import ALL_GROUPS, EXTRA_GROUPS, NON_OVERLAPPING_GROUPS, Group
from .pygments import lexer_map


def replace_content(
    filepath: str, start_tag: str, end_tag: str, new_content: str
) -> None:
    """Replace in the provided file the content surrounded by the provided tags."""
    file = Path(__file__).parent.parent.joinpath(filepath).resolve()
    assert file.exists(), f"File {file} does not exist."
    assert file.is_file(), f"File {file} is not a file."

    orig_content = file.read_text()

    # Extract pre- and post-content surrounding the tags.
    pre_content, table_start = orig_content.split(start_tag, 1)
    _, post_content = table_start.split(end_tag, 1)

    # Reconstruct the content with our updated table.
    file.write_text(
        "".join(
            (
                pre_content,
                start_tag,
                new_content,
                end_tag,
                post_content,
            )
        )
    )


def generate_lexer_table():
    """Generate a Markdown table mapping original Pygments' lexers to their new ANSI
    variants implemented by Click Extra."""
    table = []
    for orig_lexer, ansi_lexer in sorted(
        lexer_map.items(), key=lambda i: i[0].__qualname__
    ):
        table.append(
            [
                f"[`{orig_lexer.__qualname__}`](https://pygments.org/docs/lexers/#"
                f"{orig_lexer.__module__}.{orig_lexer.__qualname__})",
                f"{', '.join(f'`{a}`' for a in sorted(orig_lexer.aliases))}",
                f"{', '.join(f'`{a}`' for a in sorted(ansi_lexer.aliases))}",
            ]
        )
    output = tabulate(
        table,
        headers=[
            "Original Lexer",
            "Original IDs",
            "ANSI variants",
        ],
        tablefmt="github",
        colalign=["left", "left", "left"],
        disable_numparse=True,
    )
    return output


def generate_platforms_graph(
    graph_id: str, description: str, groups: tuple[Group, ...]
):
    """Generates an `Euler diagram <https://xkcd.com/2721/>`_ of platform and their
    grouping.

    Returns a ready to use and properly indented MyST block.
    """
    INDENT = " " * 4

    dot = graphviz.Graph(
        name=graph_id,
        comment="Auto-generated by `click_extra.docs_update` module.",
        graph_attr={
            "layout": "osage",
            "fontname": "Helvetica,Arial,sans-serif",
            "fontsize": "36",
            "label": (
                "<<BR/><BR/>"
                f'<FONT FACE="Courier New"><B>click_extra.platforms.{html.escape(graph_id)}</B></FONT><BR/><BR/>'
                f"<I>{html.escape(description)}</I><BR/><BR/>"
                f'<FONT COLOR="gray">Click Extra v{html.escape(__version__)}</FONT><BR/>'
                ">"
            ),
        },
        node_attr={
            "color": "lightblue2",
            "style": "filled",
            "fontname": "Helvetica,Arial,sans-serif",
        },
        edge_attr={
            "dir": "none",
            "fontname": "Helvetica,Arial,sans-serif",
        },
    )

    for group in groups:
        with dot.subgraph(
            name=f"cluster_{group.id}",
            body=[f"{INDENT}cluster=true;\n"],
        ) as group_cluster:
            group_cluster.attr(fontsize="16")
            group_cluster.attr(
                label=(
                    "<"
                    f'<FONT FACE="Courier New"><B>click_extra.platforms.{html.escape(group.id.upper())}</B></FONT><BR/><BR/>'
                    f"<I>{html.escape(group.name)}.</I><BR/>"
                    ">"
                )
            )
            for platform in group:
                # Make the node ID unique for overlapping groups.
                group_cluster.node(
                    f"{group.id}_{platform.id}",
                    label=graphviz.escape(f"{platform.id} - {platform.name}"),
                )

    # XXX Should we add an "unflatten()" call here for better readability?

    # Wrap the dot code in a MyST block invoking the graphviz rST directive.
    dot_code = dot.source.replace("\t", INDENT).strip()
    return "\n".join(
        (
            "```{eval-rst}",
            ".. graphviz::\n",
            indent(dot_code, " " * 3),
            "```",
        )
    )


def update_docs():
    """Update documentation with dynamic content."""
    # Update the lexer table in Sphinx's documentation.
    replace_content(
        "docs/pygments.md",
        "<!-- lexer-table-start -->\n\n",
        "\n\n<!-- lexer-table-end -->",
        generate_lexer_table(),
    )

    # TODO: Replace this hard-coded dict by allowing Group dataclass to group
    # other groups.
    all_groups = (
        {
            "id": "NON_OVERLAPPING_GROUPS",
            "description": "Non-overlapping groups.",
            "groups": NON_OVERLAPPING_GROUPS,
        },
        {
            "id": "EXTRA_GROUPS",
            "description": "Overlapping groups, defined for convenience.",
            "groups": EXTRA_GROUPS,
        },
    )
    assert tuple(g for groups in all_groups for g in groups["groups"]) == ALL_GROUPS

    # Update the platform diagram in Sphinx's documentation.
    for top_groups in all_groups:
        replace_content(
            "docs/platforms.md",
            f"<!-- {top_groups['id']}-graph-start -->\n",
            f"\n<!-- {top_groups['id']}-graph-end -->",
            generate_platforms_graph(
                top_groups["id"], top_groups["description"], top_groups["groups"]
            ),
        )


if __name__ == "__main__":
    sys.exit(update_docs())
