import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH ---
try:
    # Ensure domain is clean (removes trailing slashes and extra paths)
    RAW_DOMAIN = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    if "/rest/api" in RAW_DOMAIN:
        JIRA_DOMAIN = RAW_DOMAIN.split("/rest/api")[0]
    else:
        JIRA_DOMAIN = RAW_DOMAIN

    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.info("Ensure JIRA_DOMAIN, JIRA_USER_EMAIL, and JIRA_API_TOKEN are in your Secrets.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="✦")

# 🛠️ DEBUG SIDEBAR 
st.sidebar.header("System Debug")
debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=False)

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

# --- 1. DATA LOADING ---
@st.cache_data(ttl=600) # Caches for 10 mins
def load_h1_data(debug=False):
    # Constructing URL: https://company.atlassian.net/rest/api/3/search
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    jql = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}" ORDER BY created DESC'
    
    payload = {
        "jql": jql, 
        "maxResults": 1000,
        "fields": ["assignee", "status", "summary", "issuetype", "customfield_10010"] 
    }
    
    response = requests.post(url, json=payload, auth=JIRA_AUTH)
    
    if debug:
        st.sidebar.write("### API Connection")
        st.sidebar.write(f"**Target URL:** `{url}`")
        st.sidebar.write(f"**HTTP Status:** {response.status_code}")
        if response.status_code == 200:
            st.sidebar.success(f"Found {len(response.json().get('issues', []))} issues")
        else:
            st.sidebar.error(f"Error Body: {response.text[:200]}")

    if response.status_code in [404, 410]:
        st.error("Jira endpoint not found. Please verify your JIRA_DOMAIN secret.")
        st.stop()
        
    response.raise_for_status()
    data = response.json()
    raw_issues = data.get('issues', [])
    
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    issues = []
    
    for i in raw_issues:
        f = i.get('fields')
        if not f: continue 
            
        fields_str = str(f).lower()
        ticket_type = "Other"
        if "celtra" in fields_str: ticket_type = "Celtra"
        elif "display" in fields_str: ticket_type = "Display"
        elif "video" in fields_str: ticket_type = "Video"
            
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
with st.spinner("Syncing with Jira..."):
    df = load_h1_data(debug=debug_mode)

if df.empty:
    st.warning(f"⚠️ No tickets found in project **TKTS** since **{OKR_GO_LIVE_DATE}**.")
    st.info("If you see this but know tickets exist, check if the Project Key is exactly `TKTS` and that your API token has 'Browse Project' permissions.")
    st.stop()

# Progress Chart Function
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        color=alt.value(bar_color)
    ).properties(height=80)
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=3, strokeDash=[4,4]).encode(x='Goal:Q')
    return (bar + goal_line).configure_view(strokeWidth=0)

# --- 3. UI DISPLAY (CARDS) ---
categories = ["Display", "Video", "Celtra"]
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
            m2.metric("User Done", user_closed)
            m3.metric("Team Total", total_pool)
            
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)
            else:
                st.caption(f"No {category} tickets found in this period.")

st.divider()

# --- 4. SUMMARY TABLE ---
st.markdown("### 📋 Detailed Breakdown")
summary_list = []
for category in categories:
    cat_df = df[df['type'] == category]
    total_pool = len(cat_df)
    user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
    share = (user_closed / total_pool * 100) if total_pool > 0 else 0
    summary_list.append({
        "Category": category,
        "Total Team Tickets": total_pool,
        "Jingyao Completed": user_closed,
        "Current Share": f"{share:.1f}%",
        "Target Status": "✅ On Track" if share >= TARGET_PERCENTAGE else "⏳ Needs Attention"
    })
st.dataframe(pd.DataFrame(summary_list), use_container_width=True, hide_index=True)
