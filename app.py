import streamlit as st
import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH & URL CLEANUP ---
try:
    RAW_DOMAIN = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    JIRA_DOMAIN = RAW_DOMAIN.split("/rest/api")[0] if "/rest/api" in RAW_DOMAIN else RAW_DOMAIN
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira Secrets are missing or incorrect.")
    st.stop()

st.set_page_config(page_title="OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s OKR Tracker")

# --- 1. DATA LOADING (Maximum Fetch) ---
@st.cache_data(ttl=600)
def fetch_complete_data():
    all_issues = []
    start_at = 0
    max_results = 100
    
    # Using the mandatory JQL endpoint
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    
    # Base query for the project and date
    jql = f'project = "TKTS" AND created >= "{OKR_GO_LIVE_DATE}"'
    
    status_msg = st.empty()
    
    while True:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ["summary", "assignee", "status", "issuetype", "components"] 
        }
        
        # We use POST to allow for larger payloads and more stable connection
        response = requests.post(url, json=payload, auth=JIRA_AUTH)
        
        if response.status_code != 200:
            st.error(f"API Error {response.status_code}: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        if not issues:
            break
            
        all_issues.extend(issues)
        total = data.get('total', 0)
        
        status_msg.info(f"🔄 Syncing tickets from Jira... {len(all_issues)} of {total} collected.")
        
        if len(all_issues) >= total:
            break
        start_at += max_results

    status_msg.empty()
    return all_issues

# --- 2. PROCESSING & CATEGORIZATION ---
raw_data = fetch_complete_data()
processed_rows = []

# Statuses that count as "Done"
DONE_STATUSES = ["closed", "done", "resolved", "campaign/request closed", "completed"]

for issue in raw_data:
    fields = issue.get('fields', {})
    
    # CATEGORIZATION: We search the entire JSON of the ticket (Deep Scan)
    # This catches "Display" whether it's in the title, request type, or component.
    full_ticket_text = json.dumps(issue).lower()
    
    # Logic to match your JQL exactly
    category = "Other"
    if "display" in full_ticket_text:
        category = "Display"
    elif "video" in full_ticket_text or "ctv" in full_ticket_text or "ott" in full_ticket_text:
        category = "Video"
    elif "celtra" in full_ticket_text:
        category = "Celtra"
        
    assignee_obj = fields.get('assignee')
    name = assignee_obj.get('displayName', 'Unassigned') if assignee_obj else "Unassigned"
    
    status_name = fields.get('status', {}).get('name', '').lower()
    
    processed_rows.append({
        "Key": issue.get('key'),
        "Category": category,
        "Assignee": name,
        "Is_Closed": status_name in DONE_STATUSES
    })

df = pd.DataFrame(processed_rows)

# --- 3. UI DASHBOARD ---
if df.empty:
    st.warning("No tickets found for the selected period.")
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
            
            # OKR Calculation
            share = (user_done / total_team * 100) if total_team > 0 else 0
            
            st.metric("Market Share %", f"{share:.1f}%")
            st.write(f"**{user_done}** tickets completed by you")
            st.write(f"**{total_team}** total team tickets found")
            st.progress(min(share/100, 1.0))

st.divider()

# --- 4. DATA VALIDATION TABLE ---
with st.expander("🔍 View Raw Breakdown (Verify Ticket Counts)"):
    st.write("This table shows the counts for every category found.")
    summary = []
    for cat in categories:
        c_df = df[df['Category'] == cat]
        summary.append({
            "Category": cat,
            "Total Found": len(c_df),
            "Jingyao Done": len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])]),
            "Market Share": f"{(len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])])/len(c_df)*100 if len(c_df)>0 else 0):.1f}%"
        })
    st.table(pd.DataFrame(summary))
    
    st.write("---")
    st.write("### Sample of 'Display' Tickets Found")
    st.dataframe(df[df['Category'] == 'Display'].head(20), use_container_width=True)
