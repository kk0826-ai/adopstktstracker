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

st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s H1 OKR Tracker")

# --- 1. DATA LOADING (Pagination + issuetype fetch) ---
@st.cache_data(ttl=600)
def fetch_jira_okr_data():
    all_issues = []
    start_at = 0
    max_results = 100
    
    # Updated to the new mandatory endpoint
    url = f"{domain}/rest/api/3/search/jql"
    
    # JQL focused on your project and date range
    jql = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    progress_bar = st.empty()
    
    while True:
        # We explicitly ask for 'issuetype' because that contains the "Display" label
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,assignee,status,issuetype,resolutiondate"
        }
        
        response = requests.get(url, params=params, auth=auth)
        if response.status_code != 200:
            st.error(f"Jira API Error: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        progress_bar.info(f"📥 Loading OKR Data: {len(all_issues)} / {total} tickets...")
        
        if len(all_issues) >= total or not issues:
            break
        start_at += max_results

    progress_bar.empty()
    return all_issues

# --- 2. PROCESSING & CATEGORIZATION ---
raw_issues = fetch_jira_okr_data()
rows = []

# Statuses that count as "Done" based on your JQL logic
DONE_STATUSES = ["closed", "done", "resolved", "campaign/request closed", "completed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    
    # IMPORTANT: We fetch the Name of the Issue Type (e.g. "SEA - Display Creatives")
    issue_type_name = fields.get('issuetype', {}).get('name', '')
    summary = fields.get('summary', '')
    
    # Combined text for categorization
    combined_text = f"{issue_type_name} {summary}".lower()
    
    # Grouping logic
    category = "Other"
    if "display" in combined_text:
        category = "Display"
    elif "video" in combined_text or "ctv" in combined_text or "ott" in combined_text:
        category = "Video"
    elif "celtra" in combined_text:
        category = "Celtra"
        
    assignee = fields.get('assignee')
    assignee_name = assignee.get('displayName', 'Unassigned') if assignee else "Unassigned"
    
    # A ticket is "Closed" if its status is in our list OR if it has a resolution date
    status_name = fields.get('status', {}).get('name', '').lower()
    is_closed = (status_name in DONE_STATUSES) or (fields.get('resolutiondate') is not None)
    
    rows.append({
        "Category": category,
        "Assignee": assignee_name,
        "Is_Closed": is_closed
    })

df = pd.DataFrame(rows)

# --- 3. DASHBOARD DISPLAY ---
if df.empty:
    st.warning("No data found for this period.")
    st.stop()

categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {cat}")
            cat_df = df[df['Category'] == cat]
            
            total_team = len(cat_df)
            user_done = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
            
            share = (user_done / total_team * 100) if total_team > 0 else 0
            
            st.metric("Your Share %", f"{share:.1f}%")
            st.write(f"✅ **{user_done}** Done")
            st.write(f"📊 **{total_team}** Team Total")
            st.progress(min(share/100, 1.0))

st.divider()
st.subheader("📋 Detailed OKR Breakdown")
summary_list = []
for cat in categories:
    c_df = df[df['Category'] == cat]
    t = len(c_df)
    d = len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])])
    summary_list.append({
        "Category": cat,
        "Team Total": t,
        "Jingyao Done": d,
        "Current Share": f"{(d/t*100 if t>0 else 0):.1f}%"
    })
st.table(pd.DataFrame(summary_list))
