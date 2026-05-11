import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH ---
try:
    # Ensure domain is just 'https://company.atlassian.net'
    domain = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    if "/rest/api" in domain:
        domain = domain.split("/rest/api")[0]
    
    auth = HTTPBasicAuth(st.secrets["JIRA_USER_EMAIL"], st.secrets["JIRA_API_TOKEN"])
except Exception:
    st.error("Missing Jira Secrets in Streamlit Settings.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title="OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s OKR Tracker")

# --- 1. DATA LOADING (New /search/jql Endpoint) ---
@st.cache_data(ttl=600)
def fetch_all_jira_data():
    all_issues = []
    start_at = 0
    max_results = 100
    
    # Jira's NEW required endpoint
    search_url = f"{domain}/rest/api/3/search/jql"
    jql = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    progress_text = st.empty()
    
    while True:
        # We use 'params' to send data via the URL, which is safer for this endpoint
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,assignee,status" 
        }
        
        response = requests.get(search_url, params=params, auth=auth)
        
        if response.status_code != 200:
            st.error(f"Jira API Error: {response.status_code} - {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        progress_text.text(f"📥 Syncing tickets: {len(all_issues)} / {total}...")
        
        if len(all_issues) >= total or not issues:
            break
        start_at += max_results

    progress_text.empty()
    return all_issues

# --- 2. PROCESSING ---
raw_issues = fetch_all_jira_data()

if not raw_issues:
    st.warning("No tickets found. Check Project Key 'TKTS' or Date.")
    st.stop()

rows = []
done_statuses = ["closed", "done", "resolved", "campaign/request closed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    
    # Keyword search across the whole issue to catch "Display", "Video", "Celtra"
    # This ensures "SEA - Display", "UK - Display", etc., are all counted.
    full_text = str(issue).lower()
    
    cat = "Other"
    if "celtra" in full_text:
        cat = "Celtra"
    elif "display" in full_text:
        cat = "Display"
    elif "video" in full_text:
        cat = "Video"
        
    assignee = fields.get('assignee', {})
    display_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
    
    status_name = fields.get('status', {}).get('name', '').lower()
    
    rows.append({
        "Category": cat,
        "Assignee": display_name,
        "Is_Closed": status_name in done_statuses
    })

df = pd.DataFrame(rows)

# --- 3. DISPLAY ---
categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(cat)
            cat_df = df[df['Category'] == cat]
            total_count = len(cat_df)
            user_done = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
            
            share = (user_done / total_count * 100) if total_count > 0 else 0
            
            st.metric("Your Share %", f"{share:.1f}%")
            st.write(f"✅ **{user_done}** Done")
            st.write(f"📊 **{total_count}** Team Total")
            st.progress(min(share / 100, 1.0))

st.divider()
st.write("### 📋 Breakdown Table")
summary = []
for cat in categories:
    cat_df = df[df['Category'] == cat]
    t = len(cat_df)
    d = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
    summary.append({
        "Category": cat,
        "Total Team": t,
        "Jingyao Done": d,
        "Share %": f"{(d/t*100 if t>0 else 0):.1f}%"
    })
st.table(pd.DataFrame(summary))
