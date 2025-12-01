from __future__ import annotations

import streamlit as st

from components.charts import sankey_from_counts
from queries import get_asset_counts, get_sankey_links


def main():
    st.title("Data Flow & Assets")
    st.caption("Flow of events A→B→C→H and key asset volumes.")
    user_id = st.session_state.get("user_filter")

    links = get_sankey_links(user_id=user_id)
    st.plotly_chart(sankey_from_counts(links), use_container_width=True)

    assets = get_asset_counts(user_id=user_id)
    col1, col2 = st.columns(2)
    col1.metric("Micro Contexts (E)", f"{assets.get('micro_contexts', 0):,}")
    col2.metric("Golden Data (H, high consistency)", f"{assets.get('golden_data', 0):,}")


if __name__ == "__main__":
    main()
