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
    domain = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    if "/rest/api" in domain:
        domain = domain.split("/rest/api")[0]
    auth = HTTPBasicAuth(st.secrets["JIRA_USER_EMAIL"], st.secrets["JIRA_API_TOKEN"])
except Exception:
    st.error("Missing Jira Secrets.")
    st.stop()

st.set_page_config(page_title="OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s OKR Tracker")

# --- 1. DATA LOADING (Uses your exact JQL logic) ---
@st.cache_data(ttl=600)
def fetch_jira_data():
    all_issues = []
    start_at = 0
    max_results = 100
    
    url = f"{domain}/rest/api/3/search/jql"
    
    # We use your exact project and date, but simplify the JQL for the API
    jql = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    progress_bar = st.progress(0, text="Syncing with Jira...")
    
    while True:
        # We ask for "customfield_10010" which is "Customer Request Type"
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,assignee,status,customfield_10010"
        }
        
        response = requests.get(url, params=params, auth=auth)
        if response.status_code != 200:
            st.error(f"Jira Error: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        if total > 0:
            progress_bar.progress(min(len(all_issues)/total, 1.0), text=f"📥 Received {len(all_issues)} of {total} tickets...")
        
        if len(all_issues) >= total or not issues:
            break
        start_at += max_results

    progress_bar.empty()
    return all_issues

# --- 2. PROCESSING & CATEGORIZATION ---
issues = fetch_jira_data()
rows = []
done_statuses = ["closed", "done", "resolved", "campaign/request closed"]

for issue in issues:
    fields = issue.get('fields', {})
    
    # Get Request Type (usually stored in a dict inside customfield_10010)
    req_type_data = fields.get('customfield_10010')
    req_type_name = ""
    if isinstance(req_type_data, dict):
        req_type_name = req_type_data.get('requestType', {}).get('name', '')
    elif isinstance(req_type_data, str):
        req_type_name = req_type_data
        
    summary = fields.get('summary', '')
    
    # Combined search: Check Request Type FIRST, then Summary
    full_search_text = f"{req_type_name} {summary}".lower()
    
    category = "Other"
    if "display" in full_search_text:
        category = "Display"
    elif "video" in full_search_text:
        category = "Video"
    elif "celtra" in full_search_text:
        category = "Celtra"
        
    assignee = fields.get('assignee')
    assignee_name = assignee.get('displayName', 'Unassigned') if assignee else "Unassigned"
    
    status = fields.get('status', {}).get('name', '').lower()
    
    rows.append({
        "Category": category,
        "Assignee": assignee_name,
        "Is_Closed": status in done_statuses
    })

df = pd.DataFrame(rows)

# --- 3. DASHBOARD ---
if df.empty:
    st.warning("No data found.")
    st.stop()

categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(cat)
            c_df = df[df['Category'] == cat]
            total = len(c_df)
            done = len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])])
            share = (done / total * 100) if total > 0 else 0
            
            st.metric("Your Share %", f"{share:.1f}%")
            st.write(f"**{done}** Done / **{total}** Total")
            st.progress(min(share/100, 1.0))

st.divider()
st.subheader("📊 Detailed Summary")
summary_data = []
for cat in categories:
    c_df = df[df['Category'] == cat]
    t = len(c_df)
    d = len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])])
    summary_data.append({
        "Category": cat,
        "Total Team Tickets": t,
        "Jingyao Completed": d,
        "Current Share": f"{(d/t*100 if t>0 else 0):.1f}%"
    })
st.table(pd.DataFrame(summary_data))
