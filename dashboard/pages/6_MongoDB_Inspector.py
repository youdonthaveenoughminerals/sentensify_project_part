import streamlit as st
import pandas as pd
import json
from queries.mongo import get_collection_names, find_documents

st.set_page_config(page_title="MongoDB Inspector", layout="wide")

st.title("MongoDB Inspector")
st.caption("Directly inspect raw documents in MongoDB collections.")

# 1. Collection Selection
collections = get_collection_names()
if not collections:
    st.error("No collections found or MongoDB is offline.")
    st.stop()

selected_col = st.sidebar.selectbox("Select Collection", collections, index=0)

# 2. Filter
with st.sidebar.expander("Filter Query (JSON)"):
    filter_str = st.text_area("Query", value="{}", height=100, help='e.g., {"user_id": "..."}')
    try:
        filter_query = json.loads(filter_str)
    except json.JSONDecodeError:
        st.error("Invalid JSON query.")
        filter_query = {}

limit = st.sidebar.number_input("Limit", min_value=1, max_value=1000, value=50)

# 3. Fetch Data
docs = find_documents(selected_col, filter_query, limit=limit)

st.markdown(f"### {selected_col} ({len(docs)} documents)")

if docs:
    # Convert to DataFrame
    # Convert all values to string to avoid Arrow serialization errors with complex nested objects
    df_display = pd.DataFrame(docs).astype(str)
    
    # Move _id and created_at to front if exist
    cols = df_display.columns.tolist()
    if "created_at" in cols:
        cols.insert(0, cols.pop(cols.index("created_at")))
    if "_id" in cols:
        cols.insert(0, cols.pop(cols.index("_id")))
    
    st.dataframe(df_display[cols], use_container_width=True)
    
    with st.expander("View Raw JSON (Top 5)"):
        st.json(docs[:5])
else:
    st.info("No documents found matching the query.")
