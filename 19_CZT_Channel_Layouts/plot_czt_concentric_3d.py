#!/usr/bin/env python3
"""Visualize a focused 1+6+13 CZT detector array on a spherical cap."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def unit_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return two orthonormal vectors perpendicular to *normal*."""
    normal = normal / np.linalg.norm(normal)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(normal, helper)) > 0.9:
        helper = np.array([1.0, 0.0, 0.0])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return u, v


def cylinder_mesh(
    centre: np.ndarray,
    normal: np.ndarray,
    radius: float,
    thickness: float,
    segments: int = 32,
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    """Create faces and end caps for a cylinder oriented along *normal*."""
    normal = normal / np.linalg.norm(normal)
    u, v = unit_basis(normal)
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    front_centre = centre - normal * thickness / 2
    back_centre = centre + normal * thickness / 2
    ring_front = np.array([front_centre + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles])
    ring_back = np.array([back_centre + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles])
    sides = [
        np.array([ring_front[i], ring_front[(i + 1) % segments], ring_back[(i + 1) % segments], ring_back[i]])
        for i in range(segments)
    ]
    return sides, ring_front, ring_back


def detector_positions(cap_radius: float) -> list[tuple[int, int, np.ndarray]]:
    """Return channel, ring and centre for a 1+6+13 spherical-cap layout."""
    positions: list[tuple[int, int, np.ndarray]] = [(1, 0, np.array([0.0, 0.0, cap_radius]))]
    channel = 2
    for ring, (count, polar_deg, phase_deg) in enumerate(((6, 16.0, 0.0), (13, 31.0, 360 / 26)), start=1):
        polar = np.deg2rad(polar_deg)
        phase = np.deg2rad(phase_deg)
        for index in range(count):
            azimuth = phase + 2 * np.pi * index / count
            centre = cap_radius * np.array(
                [np.sin(polar) * np.cos(azimuth), np.sin(polar) * np.sin(azimuth), np.cos(polar)]
            )
            positions.append((channel, ring, centre))
            channel += 1
    return positions


def set_equal_limits(ax, extent: float, zmax: float) -> None:
    ax.set_xlim(-extent, extent)
    ax.set_ylim(-extent, extent)
    ax.set_zlim(0, zmax)
    ax.set_box_aspect((2 * extent, 2 * extent, zmax))


def draw_array(ax, positions, module_diameter: float, thickness: float, cap_radius: float, view: str) -> None:
    colours = {0: "#f5c242", 1: "#e89c24", 2: "#c95f36"}

    # Transparent reference cap.
    polar = np.linspace(0, np.deg2rad(35), 28)
    azimuth = np.linspace(0, 2 * np.pi, 60)
    pp, aa = np.meshgrid(polar, azimuth)
    xx = cap_radius * np.sin(pp) * np.cos(aa)
    yy = cap_radius * np.sin(pp) * np.sin(aa)
    zz = cap_radius * np.cos(pp)
    ax.plot_surface(xx, yy, zz, color="#b9cad8", alpha=0.10, linewidth=0, shade=False)

    for channel, ring, centre in positions:
        inward = -centre / np.linalg.norm(centre)
        sides, front, back = cylinder_mesh(centre, inward, module_diameter / 2, thickness)
        ax.add_collection3d(Poly3DCollection(sides, facecolor=colours[ring], edgecolor="#633b22", linewidth=0.25, alpha=0.95))
        ax.add_collection3d(Poly3DCollection([front], facecolor=colours[ring], edgecolor="#4b2a17", linewidth=0.8))
        ax.add_collection3d(Poly3DCollection([back], facecolor="#6f4227", edgecolor="#4b2a17", linewidth=0.5))

        # Selected sight lines make the focusing concept legible without clutter.
        if channel in {1, 2, 5, 8, 12, 16, 20}:
            front_centre = centre + inward * thickness / 2
            ax.plot([0, front_centre[0]], [0, front_centre[1]], [0, front_centre[2]], color="#607d8b", alpha=0.28, lw=0.8)

        label_pos = centre - inward * (thickness / 2 + 0.2)
        ax.text(*label_pos, str(channel), ha="center", va="center", fontsize=6.2, color="#24150c")

    ax.scatter([0], [0], [0], s=70, color="#2878b5", edgecolor="white", linewidth=0.8, depthshade=False)
    ax.text(0, 0, -1.7, "sample", ha="center", va="top", color="#174f78", fontsize=8)

    extent = cap_radius * np.sin(np.deg2rad(36)) + module_diameter
    set_equal_limits(ax, extent, cap_radius + thickness + 2)
    ax.set_xlabel("x [mm]", labelpad=2)
    ax.set_ylabel("y [mm]", labelpad=2)
    ax.set_zlabel("z [mm]", labelpad=2)
    ax.grid(False)
    ax.xaxis.pane.set_alpha(0.02)
    ax.yaxis.pane.set_alpha(0.02)
    ax.zaxis.pane.set_alpha(0.02)
    if view == "perspective":
        ax.view_init(elev=24, azim=-55)
        ax.set_title("Perspective view", weight="bold", y=0.91)
    else:
        ax.view_init(elev=90, azim=-90)
        ax.set_title("View from the sample", weight="bold", y=0.91)
        ax.set_axis_off()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot a focused 20-element CZT spherical-cap array.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--cap-radius", type=float, default=30.0, help="sample-to-module-centre radius in mm")
    parser.add_argument("--diameter", type=float, default=4.0, help="diameter of each circular CZT module in mm")
    parser.add_argument("--thickness", type=float, default=2.0, help="CZT module thickness in mm")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("czt_concentric_spherical_cap_3d.png"))
    args = parser.parse_args()

    positions = detector_positions(args.cap_radius)
    fig = plt.figure(figsize=(13.2, 7.2))
    ax1 = fig.add_subplot(121, projection="3d")
    ax2 = fig.add_subplot(122, projection="3d")
    draw_array(ax1, positions, args.diameter, args.thickness, args.cap_radius, "perspective")
    draw_array(ax2, positions, args.diameter, args.thickness, args.cap_radius, "front")

    fig.suptitle("Focused 20-element CZT spherical-cap array (1 + 6 + 13)", fontsize=16, weight="bold", y=0.985)
    fig.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#f5c242", label="central element", markersize=9),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#e89c24", label="inner ring: 6", markersize=9),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#c95f36", label="outer ring: 13", markersize=9),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#2878b5", label="sample / common focus", markersize=8),
        ],
        loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.015), fontsize=9,
    )
    fig.text(
        0.5, 0.005,
        f"Spherical radius {args.cap_radius:g} mm · module Ø {args.diameter:g} mm × {args.thickness:g} mm · polar rings 0°, 16°, 31°",
        ha="center", fontsize=9,
    )
    fig.subplots_adjust(left=0.01, right=0.98, top=0.88, bottom=0.10, wspace=0.02)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.show()


if __name__ == "__main__":
    main()
