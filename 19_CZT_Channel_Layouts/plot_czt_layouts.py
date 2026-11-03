#!/usr/bin/env python3
"""Compare possible layouts for 20 circular CZT readout electrodes.

The circles represent anode/readout channels patterned on one monolithic CZT
crystal, not twenty separate crystals. Dimensions are expressed in millimetres.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch


@dataclass(frozen=True)
class Layout:
    name: str
    subtitle: str
    points: list[tuple[float, float]]


def rectangular(rows: int, columns: int, pitch: float) -> list[tuple[float, float]]:
    return [(column * pitch, row * pitch) for row in range(rows) for column in range(columns)]


def staggered(rows: int, columns: int, pitch: float) -> list[tuple[float, float]]:
    dy = pitch * 3**0.5 / 2
    return [
        (column * pitch + (row % 2) * pitch / 2, row * dy)
        for row in range(rows)
        for column in range(columns)
    ]


def concentric(pitch: float) -> list[tuple[float, float]]:
    # One central channel, six in the first ring and thirteen in the second.
    points = [(0.0, 0.0)]
    for count, radius in ((6, pitch), (13, 2.18 * pitch)):
        for index in range(count):
            angle = 2 * 3.141592653589793 * index / count
            points.append((radius * __import__("math").cos(angle), radius * __import__("math").sin(angle)))
    return points


def centered(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    xs, ys = zip(*points)
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    return [(x - cx, y - cy) for x, y in points]


def footprint(points: list[tuple[float, float]], diameter: float, margin: float) -> tuple[float, float]:
    xs, ys = zip(*points)
    return max(xs) - min(xs) + diameter + 2 * margin, max(ys) - min(ys) + diameter + 2 * margin


def draw_layout(ax, layout: Layout, diameter: float, margin: float) -> None:
    points = centered(layout.points)
    width, height = footprint(points, diameter, margin)
    crystal = FancyBboxPatch(
        (-width / 2, -height / 2), width, height,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        facecolor="#e8edf3", edgecolor="#263746", linewidth=1.4,
    )
    ax.add_patch(crystal)

    for number, (x, y) in enumerate(points, start=1):
        ax.add_patch(Circle((x, y), diameter / 2, facecolor="#d9a520", edgecolor="#563d00", linewidth=0.8))
        ax.text(x, y, str(number), ha="center", va="center", fontsize=5.6, color="#202020")

    ax.set_title(f"{layout.name}\n{layout.subtitle}", fontsize=11.5, weight="bold", pad=10, linespacing=1.45)
    ax.text(
        0.5, -0.04, f"Footprint ≈ {width:.2f} × {height:.2f} mm",
        transform=ax.transAxes, ha="center", va="top", fontsize=8.5,
    )
    pad = 0.25
    ax.set_xlim(-width / 2 - pad, width / 2 + pad)
    ax.set_ylim(-height / 2 - pad, height / 2 + pad)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot alternative layouts for 20 circular CZT channels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--pitch", type=float, default=0.50, help="centre-to-centre pitch in mm")
    parser.add_argument("--diameter", type=float, default=0.40, help="electrode diameter in mm")
    parser.add_argument("--margin", type=float, default=0.35, help="crystal margin around electrodes in mm")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("czt_20_channel_layouts.png"))
    args = parser.parse_args()

    layouts = [
        Layout("Linear 1 × 20", "Quoted PRISM baseline", rectangular(1, 20, args.pitch)),
        Layout("Matrix 4 × 5", "Compact rectangular readout", rectangular(4, 5, args.pitch)),
        Layout("Staggered 4 × 5", "Hexagonal packing; smaller footprint", staggered(4, 5, args.pitch)),
        Layout("Concentric 1 + 6 + 13", "Near-circular acceptance", concentric(args.pitch)),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.7))
    for ax, layout in zip(axes.flat, layouts):
        draw_layout(ax, layout, args.diameter, args.margin)

    fig.suptitle(
        "Twenty circular anodes on a monolithic CZT sensor",
        fontsize=16, weight="bold", y=0.975,
    )
    fig.subplots_adjust(left=0.055, right=0.975, top=0.88, bottom=0.105, wspace=0.24, hspace=0.42)
    fig.text(
        0.5, 0.025,
        f"Nominal pitch {args.pitch:.2f} mm · electrode diameter {args.diameter:.2f} mm · 0.10 mm inter-electrode gap",
        ha="center", fontsize=9.5,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.show()


if __name__ == "__main__":
    main()
