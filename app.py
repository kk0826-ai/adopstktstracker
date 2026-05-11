import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH & URL SANITIZATION ---
try:
    RAW_DOMAIN = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    JIRA_DOMAIN = RAW_DOMAIN.split("/rest/api")[0] if "/rest/api" in RAW_DOMAIN else RAW_DOMAIN
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="✦")

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
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(f"""
<div class="header-box">
    <h1>✦ {TRACKED_USER}'s H1 OKR Tracker</h1>
    <p>Tracking Live Market Share for Display, Video, and Celtra (From {OKR_GO_LIVE_DATE})</p>
</div>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (Robust Pagination) ---
@st.cache_data(ttl=600) 
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    # Note: We query specifically for the fields we need to keep the data payload small
    jql_query = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}"'
    
    all_issues = []
    start_at = 0
    max_results = 50 # Smaller chunks to prevent HTTP timeouts
    
    load_progress = st.progress(0, text="Connecting to Jira...")
    
    try:
        while True:
            payload = {
                "jql": jql_query, 
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ["assignee", "status", "summary", "issuetype", "customfield_10010"] 
            }
            
            response = requests.post(url, json=payload, auth=JIRA_AUTH)
            
            # If a specific page fails, show the error but return what we have so far
            if response.status_code != 200:
                st.error(f"Jira API error on batch starting at {start_at}: {response.status_code}")
                break

            data = response.json()
            issues = data.get('issues', [])
            if not issues:
                break
                
            all_issues.extend(issues)
            total = data.get('total', 0)
            
            # Update UI
            percent = min(len(all_issues) / total, 1.0) if total > 0 else 1.0
            load_progress.progress(percent, text=f"Syncing: {len(all_issues)} / {total} tickets...")
            
            start_at += max_results
            if len(all_issues) >= total:
                break
                
    except Exception as e:
        st.warning(f"Data sync interrupted: {e}. Showing partial results.")

    load_progress.empty()
    
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    parsed_data = []
    
    for i in all_issues:
        f = i.get('fields', {})
        
        # We prioritize "Customer Request Type" for classification to match your CSV
        # Then we fall back to the Summary text.
        req_type = str(f.get('customfield_10010', '')).lower()
        summary = str(f.get('summary', '')).lower()
        combined_context = f"{req_type} {summary}"
        
        ticket_type = "Other"
        if "celtra" in combined_context:
            ticket_type = "Celtra"
        elif "display" in combined_context:
            ticket_type = "Display"
        elif "video" in combined_context:
            ticket_type = "Video"
            
        assignee_dict = f.get('assignee')
        status_dict = f.get('status', {})
        
        parsed_data.append({
            "key": i.get('key'),
            "type": ticket_type,
            "assignee": assignee_dict.get('displayName') if assignee_dict else "Unassigned",
            "is_closed": status_dict.get('name', '').lower() in done_statuses
        })
        
    return pd.DataFrame(parsed_data)

# --- 2. LOGIC ---
with st.spinner("Crunching numbers..."):
    df = load_h1_data()

if df.empty:
    st.warning("No data found. Check your Jira permissions or Project Key.")
    st.stop()

# Progress Chart Function
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        color=alt.value(bar_color)
    ).properties(height=60)
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=2).encode(x='Goal:Q')
    return (bar + goal_line).configure_view(strokeWidth=0)

# --- 3. UI DISPLAY ---
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
            m1.metric("Share %", f"{share:.1f}%")
            m2.metric("Done", user_closed)
            m3.metric("Team Total", total_pool)
            
            if total_pool > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)
            else:
                st.caption(f"No {category} tickets found.")

st.divider()
st.markdown("### 📋 Detailed Summary")
summary_list = []
for cat in categories:
    c_df = df[df['type'] == cat]
    t = len(c_df)
    u = len(c_df[(c_df['assignee'] == TRACKED_USER) & (c_df['is_closed'])])
    s = (u / t * 100) if t > 0 else 0
    summary_list.append({"Category": cat, "Team Total": t, "Your Done": u, "Current Share": f"{s:.1f}%"})

st.dataframe(pd.DataFrame(summary_list), use_container_width=True, hide_index=True)
