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
    JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira secrets not found. Please add them to this app's settings.")
    st.stop()

# --- PAGE CONFIG & UI STYLE ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="✦")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;700&display=swap');
html, body, [class*="st-"] { font-family: 'Manrope', sans-serif; }
.header-box {
    background: linear-gradient(90deg, #0f2027, #203a43, #2c5364);
    padding: 20px; border-radius: 4px; color: white; margin-bottom: 25px;
}
.header-box h1 { margin: 0; font-weight: 700; color: white !important; }
div[data-testid="stMetricValue"] { font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(f"""
<div class="header-box">
    <h1>✦ {TRACKED_USER}'s H1 OKR Tracker</h1>
    <p>Tracking Live Market Share for Display, Video, and Celtra (From {OKR_GO_LIVE_DATE})</p>
</div>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (Using your working method + Pagination) ---
@st.cache_data(ttl=1800)
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    
    # Your exact JQL string
    jql = f"""
    project = TKTS 
    AND status IN (Closed, "In Progress", Open, Reopened, Resolved, "Waiting for customer", "Waiting for support", "Campaign/request closed")
    AND created >= "{OKR_GO_LIVE_DATE}"
    ORDER BY created DESC
    """
    
    fields = ["key", "issuetype", "assignee", "status"]
    issues = []
    start_at = 0
    max_results = 100 

    # Loop to ensure we get ALL tickets (this finds those missing Celtra tickets)
    while True:
        payload = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
            "startAt": start_at
        }
        # Using the json=payload method that worked for you
        response = requests.post(url, json=payload, auth=JIRA_AUTH, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        batch = data.get('issues', [])
        issues.extend(batch)
        
        if len(batch) < max_results or start_at > 2000: # Safety break
            break
        start_at += max_results

    # Your custom closed statuses
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    
    results = []
    for i in issues:
        f = i['fields']
        results.append({
            "key": i['key'],
            "type": f['issuetype']['name'],
            "assignee": f['assignee']['displayName'] if f['assignee'] else "Unassigned",
            "is_closed": f['status']['name'].lower() in done_statuses
        })
    return pd.DataFrame(results)

# --- 2. CALCULATIONS ---
with st.spinner("✦ Accessing Jira..."):
    df = load_h1_data()

if df.empty:
    st.warning("No tickets found for the current OKR period.")
    st.stop()

# Progress Chart Builder (Cleaned up as requested)
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None), # Removed title
        color=alt.value(bar_color),
        tooltip=[alt.Tooltip('Share:Q', format='.1f', title='Current %')]
    ).properties(height=80)
    
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=3, strokeDash=[4,4]).encode(x='Goal:Q')
    
    return (bar + goal_line).configure_view(strokeWidth=0)

# --- 3. UI DISPLAY ---
categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, category in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {category}")
            
            # Category Filtering
            cat_df = df[df['type'].str.contains(category, case=False)]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%", delta=f"{(share - TARGET_PERCENTAGE):.1f}%" if share > 0 else None)
            m2.metric("Done", user_closed)
            m3.metric("Total", total_pool)
            
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)
            else:
                st.info(f"No {category} tickets found.")

st.divider()

# --- 4. SUMMARY TABLE ---
st.markdown("### 📋 Detail Summary")
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
        "Target Status": "✅ On Track" if share >= TARGET_PERCENTAGE else "⏳ Action Needed"
    })

st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
