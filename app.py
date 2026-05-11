import streamlit as st
import pandas as pd
import requests
import altair as alt
import json
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
    st.error("Jira secrets not found in Settings.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} Tracker", layout="wide", page_icon="✦")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;700&display=swap');
html, body, [class*="st-"] { font-family: 'Manrope', sans-serif; }
.header-box {
    background: linear-gradient(90deg, #0f2027, #203a43, #2c5364);
    padding: 20px; border-radius: 4px; color: white; margin-bottom: 25px;
}
.header-box h1 { margin: 0; font-weight: 700; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (FIXED JQL & FIELD MAPPING) ---
@st.cache_data(ttl=1800)
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    # FIX: Changed 'type' to '"Customer Request Type"' to match your Jira setup
    # Also kept 'issuetype' as a fallback search
    jql = f"""
    project = TKTS 
    AND (
        "Customer Request Type" IN ("ANZ - Display Creatives", "ANZ - Video Creatives", "ANZ - Celtra Creatives", "UK - Display Creatives", "UK - Video Creatives", "UK - Celtra Creatives", "SEA - Display Creatives", "SEA - Video Creatives", "SEA - Celtra Creatives", "IN - Display Creatives", "IN - Video Creatives", "IN - Celtra Creatives")
        OR issuetype IN ("ANZ - Display Creatives", "ANZ - Video Creatives", "ANZ - Celtra Creatives", "UK - Display Creatives", "UK - Video Creatives", "UK - Celtra Creatives", "SEA - Display Creatives", "SEA - Video Creatives", "SEA - Celtra Creatives", "IN - Display Creatives", "IN - Video Creatives", "IN - Celtra Creatives")
    )
    AND created >= "{OKR_GO_LIVE_DATE}"
    ORDER BY created DESC
    """
    
    payload = json.dumps({
        "jql": jql,
        "fields": ["key", "issuetype", "assignee", "status", "customfield_10010"], # 10010 is common for Request Type
        "maxResults": 1000 
    })
    
    response = requests.post(url, headers=headers, data=payload, auth=JIRA_AUTH)
    if not response.ok:
        st.error(f"Jira API Error: {response.text}")
        st.stop()
        
    issues = response.json().get('issues', [])
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    
    results = []
    for i in issues:
        f = i['fields']
        # We check both the Issue Type and the Request Type if available
        # Jira often stores Request Type labels in a specific format; we extract the text.
        req_type = f.get('issuetype', {}).get('name', '')
        
        results.append({
            "key": i['key'],
            "type": req_type,
            "assignee": f['assignee']['displayName'] if f['assignee'] else "Unassigned",
            "is_closed": f['status']['name'].lower() in done_statuses
        })
    return pd.DataFrame(results)

# --- 2. EXECUTION & UI ---
with st.spinner("✦ Fetching data..."):
    df = load_h1_data()

def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        color=alt.value(bar_color)
    ).properties(height=80)
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=2, strokeDash=[4,4]).encode(x='Goal:Q')
    return (bar + goal_line).configure_view(strokeWidth=0)

st.markdown(f'<div class="header-box"><h1>✦ {TRACKED_USER}\'s OKR Tracker</h1></div>', unsafe_allow_html=True)

categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, category in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {category}")
            cat_df = df[df['type'].str.contains(category, case=False)]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%")
            m2.metric("Done", user_closed)
            m3.metric("Total", total_pool)
            
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)
            else:
                st.info(f"No {category} tickets.")

st.divider()
st.table(df[df['assignee'] == TRACKED_USER][['key', 'type', 'is_closed']].head(10))
