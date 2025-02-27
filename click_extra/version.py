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
"""Extraction of CLI's version and its printing."""

from __future__ import annotations

import inspect
import re
from gettext import gettext as _
from importlib import metadata
from typing import TYPE_CHECKING
from functools import cached_property

from boltons.ecoutils import get_profile

from . import Context, Parameter, Style, echo, get_current_context
from .colorize import default_theme
from .parameters import ExtraOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cloup.styling import IStyle


class VersionOption(ExtraOption):
    """Gather CLI metadata and prints a colored version string.

    The elements composing the version string are made available in the context as:

    - ``ctx.meta["click_extra.prog_name"]``
    - ``ctx.meta["click_extra.package"]``
    - ``ctx.meta["click_extra.version"]``

    .. warning::
        This started as a `copy of the standard @click.version_option() decorator
        <https://github.com/pallets/click/blob/dc918b4/src/click/decorators.py#L399-L466>`_,
        but is **no longer a drop-in replacement**.

        Still, keep an eye on the original implementation to backport fixes and
        improvements.

    .. important::
        This option has been made into a class here, to allow its use with the declarative
        ``params=`` argument. Which `fixes Click #2324 issue
        <https://github.com/pallets/click/issues/2324>`_.

    .. important::
        This class has been augmented with...
    """

    def __init__(
        self,
        param_decls: Sequence[str] | None = None,

        version: str | None = None,
        package_name: str | None = None,
        prog_name: str | None = None,
        env_info: str | None = None,
        message: str | None = None,

        version_style: IStyle | None = Style(fg="green"),
        package_name_style: IStyle | None = default_theme.invoked_command,
        prog_name_style: IStyle | None = default_theme.invoked_command,
        env_info_style: IStyle | None = Style(fg="bright_black"),
        message_style: IStyle | None = None,

        is_flag=True,
        expose_value=False,
        is_eager=True,
        help=_("Show the version and exit."),
        **kwargs,
    ) -> None:
        """Adds a couple of extra parameters to the standard ``click.version_option``.

        :param version_style: adds environment info at the end of the message. Useful to
            gather user's details for troubleshooting. Defaults to
            ``Style(fg="green")``.
        :param package_name_style: style of the ``version``. Defaults to
            ``default_theme.invoked_command``.
        :param prog_name_style: style of the ``prog_name``. Defaults to
            ``default_theme.invoked_command``.
        :param message_style: default style of the ``message`` parameter. Defaults to
            ``None``.
        :param env_info_style: style of the environment info. Defaults to
            ``Style(fg="bright_black")``.

        For other params `see Click's version_option decorator
        <https://click.palletsprojects.com/en/8.1.x/api/#click.version_option>`_.
        """
        if not param_decls:
            param_decls = ("--version",)

        # Use the user-provided values instead of relying on auto-detection and defaults.
        if version:
            self.version = version
        if package_name:
            self.package_name = package_name
        if prog_name:
            self.prog_name = prog_name
        if env_info:
            self.env_info = env_info
        if message:
            self.message = message

        # Save the styles for later use.
        self.version_style = version_style
        self.package_name_style = package_name_style
        self.prog_name_style = prog_name_style
        self.env_info_style = env_info_style
        self.message_style = message_style

        kwargs.setdefault("callback", self.print_and_exit)

        super().__init__(
            param_decls=param_decls,
            is_flag=is_flag,
            expose_value=expose_value,
            is_eager=is_eager,
            help=help,
            **kwargs,
        )

    @cached_property
    def package_name(self) -> str | None:
        """Try to guess the package name.

        Inspects the stack frames to find the exact name of the installed package.
        """
        package_name = None

        frame = inspect.currentframe()

        f_back = None
        if frame is not None:
            # Get back one frame.
            f_back = frame.f_back
            if f_back is not None:
                f_class = f_back.f_locals['self'].__class__
                f_source = f"{f_class.__module__}.{f_class.__name__}"
                # Skip the intermediate frame added by the `@cached_property` decorator.
                if f_source == "functools.cached_property":
                    # Get back 2 frames: i.e. the frame before the decorator.
                    f_back = f_back.f_back

        f_globals = f_back.f_globals if f_back is not None else None

        # Break reference cycle
        # https://docs.python.org/3/library/inspect.html#the-interpreter-stack
        del frame

        if f_globals is not None:
            package_name = f_globals.get("__name__")

            if package_name == "__main__":
                package_name = f_globals.get("__package__")

            if package_name:
                package_name = package_name.partition(".")[0]

        return package_name

    @cached_property
    def version(self) -> str:
        try:
            version = metadata.version(self.package_name)
        except metadata.PackageNotFoundError:
            msg = (
                f"{self.package_name!r} is not installed. Try passing "
                "'package_name' instead."
            )
            raise RuntimeError(msg) from None

        if not version:
            msg = (
                f"Could not determine the version for {self.package_name!r} "
                "automatically."
            )
            raise RuntimeError(msg)

        return version

    @cached_property
    def prog_name(self) -> str:
        ctx = get_current_context()
        return ctx.find_root().info_name

    @cached_property
    def env_info(self) -> str:
        return str(get_profile(scrub=True))

    message: str = _("%(prog_name)s, version %(version)s")
    """Default message template used to render the version string."""

    def colored_template(self, template: str | None = None) -> str:
        """Insert ANSI style to a message template.

        Accepts a custom ``template`` as parameter, otherwise uses the default message defined on the instance.
        """
        # Map the template parts to their style function.
        part_vars = {
            "%(version)s": self.version_style,
            "%(package_name)s": self.package_name_style,
            "%(prog_name)s": self.prog_name_style,
            "%(env_info)s": self.env_info_style,
        }
        part_regex = re.compile(
            "(" +
            "|".join(map(re.escape, part_vars)) +
            ")"
        )

        if template is None:
            template = self.message

        colored_template = ""
        for part in re.split(part_regex, template):
            # Skip empty strings.
            if not part:
                continue
            # Get the style function for this part, defaults to `self.message_style`.
            style_func = part_vars.get(part, self.message_style)
            # Apply the style function if any, otherwise just append the part.
            colored_template += style_func(part) if style_func else part

        return colored_template

    def render_message(self, template: str | None = None) -> str:
        """Render the version string from the provided template.

        Accepts a custom ``template`` as parameter, otherwise uses the default ``self.colored_template()`` defined on the instance.
        """
        if template is None:
            template = self.colored_template()
        return template % {
            "version": self.version,
            "package_name": self.package_name,
            "prog_name": self.prog_name,
            "env_info": self.env_info,
        }

    def print_and_exit(
        self,
        ctx: Context,
        param: Parameter,
        value: bool,
    ) -> None:
        """Print the version string and exits.

        Also stores all version string elements in the context's ``meta`` `dict`.
        """
        # XXX ctx.meta doesn't cut it, we need to target ctx._meta.
        ctx._meta["click_extra.package_name"] = self.package_name
        # Trigger the version after package_name as it depends on it.
        ctx._meta["click_extra.version"] = self.version
        ctx._meta["click_extra.prog_name"] = self.prog_name
        ctx._meta["click_extra.env_info"] = self.env_info

        if not value or ctx.resilient_parsing:
            return None

        echo(self.render_message(), color=ctx.color)

        # Do not just ctx.exit() as it will prevent callbacks defined on options
        # to be called.
        ctx.close()
        ctx.exit()
        return None  # type: ignore[unreachable]