import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.decomposition import PCA
from queries.qdrant import get_collections, get_collection_info, scroll_points

st.set_page_config(page_title="Vector DB Inspector", layout="wide")

st.title("Vector DB Inspector (Qdrant)")
st.caption("Inspect vector collections, stats, and visualize embeddings.")

# 1. Sidebar: Collection Selection
collections = get_collections()
if not collections:
    st.warning("No collections found or Qdrant is offline.")
    st.stop()

selected_col = st.sidebar.selectbox("Select Collection", collections, index=0)

# 2. Collection Info
info = get_collection_info(selected_col)
if info:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", info.get("status", "N/A"))
    c2.metric("Total Points", info.get("points_count", 0))
    c3.metric("Vectors", info.get("vectors_count", 0))
    c4.metric("Segments", info.get("segments_count", 0))
    
    with st.expander("Collection Configuration"):
        st.json(info.get("config", {}))

st.divider()

# 3. Data Preview & Visualization
tab1, tab2 = st.tabs(["Data Preview", "Embedding Space"])

# Fetch Data
points = scroll_points(selected_col, limit=300) # Limit for perf

with tab1:
    st.markdown(f"### Last {len(points)} Points")
    if points:
        # Convert points to DataFrame
        data = []
        for p in points:
            row = {"id": str(p.id)}
            row.update(p.payload or {})
            data.append(row)
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No points to display.")

with tab2:
    st.markdown("### 2D PCA Projection")
    st.caption("Visualize high-dimensional vectors in 2D space using PCA. Points closer together are semantically similar.")
    
    if not points:
        st.info("Not enough data to visualize.")
    else:
        try:
            # Extract vectors
            vectors = [p.vector for p in points if p.vector]
            
            if not vectors:
                st.warning("Points have no vectors loaded.")
            elif len(vectors) < 3:
                st.warning("Need at least 3 points for PCA.")
            else:
                # 1. Run PCA
                pca = PCA(n_components=2)
                vecs_2d = pca.fit_transform(vectors)
                explained_variance = pca.explained_variance_ratio_
                
                # 2. Prepare Plot Data & Detect Keys
                plot_data = []
                available_keys = set()
                
                for idx, p in enumerate(points):
                    if not p.vector: continue
                    
                    meta = p.payload or {}
                    row = {
                        "x": vecs_2d[idx, 0],
                        "y": vecs_2d[idx, 1],
                        "ID": str(p.id),
                        "Default": "Point" # Default color group
                    }
                    
                    # Flatten metadata for DataFrame columns
                    for k, v in meta.items():
                        if isinstance(v, (str, int, float, bool)):
                            row[k] = v
                            available_keys.add(k)
                        elif isinstance(v, list):
                            # Simplify lists for display
                            row[k] = f"List[{len(v)}]"
                    
                    plot_data.append(row)
                
                pdf = pd.DataFrame(plot_data)
                
                # 3. Controls
                c1, c2 = st.columns([1, 3])
                with c1:
                    # dynamic color options
                    color_options = ["Default"] + sorted(list(available_keys))
                    # Set reasonable defaults if they exist
                    default_idx = 0
                    if "field" in color_options: default_idx = color_options.index("field")
                    elif "category" in color_options: default_idx = color_options.index("category")
                    elif "user_id" in color_options: default_idx = color_options.index("user_id")
                    
                    color_by = st.selectbox("Color By (Metadata)", color_options, index=default_idx)
                
                with c2:
                    st.info(f"PCA Explained Variance: PC1={explained_variance[0]:.1%}, PC2={explained_variance[1]:.1%}")

                # 4. Draw Scatter Plot
                # Determine hover data (all available scalar keys)
                hover_cols = ["ID"] + sorted(list(available_keys))
                
                fig = px.scatter(
                    pdf, x="x", y="y",
                    color=color_by,
                    hover_data=hover_cols,
                    title=f"Embedding Space: {selected_col}",
                    labels={"x": f"PC1 ({explained_variance[0]:.1%})", "y": f"PC2 ({explained_variance[1]:.1%})"},
                    height=600
                )
                fig.update_traces(marker=dict(size=8, line=dict(width=1, color='DarkSlateGrey')))
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"Visualization failed: {e}")
