import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth
from datetime import datetime

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-03-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0  # The OKR Goal

# --- JIRA AUTH (Uses your existing secrets) ---
try:
    JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira secrets not found. Please add them to this app's settings.")
    st.stop()

# --- PAGE CONFIG & CUSTOM CSS (Premium UI) ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="🎯")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;700&display=swap');

html, body, [class*="st-"] {
    font-family: 'Manrope', sans-serif;
}

/* Custom Header */
.header-box {
    background: linear-gradient(90deg, #0f2027, #203a43, #2c5364);
    padding: 20px;
    border-radius: 8px;
    color: white;
    margin-bottom: 25px;
}
.header-box h1 { margin: 0; font-weight: 700; color: white !important; font-size: 2.2rem; }
.header-box p { margin: 5px 0 0 0; font-weight: 300; font-size: 1.1rem; opacity: 0.9; }

/* Metric Styling */
div[data-testid="stMetricValue"] {
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

# --- ALTAIR THEME ---
def set_altair_theme():
    font = "Manrope"
    alt.themes.register("my_theme", lambda: {
        "config": {
            "font": font,
            "title": {"font": font, "fontSize": 14, "fontWeight": 600},
            "axis": {"labelFont": font, "titleFont": font, "grid": False},
        }
    })
    alt.themes.enable("my_theme")
set_altair_theme()


# --- HEADER ---
st.markdown(f"""
<div class="header-box">
    <h1>🎯 {TRACKED_USER}'s H1 OKR Tracker</h1>
    <p>Tracking Live Market Share for Display, Video, and Celtra (From {OKR_GO_LIVE_DATE})</p>
</div>
""", unsafe_allow_html=True)


# --- 1. DATA LOADING ---
@st.cache_data(ttl=1800) # Caches for 30 mins
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    jql = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}"'
    fields = ["key", "issuetype", "assignee", "status", "resolutiondate"]
    
    payload = {"jql": jql, "fields": fields, "maxResults": 1000}
    response = requests.post(url, json=payload, auth=JIRA_AUTH)
    response.raise_for_status()
    
    issues = []
    for i in response.json().get('issues', []):
        f = i['fields']
        issues.append({
            "key": i['key'],
            "type": f['issuetype']['name'],
            "assignee": f['assignee']['displayName'] if f['assignee'] else "Unassigned",
            "is_closed": f['status']['name'].lower() in ["closed", "done", "resolved"]
        })
    return pd.DataFrame(issues)

# --- 2. LOGIC & CALCULATIONS ---
with st.spinner("Crunching OKR data..."):
    df = load_h1_data()

if df.empty:
    st.warning("No tickets found for the current OKR period.")
    st.stop()

# Helper function to generate premium charts
def build_progress_chart(share_val, title):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' # Green if hit, Yellow if under
    
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    
    # The actual progress bar
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title="Current Market Share %"),
        color=alt.value(bar_color),
        tooltip=[alt.Tooltip('Share:Q', format='.1f', title='Current %')]
    ).properties(height=80)
    
    # The target line
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=3, strokeDash=[4,4]).encode(
        x='Goal:Q',
        tooltip=[alt.Tooltip('Goal:Q', title='OKR Target %')]
    )
    
    return (bar + goal_line).configure_view(strokeWidth=0)

# Categories to track
categories = ["Display", "Video", "Celtra"]

# --- 3. UI DISPLAY (CARDS) ---
cols = st.columns(3)

for idx, category in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"📊 {category}")
            
            # Filter Data
            cat_df = df[df['type'].str.contains(category, case=False)]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            
            # Calculate Percentage
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            # Metrics Layout
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%", delta=f"{(share - TARGET_PERCENTAGE):.1f}%" if share > 0 else None)
            m2.metric("Jingyao Done", user_closed)
            m3.metric("Team Total", total_pool)
            
            # Chart
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share, category), use_container_width=True)
            else:
                st.info(f"No {category} tickets raised yet.")

st.divider()

# --- 4. DATA TABLE ---
st.markdown("### 📋 Detail Summary")
st.caption("A quick look at the raw numbers powering the charts above.")

summary_data = []
for category in categories:
    cat_df = df[df['type'].str.contains(category, case=False)]
    total_pool = len(cat_df)
    user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
    share = (user_closed / total_pool * 100) if total_pool > 0 else 0
    
    summary_data.append({
        "Category": category,
        "Total Team Tickets": total_pool,
        "Jingyao Completed": user_closed,
        "Current OKR Share": f"{share:.1f}%",
        "Target Status": "✅ On Track" if share >= TARGET_PERCENTAGE else "⏳ Needs Attention"
    })

st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
