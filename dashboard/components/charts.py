from __future__ import annotations

from typing import Dict, List, Tuple

import plotly.graph_objects as go


def sankey_from_counts(links: Dict[str, int]) -> go.Figure:
    """
    Build a Sankey diagram for the flow:
    View (A) -> Run (B) -> Accept (C) -> Golden (H)
    """
    values = [
        links.get("A_to_B", 0),
        links.get("B_to_C", 0),
        links.get("C_to_H", 0),
    ]
    fig = go.Figure(
        go.Sankey(
            node=dict(
                pad=20,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=["View (A)", "Run (B)", "Accept (C)", "Golden (H)"],
                color=["#1f77b4", "#1f77b4", "#1f77b4", "#2ca02c"],
            ),
            link=dict(
                source=[0, 1, 2],
                target=[1, 2, 3],
                value=values,
                color=["#9ecae1", "#9ecae1", "#a1d99b"],
            ),
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    return fig


def latency_line(series: List[Tuple], title: str = "Latency (ms)") -> go.Figure:
    if not series:
        return go.Figure().update_layout(
            title="No latency data",
            margin=dict(l=10, r=10, t=30, b=10),
        )
    x, y = zip(*series)
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color="#ff7f0e"),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="ms",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
