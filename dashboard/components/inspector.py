import streamlit as st
import pandas as pd
import plotly.express as px
from queries.redis import get_redis_info, get_cache_stats, get_key_samples
from queries.mongo import (
    get_total_counts, 
    get_recent_a_events, 
    get_system_health, 
    get_macro_queue_length,
    get_k_doc_count,
    get_recent_error_logs,
    get_recent_docs,
    get_recent_upserts,
    COLL_A, COLL_B, COLL_E, COLL_F, COLL_I, COLL_K
)

def render_inspector(selected_node: str, user_id: str = None):
    """
    Renders detailed inspection view for the selected system component.
    """
    if not selected_node:
        st.info("👆 Click a node in the System Map to inspect details.")
        return

    st.markdown(f"### 🔍 Inspector: **{selected_node}**")

    # Dispatch based on Node ID (from topology_graph.py)
    if selected_node == "Redis":
        _render_redis_inspector()
    elif selected_node == "Mongo":
        _render_mongo_inspector(user_id)
    elif selected_node == "API":
        _render_api_inspector(user_id)
    elif selected_node == "Worker":
        _render_worker_inspector(user_id)
    elif selected_node == "VectorDB":
        _render_vectordb_inspector(user_id)
    elif selected_node == "Emb Model":
        _render_emb_model_inspector(user_id)
    elif selected_node == "GenAI (Run)":
        _render_genai_run_inspector(user_id)
    elif selected_node == "GenAI (Macro)":
        _render_genai_macro_inspector(user_id)
    else:
        st.write(f"No detailed inspection available for {selected_node}.")


def _render_recent_logs(data: list, title: str = "Recent Logs"):
    """Helper to render a log table."""
    st.divider()
    st.caption(title)
    if data:
        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent logs found.")


