import streamlit as st
import pandas as pd
import requests
import json
import altair as alt
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
    JIRA_AUTH = HTTPBasicAuth(st.secrets["JIRA_USER_EMAIL"], st.secrets["JIRA_API_TOKEN"])
except Exception:
    st.error("Missing Jira Secrets in Streamlit settings.")
    st.stop()

st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide")
st.title(f"✦ {TRACKED_USER}'s H1 OKR Tracker")

# --- 1. DATA LOADING (Identical to your working tool) ---
@st.cache_data(ttl=600)
def fetch_jira_okr_data():
    all_issues = []
    
    url = f"{domain}/rest/api/3/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    jql_query = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}" ORDER BY created DESC'
    fields_to_request = ["summary", "assignee", "status", "issuetype", "resolutiondate"]
    
    progress_bar = st.empty()
    next_page_token = None
    
    while True:
        # EXACT match to your working tool, but with the new nextPageToken for pagination
        payload_dict = {
            "jql": jql_query,
            "fields": fields_to_request,
            "maxResults": 1000 
        }
        
        # If Jira gives us a token for the next page, we include it in the payload
        if next_page_token:
            payload_dict["nextPageToken"] = next_page_token
            
        payload = json.dumps(payload_dict)
        
        response = requests.post(url, headers=headers, data=payload, auth=JIRA_AUTH, timeout=15)
        
        if response.status_code != 200:
            st.error(f"Jira API Error {response.status_code}: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        
        if not issues:
            break
            
        all_issues.extend(issues)
        
        # The new API uses nextPageToken instead of total/startAt
        next_page_token = data.get('nextPageToken')
        
        progress_bar.info(f"📥 Downloading Jira Data: {len(all_issues)} tickets fetched so far...")
        
        if not next_page_token:
            break

    progress_bar.empty()
    return all_issues

# --- 2. PROCESSING & CATEGORIZATION ---
raw_issues = fetch_jira_okr_data()
rows = []

# Statuses that count as "Done"
DONE_STATUSES = ["closed", "done", "resolved", "campaign/request closed", "completed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    
    # Extract the exact Issue Type name (e.g., "SEA - Display Creatives")
    issue_type_name = fields.get('issuetype', {}).get('name', '') if fields.get('issuetype') else ""
    issue_type_lower = issue_type_name.lower()
    
    category = "Other"
    
    # Categorize based strictly on the issuetype name, mimicking your JQL list
    if "display" in issue_type_lower:
        category = "Display"
    elif "video" in issue_type_lower or "ctv" in issue_type_lower or "ott" in issue_type_lower:
        category = "Video"
    elif "celtra" in issue_type_lower:
        category = "Celtra"
        
    assignee = fields.get('assignee')
    assignee_name = assignee.get('displayName', 'Unassigned') if assignee else "Unassigned"
    
    status_name = fields.get('status', {}).get('name', '').lower()
    is_closed = (status_name in DONE_STATUSES) or (fields.get('resolutiondate') is not None)
    
    rows.append({
        "Ticket Key": issue.get('key'),
        "Issue Type": issue_type_name,
        "Category": category,
        "Assignee": assignee_name,
        "Is_Closed": is_closed,
        "Status": status_name.title()
    })

df = pd.DataFrame(rows)

# --- 3. DASHBOARD DISPLAY ---
if df.empty:
    st.warning("No data found for this period.")
    st.stop()

# Helper function to generate premium charts
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#FFCA28' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        color=alt.value(bar_color)
    ).properties(height=60)
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=2).encode(x='Goal:Q')
    return (bar + goal_line).configure_view(strokeWidth=0)

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
            if total_team > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)

st.divider()

# --- 4. SUMMARY & AUDIT ---
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
st.dataframe(pd.DataFrame(summary_list), use_container_width=True, hide_index=True)

st.write("---")
with st.expander("🔍 Verify Raw Data (Ticket Audit Log)"):
    st.write("View exactly which tickets are being counted under each category to verify the logic.")
    st.dataframe(df[df['Category'] != "Other"], use_container_width=True, hide_index=True)
