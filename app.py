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

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} - OKR Tracker", layout="wide", page_icon="✦")

# --- CUSTOM CSS (Inspired by your Dashboard) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&display=swap');

html, body, [class*="st-"] { 
    font-family: 'Manrope', sans-serif; 
}

/* Hero Banner */
.header-container { 
    padding: 2.5rem; 
    background-image: linear-gradient(rgba(14, 17, 23, 0.6), rgba(14, 17, 23, 0.8)), url('https://i.ibb.co/nMTJF4B9/vj-HZbu8-Imgur.jpg'); 
    background-size: cover; 
    background-position: center; 
    margin-bottom: 2rem; 
    border-radius: 0px !important; 
    text-align: center;
}
.header-container h1 { color: #FFFFFF !important; font-size: 2.5rem; font-weight: 600; margin: 0; padding: 0;}
.header-container p { color: #A0AEC0 !important; font-size: 1.1rem; font-weight: 300; margin-top: 5px; }

/* Flat UI Enforcements */
div[data-testid="stContainer"], div[data-testid="stExpander"], div[data-testid="stVerticalBlock"] { 
    border-radius: 0px !important; 
}

/* Custom Metric Styling */
.custom-metric-box {
    text-align: center;
    padding: 10px;
}
.custom-metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
}
.custom-metric-label {
    font-size: 0.9rem;
    font-weight: 500;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Color Coding */
.val-green { color: #00E676; }
.val-blue { color: #58C0ED; }
.val-orange { color: #FFC300; }
</style>
""", unsafe_allow_html=True)

# --- ALTAIR GLOBAL THEME ---
def set_altair_theme():
    font = "Manrope"
    alt.themes.register("my_theme", lambda: {
        "config": {
            "font": font,
            "title": {"font": font, "fontSize": 14, "fontWeight": 600},
            "axis": {"labelFont": font, "titleFont": font, "grid": False},
        }
    })
    alt.themes.enable("my_theme")
set_altair_theme()

# --- HEADER ---
st.markdown(f"""
<div class="header-container">
    <h1>✦ {TRACKED_USER}'s OKR Tracker</h1>
    <p>Live Market Share Data for Display, Video, and Celtra (From {OKR_GO_LIVE_DATE})</p>
</div>
""", unsafe_allow_html=True)


# --- 1. DATA LOADING (The Bulletproof Method) ---
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
        payload_dict = {
            "jql": jql_query,
            "fields": fields_to_request,
            "maxResults": 1000 
        }
        
        if next_page_token:
            payload_dict["nextPageToken"] = next_page_token
            
        payload = json.dumps(payload_dict)
        
        response = requests.post(url, headers=headers, data=payload, auth=JIRA_AUTH, timeout=15)
        
        if response.status_code != 200:
            st.error(f"Jira API Error {response.status_code}: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        
        if not issues: break
        all_issues.extend(issues)
        
        next_page_token = data.get('nextPageToken')
        progress_bar.info(f"📥 Downloading Jira Data: {len(all_issues)} tickets fetched so far...")
        
        if not next_page_token: break

    progress_bar.empty()
    return all_issues

# --- 2. PROCESSING ---
raw_issues = fetch_jira_okr_data()
rows = []
DONE_STATUSES = ["closed", "done", "resolved", "campaign/request closed", "completed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    
    issue_type_name = fields.get('issuetype', {}).get('name', '') if fields.get('issuetype') else ""
    issue_type_lower = issue_type_name.lower()
    
    category = "Other"
    if "display" in issue_type_lower: category = "Display"
    elif "video" in issue_type_lower or "ctv" in issue_type_lower or "ott" in issue_type_lower: category = "Video"
    elif "celtra" in issue_type_lower: category = "Celtra"
        
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

if df.empty:
    st.warning("No data found for this period.")
    st.stop()


# --- 3. HELPER CHARTS ---
def build_progress_chart(share_val):
    bar_color = '#00E676' if share_val >= TARGET_PERCENTAGE else '#58C0ED' 
    chart_data = pd.DataFrame({'Share': [share_val], 'Goal': [TARGET_PERCENTAGE]})
    
    bar = alt.Chart(chart_data).mark_bar(size=24).encode(
        x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None, axis=alt.Axis(labels=False, ticks=False)),
        color=alt.value(bar_color),
        tooltip=['Share']
    ).properties(height=40)
    
    goal_line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=3).encode(
        x='Goal:Q',
        tooltip=['Goal']
    )
    return (bar + goal_line).configure_view(strokeWidth=0)


# --- 4. DASHBOARD UI ---
categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.markdown(f"<h3 style='text-align:center; font-weight:600; margin-top:0;'>{cat}</h3>", unsafe_allow_html=True)
            
            cat_df = df[df['Category'] == cat]
            total_team = len(cat_df)
            user_done = len(cat_df[(cat_df['Assignee'] == TRACKED_USER) & (cat_df['Is_Closed'])])
            share = (user_done / total_team * 100) if total_team > 0 else 0
            
            # Custom 3-Metric Layout
            m1, m2, m3 = st.columns(3)
            m1.markdown(f"<div class='custom-metric-box'><p class='custom-metric-value val-blue'>{share:.1f}%</p><p class='custom-metric-label'>Share</p></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='custom-metric-box'><p class='custom-metric-value val-green'>{user_done}</p><p class='custom-metric-label'>Done</p></div>", unsafe_allow_html=True)
            m3.markdown(f"<div class='custom-metric-box'><p class='custom-metric-value val-orange'>{total_team}</p><p class='custom-metric-label'>Total</p></div>", unsafe_allow_html=True)
            
            # Progress Bar at the bottom of the card
            if total_team > 0:
                st.altair_chart(build_progress_chart(share), use_container_width=True)

st.divider()

# --- 5. DATA TABLES ---
st.markdown("### 📋 Executive Summary")
summary_list = []
for cat in categories:
    c_df = df[df['Category'] == cat]
    t = len(c_df)
    d = len(c_df[(c_df['Assignee'] == TRACKED_USER) & (c_df['Is_Closed'])])
    share_val = (d/t*100) if t > 0 else 0
    summary_list.append({
        "Category": cat,
        "Total Team Tickets": t,
        "Jingyao Completed": d,
        "Current Share": f"{share_val:.1f}%",
        "Target": f"{TARGET_PERCENTAGE}%",
        "Status": "✅ On Track" if share_val >= TARGET_PERCENTAGE else "⏳ Needs Attention"
    })
st.dataframe(pd.DataFrame(summary_list), use_container_width=True, hide_index=True)

st.write("")
with st.expander("🔍 Ticket Audit Log (Verify Categorization)"):
    st.write("Review the raw ticket assignment to verify the OKR categorization logic.")
    st.dataframe(df[df['Category'] != "Other"], use_container_width=True, hide_index=True)
