#!/usr/bin/env python3
"""Validate the WP1 OASYS2 workflow against the installed widget registry."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile


DEFAULT_WORKFLOW = Path(__file__).with_name("wp1_monoenergetic.ows")


def validate(workflow: Path) -> tuple[int, int]:
    # DABAX initializes while the crystal widget is discovered.  Keep its
    # cache writable even in read-only or sandboxed desktop installations.
    os.environ.setdefault("XDG_DATA_HOME", str(Path(tempfile.gettempdir()) / "wp1-oasys-data"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from orangecanvas.registry import WidgetRegistry
    from orangecanvas.scheme import Scheme
    from oasys2.canvas.config import OasysConfig
    from oasys2.canvas.scheme.readwrite import scheme_load

    registry = WidgetRegistry()
    discovery = OasysConfig.widget_discovery(registry)
    discovery.run(OasysConfig.widgets_entry_points())

    errors: list[Exception] = []
    scheme = Scheme()
    with workflow.open("rb") as stream:
        scheme_load(scheme, stream, registry=registry, error_handler=errors.append)

    if errors:
        details = "\n".join(f"- {type(error).__name__}: {error}" for error in errors)
        raise RuntimeError(f"OASYS2 rejected {workflow}:\n{details}")

    return len(scheme.nodes), len(scheme.links)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKFLOW,
        help="OASYS2 .ows workflow to validate",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    nodes, links = validate(args.workflow.resolve())
    print(f"Validated {args.workflow}: {nodes} nodes, {links} links")


if __name__ == "__main__":
    main()
