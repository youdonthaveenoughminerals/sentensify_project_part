from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.express as px

from queries import (
    get_recent_a_events,
    get_system_health,
    get_recent_activity_stream,
    get_macro_impact_stats,
    get_hybrid_score_ratio
)


st.set_page_config(
    page_title="Sentencify Control Tower",
    layout="wide",
)


def _fmt_health(name: str, status: bool) -> str:
    state = "[Online]" if status else "[Offline]"
    return f"**{name}**: {state}"


def _render_health() -> None:
    health = get_system_health()
    st.sidebar.markdown("### System Health")
    st.sidebar.write(_fmt_health("MongoDB", health["mongo"]))
    st.sidebar.write(_fmt_health("Redis", health["redis"]))
    st.sidebar.write(_fmt_health("VectorDB", health["vector"]))


def _render_ticker(user_id: Optional[str]) -> None:
    st.sidebar.markdown("### Live Ticker (A)")
    events = get_recent_a_events(limit=5, user_id=user_id)
    if not events:
        st.sidebar.info("No recent A events.")
        return
    for ev in events:
        ts = ev.get("created_at")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%H:%M:%S")
        else:
            ts_str = "--:--:--"
        uid = ev.get("user_id", "unknown")
        cat = ev.get("reco_category_input", "n/a")
        latency = ev.get("latency_ms")
        latency_str = f"{latency:.0f}ms" if latency is not None else "--"
        st.sidebar.write(f"[{ts_str}] {uid} : {cat} ({latency_str})")


def _sidebar_controls() -> Optional[str]:
    st.sidebar.title("Sentencify v2.4 Control Tower")
    user_id = st.sidebar.text_input("User ID Filter (optional)")
    st.session_state["user_filter"] = user_id or None

    auto = st.sidebar.toggle("Auto-Refresh (5s)", value=False)
    if auto:
        time.sleep(5)
        st.rerun()

    _render_health()
    _render_ticker(user_id or None)
    return user_id or None


def _render_phase1_5_stats(user_id: Optional[str]):
    # st.markdown("### Phase 1.5 Hybrid Performance (Micro vs Macro)")
    
    col1, col2 = st.columns(2)
    
    # 1. Hybrid Score Ratio
    with col1:
        ratio = get_hybrid_score_ratio(user_id)
        data = {
            "Component": ["Micro (Vector)", "Macro (Context)"],
            "Contribution": [ratio["micro_ratio"], ratio["macro_ratio"]]
        }
        fig = px.pie(
            data, values="Contribution", names="Component", 
            title="Avg. Scoring Contribution",
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
    # 2. Macro Impact Stats (Alpha Distribution)
    with col2:
        stats = get_macro_impact_stats(user_id)
        buckets = stats["buckets"]
        b_data = {
            "Maturity Range": ["Low (<0.3)", "Mid (0.3-0.7)", "High (>0.7)"],
            "Count": [buckets["low"], buckets["mid"], buckets["high"]]
        }
        fig2 = px.bar(
            b_data, x="Maturity Range", y="Count",
            title=f"Document Maturity Distribution (Avg Alpha: {stats['avg_alpha']:.2f})",
            color="Count",
            color_continuous_scale="Viridis"
        )
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)


def main() -> None:
    user_id = _sidebar_controls()
    st.title("Sentencify Dashboard")
    
    # Phase 1.5 Stats Section
    _render_phase1_5_stats(user_id)
    
    st.divider()

    # Main Content: Live Activity Stream
    st.markdown("### Live Activity Stream (All Events)")
    
    stream_data = get_recent_activity_stream(limit=20, user_id=user_id)
    
    if stream_data:
        # Convert to DataFrame for better display
        df = pd.DataFrame(stream_data)
        # Format timestamp
        df["timestamp"] = df["timestamp"].apply(lambda x: x.strftime("%H:%M:%S") if isinstance(x, datetime) else str(x))
        
        st.dataframe(
            df,
            column_config={
                "timestamp": st.column_config.TextColumn("Time", width="medium"),
                "event": st.column_config.TextColumn("Event Type", width="medium"),
                "user": st.column_config.TextColumn("User ID", width="medium"),
                "detail": st.column_config.TextColumn("Detail Info", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recent activity found. Waiting for events...")

    if user_id:
        st.write(f"Filtering by User ID: `{user_id}`")


if __name__ == "__main__":
    main()