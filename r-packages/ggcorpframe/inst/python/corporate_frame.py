#!/usr/bin/env python3
"""Corporate frame — wraps a captured image with a matplotlib title header.

Usage:
    python corporate_frame.py \\
        --input chart.png --output framed.png \\
        --title "Q4 Results" --subtitle "Revenue by Region"

Dummy implementation using plain matplotlib.
Replace with actual corporate design package.
"""

from __future__ import annotations

import argparse
import io

import matplotlib.pyplot as plt

plt.switch_backend("agg")


def apply_frame(
    png_bytes: bytes,
    title: str = "",
    subtitle: str = "",
    footnotes: str = "",
    sources: str = "",
    dpi: int = 300,
) -> bytes:
    """Wrap a PNG image with a title header using matplotlib."""
    img = plt.imread(io.BytesIO(png_bytes))
    img_h, img_w = img.shape[:2]

    # Header: title + underline + subtitle
    header_h = int(img_h * 0.12) if (title or subtitle) else 0
    # Footer: footnotes + sources
    footer_h = int(img_h * 0.08) if (footnotes or sources) else 0
    total_h = img_h + header_h + footer_h

    fig = plt.figure(
        figsize=(img_w / dpi, total_h / dpi), dpi=dpi, facecolor="white",
    )

    # --- header ---
    if header_h > 0:
        ax = fig.add_axes([0, 1 - header_h / total_h, 1, header_h / total_h])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_facecolor("white")
        ax.axis("off")

        if title:
            ax.text(
                0.03, 0.65, title,
                fontsize=11, fontweight="bold", color="#1a1a2e",
                va="center", transform=ax.transAxes,
            )
            # Underline
            ax.plot(
                [0.03, 0.35], [0.42, 0.42],
                color="#e94560", linewidth=2,
                transform=ax.transAxes, clip_on=False,
            )
        if subtitle:
            ax.text(
                0.03, 0.15, subtitle,
                fontsize=8, color="#555555", style="italic",
                va="center", transform=ax.transAxes,
            )

    # --- image ---
    ax_img = fig.add_axes([0, footer_h / total_h, 1, img_h / total_h])
    ax_img.imshow(img)
    ax_img.axis("off")

    # --- footer ---
    if footer_h > 0:
        ax = fig.add_axes([0, 0, 1, footer_h / total_h])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_facecolor("white")
        ax.axis("off")
        ax.plot(
            [0.03, 0.97], [0.85, 0.85],
            color="#dddddd", linewidth=0.5,
            transform=ax.transAxes, clip_on=False,
        )
        if footnotes:
            ax.text(
                0.03, 0.4, footnotes,
                fontsize=6, color="#888888",
                va="center", transform=ax.transAxes,
            )
        if sources:
            ax.text(
                0.97, 0.4, sources,
                fontsize=6, color="#888888",
                va="center", ha="right", transform=ax.transAxes,
            )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def main():
    parser = argparse.ArgumentParser(description="Apply corporate frame to PNG")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--footnotes", default="")
    parser.add_argument("--sources", default="")
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    with open(args.input, "rb") as f:
        png_bytes = f.read()

    framed = apply_frame(
        png_bytes, title=args.title, subtitle=args.subtitle,
        footnotes=args.footnotes, sources=args.sources, dpi=args.dpi,
    )

    with open(args.output, "wb") as f:
        f.write(framed)


if __name__ == "__main__":
    main()
