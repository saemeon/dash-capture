"""Demo: my_brand_example in action.

Run from the mpl-brandpacker directory:
    cd packages/mpl-brandpacker
    uv run python examples/demo.py
"""

import sys
from pathlib import Path

# Make my_brand_example importable from this directory
sys.path.insert(0, str(Path(__file__).parent))

import my_brand_example
import my_brand_example.pyplot as plt
from my_brand_example.legend import legend_below

# --- Standard plot ---
fig, ax = plt.subplots(figsize=my_brand_example.Sizes.half)

ax.plot([1, 2, 3, 4], [2, 5, 3, 8], color=my_brand_example.Colors.primary, linewidth=2, label="Revenue")
ax.plot([1, 2, 3, 4], [1, 3, 6, 4], color=my_brand_example.Colors.accent, linewidth=2, label="Target")

fig.set_title("Quarterly Revenue")
fig.set_subtitle("All regions, 2026")
fig.set_sources("Internal ERP")
ax.set_xlabel("Quarter")
ax.set_ylabel("CHF m")
legend_below(ax)

plt.savefig("demo_output.png", dpi=150, bbox_inches="tight")
print("Saved: demo_output.png")

# --- Scaled for presentation ---
with my_brand_example.FontSizes.scaled("presentation"):
    fig2, ax2 = plt.subplots(figsize=my_brand_example.Sizes.presentation)
    ax2.plot([1, 2, 3, 4], [2, 5, 3, 8], color=my_brand_example.Colors.primary, linewidth=3)
    fig2.set_title("Quarterly Revenue (Presentation)")
    ax2.set_xlabel("Quarter")
    plt.savefig("demo_presentation.png", dpi=150, bbox_inches="tight")
    print("Saved: demo_presentation.png")

plt.show()
