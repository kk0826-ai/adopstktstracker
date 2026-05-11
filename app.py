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
    # Clean the domain
    domain = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    if "/rest/api" in domain:
        domain = domain.split("/rest/api")[0]
    
    auth = HTTPBasicAuth(st.secrets["JIRA_USER_EMAIL"], st.secrets["JIRA_API_TOKEN"])
except Exception:
    st.error("Missing Jira Secrets (Domain, Email, or Token).")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title="OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s OKR Tracker")
st.caption(f"Tracking tickets from {OKR_GO_LIVE_DATE}")

# --- 1. DATA LOADING (Simplified GET Method) ---
@st.cache_data(ttl=600)
def fetch_all_jira_data():
    all_issues = []
    start_at = 0
    max_results = 100
    
    # We use a simple GET request which is much more stable
    search_url = f"{domain}/rest/api/3/search"
    jql = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    progress_text = st.empty()
    
    while True:
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,assignee,status,customfield_10010" # summary, user, status
        }
        
        response = requests.get(search_url, params=params, auth=auth)
        
        if response.status_code != 200:
            st.error(f"Jira API Error: {response.status_code} - {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        progress_text.text(f"📥 Loading tickets: {len(all_issues)} / {total}...")
        
        if len(all_issues) >= total or not issues:
            break
        start_at += max_results

    progress_text.empty()
    return all_issues

# --- 2. PROCESSING ---
raw_issues = fetch_all_jira_data()

if not raw_issues:
    st.warning("No tickets found. Check your Project Key (TKTS) or Date.")
    st.stop()

# Build the list for the dashboard
rows = []
done_statuses = ["closed", "done", "resolved", "campaign/request closed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    
    # Classification Logic
    # We look at everything (Summary and Request Type) to categorize
    combined_text = f"{fields.get('summary', '')} {str(fields).lower()}"
    
    cat = "Other"
    if "celtra" in combined_text.lower():
        cat = "Celtra"
    elif "display" in combined_text.lower():
        cat = "Display"
    elif "video" in combined_text.lower():
        cat = "Video"
        
    assignee = fields.get('assignee', {})
    display_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
    
    status = fields.get('status', {})
    status_name = status.get('name', '').lower()
    
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
        st.subheader(cat)
        cat_df = df[df['Category'] == cat]
        total_count = len(cat_df)
        user_done = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
        
        share = (user_done / total_count * 100) if total_count > 0 else 0
        
        st.metric("Your Share %", f"{share:.1f}%")
        st.write(f"**{user_done}** completed by you")
        st.write(f"**{total_count}** total team tickets")
        st.progress(share / 100 if share <= 100 else 1.0)

st.divider()
st.write("### 📋 Data Breakdown")
summary = []
for cat in categories:
    cat_df = df[df['Category'] == cat]
    t = len(cat_df)
    d = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
    summary.append({
        "Category": cat,
        "Team Total": t,
        "Jingyao Completed": d,
        "Market Share": f"{(d/t*100 if t>0 else 0):.1f}%"
    })
st.table(pd.DataFrame(summary))
