import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0  # The OKR Goal

# --- JIRA AUTH ---
try:
    JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira secrets not found. Please add them to this app's settings.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="✦")

# Debug Mode Toggle (Visible only to you for troubleshooting)
debug_mode = st.sidebar.checkbox("Show Debug Info")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;700&display=swap');
html, body, [class*="st-"] { font-family: 'Manrope', sans-serif; }
.header-box {
    background: linear-gradient(90deg, #0f2027, #203a43, #2c5364);
    padding: 20px; border-radius: 4px; color: white; margin-bottom: 25px;
}
.header-box h1 { margin: 0; font-weight: 700; color: white !important; font-size: 2.2rem; }
.header-box p { margin: 5px 0 0 0; font-weight: 300; font-size: 1.1rem; opacity: 0.9; }
div[data-testid="stMetricValue"] { font-weight: 700 !important; }
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
    <h1>✦ {TRACKED_USER}'s H1 OKR Tracker</h1>
    <p>Tracking Live Market Share for Display, Video, and Celtra (From {OKR_GO_LIVE_DATE})</p>
</div>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (Safe Version) ---
@st.cache_data(ttl=1800)
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    jql = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}"'
    
    payload = {"jql": jql, "maxResults": 1000}
    response = requests.post(url, json=payload, auth=JIRA_AUTH)
    
    if debug_mode:
        st.sidebar.write(f"JQL Sent: `{jql}`")
        st.sidebar.write(f"API Response Code: {response.status_code}")

    response.raise_for_status()
    data = response.json()
    
    raw_issues = data.get('issues', [])
    
    if debug_mode:
        st.sidebar.write(f"Raw issues found: {len(raw_issues)}")

    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    issues = []
    
    for i in raw_issues:
        # Use .get() to prevent KeyError if 'fields' is missing/redacted
        f = i.get('fields')
        if not f:
            continue
            
        fields_str = str(f).lower()
        
        ticket_type = "Other"
        if "celtra" in fields_str:
            ticket_type = "Celtra"
        elif "display" in fields_str:
            ticket_type = "Display"
        elif "video" in fields_str:
            ticket_type = "Video"
            
        assignee_dict = f.get('assignee')
        status_dict = f.get('status', {})
        
        issues.append({
            "key": i.get('key', 'N/A'),
            "type": ticket_type,
            "assignee": assignee_dict.get('displayName') if assignee_dict else "Unassigned",
            "is_closed": status_dict.get('name', '').lower() in done_statuses
        })
        
    return pd.DataFrame(issues)

# --- 2. LOGIC & CALCULATIONS ---
with st.spinner("Crunching OKR data..."):
    df = load_h1_data()

if df.empty:
    st.warning(f"⚠️ No tickets found in project **TKTS** created since **{OKR_GO_LIVE_DATE}**.")
    st.info("Check if the Project Key is correct and if tickets actually exist within that date range in Jira.")
    st.stop()

# Helper function to generate premium charts
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        color=alt.value(bar_color)
    ).properties(height=80)
    
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=3, strokeDash=[4,4]).encode(x='Goal:Q')
    return (bar + goal_line).configure_view(strokeWidth=0)

# Categories to track
categories = ["Display", "Video", "Celtra"]

# --- 3. UI DISPLAY (CARDS) ---
cols = st.columns(3)

for idx, category in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {category}")
            
            cat_df = df[df['type'] == category]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%", delta=f"{(share - TARGET_PERCENTAGE):.1f}%" if share > 0 else None)
            m2.metric("Jingyao Done", user_closed)
            m3.metric("Team Total", total_pool)
            
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)
            else:
                st.info(f"No {category} tickets found.")

st.divider()

# --- 4. DATA TABLE ---
st.markdown("### 📋 Detail Summary")
summary_data = []
for category in categories:
    cat_df = df[df['type'] == category]
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
