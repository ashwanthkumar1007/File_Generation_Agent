"""Chart rendering using matplotlib — returns base64 encoded PNGs."""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt

from pdf_agent.schemas.document_spec import ChartContent


def generate_chart(chart_spec: ChartContent) -> str:
    """Render a chart from *chart_spec* and return a base64-encoded PNG string.

    Supported chart types: bar, line, pie, scatter.
    """
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)

    chart_type = chart_spec.chart_type

    if chart_type == "bar":
        ax.bar(chart_spec.labels, chart_spec.values, color="#4A90D9")
    elif chart_type == "line":
        ax.plot(
            chart_spec.labels,
            chart_spec.values,
            marker="o",
            linewidth=2,
            color="#4A90D9",
        )
    elif chart_type == "pie":
        ax.pie(
            chart_spec.values,
            labels=chart_spec.labels,
            autopct="%1.1f%%",
            startangle=140,
        )
    elif chart_type == "scatter":
        x_range = list(range(len(chart_spec.labels)))
        ax.scatter(x_range, chart_spec.values, color="#4A90D9")
        ax.set_xticks(x_range)
        ax.set_xticklabels(chart_spec.labels, rotation=45, ha="right")
    else:
        ax.text(
            0.5,
            0.5,
            f"Unsupported chart type: {chart_type}",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    if chart_spec.title:
        ax.set_title(chart_spec.title, fontsize=12, fontweight="bold")

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode("ascii")
