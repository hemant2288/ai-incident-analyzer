"""Streamlit analytics dashboard for AI Incident Root Cause Analyzer."""

from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from app.config import settings
from app.services.incident_store import IncidentStore

st.set_page_config(
    page_title="SRE Incident Analytics",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOT_LAYOUT = dict(
    plot_bgcolor="#0E1117",
    paper_bgcolor="#0E1117",
    font_color="#FAFAFA",
)


@st.cache_resource
def get_store() -> IncidentStore:
    return IncidentStore()


def load_data() -> tuple[IncidentStore, dict, list]:
    store = get_store()
    try:
        analytics = store.get_analytics()
        incidents = store.list_all(limit=200)
    except Exception as exc:
        st.error(f"Failed to load incident data: {exc}")
        st.stop()
    return store, analytics, incidents


store, analytics, incidents = load_data()

st.title("⚙️ AI Incident Root Cause Analyzer — Enterprise Dashboard")
st.caption(
    "Incident intelligence, financial impact tracking, and AI diagnosis metrics"
)

st.sidebar.header("Configuration")
st.sidebar.markdown(f"**Incident DB:** `{settings.incident_history_db_path}`")
st.sidebar.markdown(f"**Chroma path:** `{settings.chroma_db_path}`")
st.sidebar.markdown(
    f"**LLM:** {'Configured' if settings.openai_api_key else 'Offline RCA mode'}"
)

if not incidents:
    st.info(
        "No incidents recorded yet. Start the API server and run:\n\n"
        "```bash\n"
        "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n"
        "python simulate_advanced_alert.py\n"
        "```"
    )
    st.stop()

df_incidents = pd.DataFrame(incidents)
df_incidents["created_at"] = pd.to_datetime(df_incidents["created_at"], errors="coerce")

st.sidebar.header("Filters")
services = sorted(df_incidents["service_name"].dropna().unique().tolist())
selected_service = st.sidebar.selectbox("Service", ["All"] + services)

if selected_service != "All":
    df_view = df_incidents[df_incidents["service_name"] == selected_service].copy()
    filtered_analytics = {
        "total_incidents": len(df_view),
        "total_estimated_loss_usd": round(
            float(df_view["estimated_loss_usd"].sum()), 2
        ),
        "total_revenue_saved_usd": round(
            float(
                (df_view["estimated_loss_usd"] * (df_view["ai_accuracy_score"] / 100)).sum()
            ),
            2,
        ),
        "average_ai_accuracy": round(float(df_view["ai_accuracy_score"].mean()), 1)
        if len(df_view)
        else 0.0,
        "by_service": [
            {
                "service_name": selected_service,
                "incident_count": len(df_view),
                "total_loss_usd": round(float(df_view["estimated_loss_usd"].sum()), 2),
            }
        ],
    }
else:
    df_view = df_incidents
    filtered_analytics = analytics

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Incidents", filtered_analytics["total_incidents"])
col2.metric(
    "Total Est. Financial Loss",
    f"${filtered_analytics['total_estimated_loss_usd']:,.0f}",
)
col3.metric(
    "Revenue Protected (AI-Assisted)",
    f"${filtered_analytics['total_revenue_saved_usd']:,.0f}",
)
col4.metric(
    "Avg AI Diagnosis Accuracy",
    f"{filtered_analytics['average_ai_accuracy']:.1f}%",
)

st.divider()

left, right = st.columns(2)
by_service = filtered_analytics.get("by_service", [])

with left:
    st.subheader("Financial Cost Impact by Service")
    if by_service:
        df_service = pd.DataFrame(by_service)
        fig_bar = px.bar(
            df_service,
            x="service_name",
            y="total_loss_usd",
            color="service_name",
            title="Estimated Loss (USD) per Service",
            labels={"service_name": "Service", "total_loss_usd": "Loss (USD)"},
        )
        fig_bar.update_layout(showlegend=False, **PLOT_LAYOUT)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.write("No service breakdown available.")

with right:
    st.subheader("Incident Volume by Service")
    if by_service:
        df_pie = pd.DataFrame(by_service)
        fig_pie = px.pie(
            df_pie,
            names="service_name",
            values="incident_count",
            title="Incidents by Service",
            hole=0.4,
        )
        fig_pie.update_layout(**PLOT_LAYOUT)
        st.plotly_chart(fig_pie, use_container_width=True)

st.subheader("Downtime vs Financial Loss Trend")
if not df_view.empty:
    df_sorted = df_view.sort_values("created_at")
    fig_scatter = px.scatter(
        df_sorted,
        x="downtime_minutes",
        y="estimated_loss_usd",
        color="service_name",
        size="ai_accuracy_score",
        hover_data=["incident_id", "severity", "culprit_commit"],
        title="Downtime Duration vs Estimated Financial Loss",
        labels={
            "downtime_minutes": "Downtime (minutes)",
            "estimated_loss_usd": "Estimated Loss (USD)",
        },
    )
    fig_scatter.update_layout(**PLOT_LAYOUT)
    st.plotly_chart(fig_scatter, use_container_width=True)

st.subheader("AI Accuracy Score Over Time")
if not df_view.empty and "created_at" in df_view.columns:
    fig_line = px.line(
        df_view.sort_values("created_at"),
        x="created_at",
        y="ai_accuracy_score",
        color="service_name",
        markers=True,
        title="AI Diagnosis Accuracy by Incident",
        labels={"ai_accuracy_score": "Accuracy (%)", "created_at": "Date"},
    )
    fig_line.update_layout(**PLOT_LAYOUT)
    st.plotly_chart(fig_line, use_container_width=True)

st.divider()
st.subheader("Incident History")

display_cols = [
    "incident_id",
    "title",
    "service_name",
    "severity",
    "downtime_minutes",
    "estimated_loss_usd",
    "ai_accuracy_score",
    "culprit_commit",
    "created_at",
]
st.dataframe(
    df_view[display_cols].rename(
        columns={
            "incident_id": "Incident ID",
            "title": "Title",
            "service_name": "Service",
            "severity": "Severity",
            "downtime_minutes": "Downtime (min)",
            "estimated_loss_usd": "Est. Loss ($)",
            "ai_accuracy_score": "AI Accuracy (%)",
            "culprit_commit": "Culprit Commit",
            "created_at": "Recorded At",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("View Latest Full AI Report"):
    latest_row = df_view.sort_values("created_at", ascending=False).iloc[0]
    st.markdown(f"**{latest_row['incident_id']}** — {latest_row['title']}")
    st.markdown(latest_row["report_markdown"])

st.sidebar.divider()
st.sidebar.markdown(
    f"**Last refreshed:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
)
if st.sidebar.button("Refresh Data"):
    st.cache_resource.clear()
    st.rerun()