def _render_redis_inspector():
    col1, col2 = st.columns(2)
    
    # 1. Redis Info
    info = get_redis_info()
    with col1:
        st.caption("Instance Info")
        if "error" in info:
            st.error(f"Redis Error: {info['error']}")
        else:
            st.metric("Memory Used", info.get("used_memory_human"))
            st.metric("Total Keys", info.get("total_keys"))
            st.metric("Connected Clients", info.get("connected_clients"))

    # 2. Cache Stats & Pie Chart
    # User requested: Cached LLM Response (llm:para:*) and Document Context Cache (macro_context:*)
    patterns = ["llm:para:*", "macro_context:*"]
    stats = get_cache_stats(patterns)
    
    with col2:
        st.caption("Cache Distribution")
        if "error" in stats:
            st.error(stats["error"])
        else:
            data = {
                "Type": ["LLM Response (Micro)", "Context Cache (Macro)"],
                "Count": [stats.get("llm:para:*", 0), stats.get("macro_context:*", 0)]
            }
            df = pd.DataFrame(data)
            if df["Count"].sum() > 0:
                fig = px.pie(df, values="Count", names="Type", hole=0.4, height=200)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No keys found for monitored patterns.")

    # 3. Key Samples (serving as "Logs" for Redis)
    st.divider()
    st.caption("Recent Cache Entries (Sorted by Recency)")
    tab1, tab2 = st.tabs(["Micro (LLM Response)", "Macro (Context Cache)"])
    
    with tab1:
        # Micro Cache Pattern: llm:para:*
        samples = get_key_samples("llm:para:*", limit=5)
        if samples and "error" not in samples[0]:
            df = pd.DataFrame(samples)
            if not df.empty:
                st.dataframe(
                    df[["key", "idle", "ttl", "value"]].rename(columns={"idle": "Idle (s)"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No micro cache keys found.")
        else:
            st.info("No micro cache keys found or error.")

    with tab2:
        # Macro Cache Pattern: macro_context:* (Corrected from doc:*:macro)
        samples = get_key_samples("macro_context:*", limit=5)
        if samples and "error" not in samples[0]:
            df = pd.DataFrame(samples)
            if not df.empty:
                st.dataframe(
                    df[["key", "idle", "ttl", "value"]].rename(columns={"idle": "Idle (s)"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No macro cache keys found.")
        else:
            st.info("No macro cache keys found or error.")


def _render_mongo_inspector(user_id: str):
    counts = get_total_counts(user_id)
    k_count = get_k_doc_count(user_id)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Logs (A)", counts.get("A", 0))
    c2.metric("Total Runs (B)", counts.get("B", 0))
    c3.metric("Golden Data (H)", counts.get("H", 0))
    
    st.divider()
    st.caption("Collection Stats (v2.4 Schema)")
    df = pd.DataFrame([
        {"Collection": "Full Docs (K)", "Count": k_count},
        {"Collection": "Profiles (G)", "Count": counts.get("G", 0)},
        {"Collection": "Micro Context (E)", "Count": counts.get("E", 0)},
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Recent System Logs (using COLL_I as a proxy for general system activity stored in Mongo)
    logs = get_recent_docs(COLL_I, limit=5, user_id=user_id)
    _render_recent_logs(logs, "Recent System Logs (COLL_I)")


def _render_api_inspector(user_id: str):
    health = get_system_health()
    
    st.caption("System Health")
    c1, c2, c3 = st.columns(3)
    c1.metric("MongoDB", "Online" if health["mongo"] else "Offline")
    c2.metric("Redis", "Online" if health["redis"] else "Offline")
    c3.metric("VectorDB", "Online" if health["vector"] else "Offline")
    
    st.divider()
    st.caption("Recent API Request Logs (COLL_A)")
    # Using COLL_A as the main API interaction log
    logs = get_recent_a_events(limit=5, user_id=user_id)
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.info("No recent API logs.")
        
    st.divider()
    st.caption("Recent Errors (>2000ms latency)")
    errors = get_recent_error_logs(limit=5, user_id=user_id)
    if errors:
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
    else:
        st.success("✅ No critical anomalies found in recent logs.")


def _render_worker_inspector(user_id: str):
    queue_len = get_macro_queue_length()
    st.metric("Macro Queue (Diff >= 0.1)", queue_len)
    st.progress(min(queue_len / 100.0, 1.0), text="Queue Load")
    
    # Worker logs -> Macro Cache Updates (COLL_F)
    logs = get_recent_docs(COLL_F, limit=5, user_id=user_id)
    _render_recent_logs(logs, "Recent Worker Activity (Macro Cache Updates)")


def _render_vectordb_inspector(user_id: str):
    # Metrics
    counts = get_total_counts(user_id)
    
    st.caption("Vector Database Metrics")
    c1, c2 = st.columns(2)
    c1.metric("Total Context Blocks", counts.get("E", 0))
    # We could show 'New blocks in last hour' if we did more calculation, 
    # but for now Total is a good baseline.
    
    # Logs (Upserts)
    upserts = get_recent_upserts(limit=10, user_id=user_id)
    _render_recent_logs(upserts, "Recently Upserted Context Blocks (COLL_E)")


def _render_emb_model_inspector(user_id: str):
    st.info("Embedding Model is stateless. Monitoring API interactions involving embeddings.")
    # Show logs from COLL_A/COLL_I where embedding might be involved
    # For now, generic API logs are the closest proxy
    logs = get_recent_docs(COLL_I, limit=5, user_id=user_id)
    _render_recent_logs(logs, "Recent Embedding API Activity")


def _render_genai_run_inspector(user_id: str):
    st.caption("GenAI (Run) - Paraphrasing Service")
    # Metrics: Recent Runs
    runs = get_recent_docs(COLL_B, limit=5, user_id=user_id)
    _render_recent_logs(runs, "Recent Generation Requests (COLL_B)")


def _render_genai_macro_inspector(user_id: str):
    st.caption("GenAI (Macro) - Context Analysis")
    # Metrics: Macro updates
    logs = get_recent_docs(COLL_F, limit=5, user_id=user_id)
    _render_recent_logs(logs, "Recent Macro Analysis Updates (COLL_F)")