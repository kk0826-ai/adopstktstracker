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
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(f'<div class="header-box"><h1>✦ {TRACKED_USER}\'s OKR Tracker</h1></div>', unsafe_allow_html=True)

# --- 1. DATA LOADING (Ultra-Safe Version) ---
@st.cache_data(ttl=600) 
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    # Simplified query to ensure no syntax errors
    jql_query = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    all_issues = []
    start_at = 0
    max_results = 50 
    
    load_progress = st.progress(0, text="Initializing Jira Sync...")
    
    try:
        while True:
            # We only request standard fields to avoid 400 Errors from missing Custom Fields
            payload = {
                "jql": jql_query, 
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ["summary", "assignee", "status", "issuetype"] 
            }
            
            response = requests.post(url, json=payload, auth=JIRA_AUTH)
            
            if response.status_code != 200:
                st.error(f"Jira API Error {response.status_code}: {response.text}")
                break

            data = response.json()
            issues = data.get('issues', [])
            if not issues:
                break
                
            all_issues.extend(issues)
            total = data.get('total', 0)
            
            percent = min(len(all_issues) / total, 1.0) if total > 0 else 1.0
            load_progress.progress(percent, text=f"Downloading {len(all_issues)} / {total} tickets...")
            
            start_at += max_results
            if len(all_issues) >= total:
                break
                
    except Exception as e:
        st.warning(f"Connection issue: {e}")

    load_progress.empty()
    
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    parsed_data = []
    
    for i in all_issues:
        f = i.get('fields', {})
        
        # KEYWORD MATCHING: Since we can't reliably name the Custom Field ID, 
        # we check the entire ticket object string for our categories.
        ticket_full_text = str(i).lower()
        
        category = "Other"
        if "celtra" in ticket_full_text:
            category = "Celtra"
        elif "display" in ticket_full_text:
            category = "Display"
        elif "video" in ticket_full_text:
            category = "Video"
            
        assignee = f.get('assignee')
        status = f.get('status', {})
        
        parsed_data.append({
            "key": i.get('key'),
            "type": category,
            "assignee": assignee.get('displayName') if assignee else "Unassigned",
            "is_closed": status.get('name', '').lower() in done_statuses
        })
        
    return pd.DataFrame(parsed_data)

# --- 2. CALCULATIONS ---
df = load_h1_data()

if df.empty:
    st.error("No data found. Please check if your JIRA_DOMAIN and API Token are correct.")
    st.stop()

# --- 3. UI ---
categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {cat}")
            c_df = df[df['type'] == cat]
            total = len(c_df)
            done = len(c_df[(c_df['assignee'] == TRACKED_USER) & (c_df['is_closed'])])
            share = (done / total * 100) if total > 0 else 0
            
            st.metric("Share %", f"{share:.1f}%")
            st.write(f"**{done}** done out of **{total}** total")
            
            # Simple Progress Bar
            st.progress(share / 100)

st.divider()
st.markdown("### 📋 Detailed Summary")
summary = []
for cat in categories:
    c_df = df[df['type'] == cat]
    t, d = len(c_df), len(c_df[(c_df['assignee'] == TRACKED_USER) & (c_df['is_closed'])])
    summary.append({"Category": cat, "Team Total": t, "Your Done": d, "Share": f"{(d/t*100 if t>0 else 0):.1f}%"})
st.table(pd.DataFrame(summary))
