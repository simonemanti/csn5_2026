#!/usr/bin/env python3
"""Make a labelled 2x2 visual comparison of the four PRISM layouts."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--width", type=int, default=1500,
                        help="width in pixels of each layout preview")
    parser.add_argument("--output", type=Path, default=root / "v0_Confronto.png",
                        help="comparison image")
    args = parser.parse_args()
    if args.width < 600:
        parser.error("preview width must be at least 600 pixels")
    height = round(args.width * 70 / 224.2)
    margin, header = round(args.width * .025), round(args.width * .045)
    cell_height = height + header
    canvas = Image.new("RGB", (2 * args.width + 3 * margin,
                              2 * cell_height + 3 * margin), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("DejaVuSans.ttf", round(args.width * .021))
    labels = ["v1 | Pentagonale", "v2 | Lineare",
              "v3 | Due righe", "v4 | Arco"]
    for index, label in enumerate(labels):
        x = margin + index % 2 * (args.width + margin)
        y = margin + index // 2 * (cell_height + margin)
        draw.text((x, y), label, font=font, fill="#333333")
        with Image.open(root / f"v{index + 1}_Focusing_Area.png") as source:
            preview = source.convert("RGBA").resize(
                (args.width, height), Image.Resampling.LANCZOS)
            canvas.paste(preview, (x, y + header), preview)
    canvas.save(args.output)
    print(f"Saved {args.output} ({canvas.width} x {canvas.height})")


if __name__ == "__main__":
    main()
