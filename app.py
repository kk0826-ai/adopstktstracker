import streamlit as st
import pandas as pd
import requests
import json
import datetime
from requests.auth import HTTPBasicAuth

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Master TKTS Tracker", layout="wide")

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 

# Master Target Dictionary for the Entire Team
USER_TARGETS = {
    "Jingyao Wang": {"Display": 14.0, "Video": 14.0, "Celtra": 10.0},
    "Priyanka Shaw": {"Display": 12.0, "Video": 12.0, "Celtra": 10.0, "SeenThis": 10.0},
    "Pushyami": {"Display": 16.0, "Video": 16.0, "Celtra": 11.0},
    "Roshni Subramanian": {"Display": 12.0, "Video": 12.0, "Celtra": 10.0, "SeenThis": 10.0},
    "Simin Zheng": {"Display": 16.0, "Video": 16.0, "Celtra": 10.0, "SeenThis": 16.0},
    "Tania Singh": {"Display": 15.0, "Video": 15.0, "Celtra": 15.0, "SeenThis": 15.0},
    "Kiran Kumar": {"Troubleshooting": 16.0} # Added Kiran Kumar with Troubleshooting
}

VALID_TEAM = [name.lower().strip() for name in USER_TARGETS.keys()]

# --- JIRA AUTH ---
try:
    domain = st.secrets["JIRA_DOMAIN"].strip().rstrip('/')
    if "/rest/api" in domain:
        domain = domain.split("/rest/api")[0]
    JIRA_AUTH = HTTPBasicAuth(st.secrets["JIRA_USER_EMAIL"], st.secrets["JIRA_API_TOKEN"])
except Exception:
    st.error("Missing Jira Secrets in Streamlit settings.")
    st.stop()

# --- CUSTOM CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&display=swap');

/* Apply font safely without breaking Material Icons */
html, body, p, div, h1, h2, h3, h4, h5, h6, span { 
    font-family: 'Manrope', Arial, sans-serif; 
}

/* Ensure Streamlit icons render correctly */
i, .material-icons, .material-symbols-rounded, [class*="icon"] {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}

/* Hero Banner */
.header-container { 
    padding: 1.2rem; 
    background-image: linear-gradient(rgba(14, 17, 23, 0.6), rgba(14, 17, 23, 0.8)), url('https://i.ibb.co/nMTJF4B9/vj-HZbu8-Imgur.jpg'); 
    background-size: cover; 
    background-position: center; 
    margin-bottom: 1.5rem; 
    border-radius: 0px !important; 
    text-align: center;
}
.header-container h1 { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 600; margin: 0; padding: 0;}

/* Enforce Sharp Edges Everywhere */
div[data-testid="stContainer"], 
div[data-testid="stTabs"], 
div[data-testid="stVerticalBlock"], 
div[data-testid="stMetric"],
[data-testid="stTable"],
[data-testid="stTable"] > div { 
    border-radius: 0px !important; 
}
button { 
    border-radius: 0px !important; 
}

/* Make Dropdown selectboxes flat */
div[data-baseweb="select"] > div {
    border-radius: 0px !important;
}

/* Custom Metric Styling */
.custom-metric-box {
    text-align: center;
    padding: 5px 0px; 
}
.custom-metric-value {
    font-size: 2.0rem; 
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
}
.custom-metric-label {
    font-size: 0.85rem;
    font-weight: 600; 
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px; 
    white-space: nowrap; 
}

/* Custom HTML Tables */
.static-table {
    border: 1px solid rgba(250, 250, 250, 0.2);
    border-radius: 0px !important; 
    margin-bottom: 1.5rem;
}
.scrollable-table {
    height: 400px;
    overflow-y: auto;
    border: 1px solid rgba(250, 250, 250, 0.2);
    border-radius: 0px !important; 
}
.custom-audit-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}
.custom-audit-table th, .custom-audit-table td {
    padding: 10px;
    border-bottom: 1px solid rgba(250, 250, 250, 0.1);
    text-align: left;
}
.custom-audit-table th {
    background-color: #0E1117; 
    color: white;
    position: sticky;
    top: 0;
    z-index: 1;
    font-weight: 600;
}

.custom-audit-table a {
    color: #58C0ED;
    text-decoration: none;
    font-weight: 600;
}
.custom-audit-table a:hover {
    text-decoration: underline;
}

/* Color Coding */
.val-green { color: #00E676; }
.val-blue { color: #58C0ED; }
.val-orange { color: #FFC300; }
</style>
""", unsafe_allow_html=True)

# --- 2. HEADER & DROPDOWN ---
header_placeholder = st.empty()

col_spacer1, col_center, col_spacer2 = st.columns([1, 2, 1])
with col_center:
    TRACKED_USER = st.selectbox(
        "👤 Select Team Member:", 
        options=list(USER_TARGETS.keys()), 
        index=list(USER_TARGETS.keys()).index("Jingyao Wang") 
    )

header_placeholder.markdown(f"""
<div class="header-container">
    <h1>{TRACKED_USER}'s TKTS Tracker</h1>
</div>
""", unsafe_allow_html=True)


# --- 3. DATA LOADING ---
@st.cache_data(ttl=600)
def fetch_jira_okr_data():
    all_issues = []
    
    url = f"{domain}/rest/api/3/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    jql_query = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}" ORDER BY created DESC'
    fields_to_request = ["summary", "assignee", "status", "issuetype", "resolutiondate", "created"]
    
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
        progress_bar.info(f"Downloading Jira Data: {len(all_issues)} tickets fetched so far...")
        
        if not next_page_token: break

    progress_bar.empty()
    return all_issues

# --- 4. PROCESSING ---
raw_issues = fetch_jira_okr_data()
rows = []
DONE_STATUSES = ["closed", "done", "resolved", "campaign/request closed", "completed"]

for issue in raw_issues:
    fields = issue.get('fields', {})
    ticket_key = issue.get('key')
    
    created_raw = fields.get('created')
    created_date = pd.to_datetime(created_raw).strftime('%d %b %Y') if created_raw else "Unknown"
    
    issue_type_name = fields.get('issuetype', {}).get('name', '') if fields.get('issuetype') else ""
    issue_type_lower = issue_type_name.lower()
    
    category = "Other"
    
    # Catching all ticket types, including Troubleshooting
    if "display" in issue_type_lower: 
        category = "Display"
    elif any(keyword in issue_type_lower for keyword in ["video", "ctv", "ott"]): 
        category = "Video"
    elif "celtra" in issue_type_lower: 
        category = "Celtra"
    elif "seenthis" in issue_type_lower:
        category = "SeenThis"
    elif "troubleshooting" in issue_type_lower:
        category = "Troubleshooting"
        
    assignee = fields.get('assignee')
    assignee_name = assignee.get('displayName', 'Unassigned') if assignee else "Unassigned"
    
    status_name = fields.get('status', {}).get('name', '').lower()
    is_closed = (status_name in DONE_STATUSES) or (fields.get('resolutiondate') is not None)
    
    jira_link = f'<a href="{domain}/browse/{ticket_key}" target="_blank">{ticket_key}</a>'
    
    rows.append({
        "TKTS-ID": jira_link,
        "Created Date": created_date,
        "TKTS-Type": issue_type_name,
        "Category": category,
        "Assignee": assignee_name,
        "Assignee_Lower": assignee_name.lower().strip(),
        "Status": status_name.title(),
        "Is_Closed": is_closed
    })

df = pd.DataFrame(rows)

if df.empty:
    st.warning("No data found for this period.")
    st.stop()

# --- FILTER BY TARGET POD/TEAM ---
team_df = df[df['Assignee_Lower'].isin(VALID_TEAM)].copy()
team_df.drop(columns=['Assignee_Lower'], inplace=True) 

if team_df.empty:
    st.warning("No tickets found for the specified team members.")
    st.stop()

# --- 5. ACTUAL PERCENTAGE CSS PROGRESS BAR ---
def render_custom_progress_bar(share_val, target_val):
    progress_ratio = (share_val / target_val * 100) if target_val > 0 else 0
    fill_width = min(100, progress_ratio)
    
    bar_color = "#00E676" 
    track_color = "#E2E8F0" 
    
    actual_share_int = int(round(share_val))
    target_int = int(round(target_val))
    
    progress_label_html = ""
    
    if progress_ratio > 100:
        progress_label_html = f'<div style="position: absolute; right: 0; top: 50%; transform: translate(-8px, -50%); background-color: #FF0000; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 3px 8px; border-radius: 3px; z-index: 20; display: flex; align-items: center;">{actual_share_int}%<div style="position: absolute; right: -5px; top: 50%; transform: translateY(-50%); width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 5px solid #FF0000;"></div></div>'
    elif progress_ratio > 0:
        if progress_ratio < 15:
            progress_label_html = f'<div style="position: absolute; left: {fill_width}%; top: 50%; transform: translate(8px, -50%); color: #666; font-size: 14px; font-weight: 800; z-index: 20;">{actual_share_int}%</div>'
        else:
            progress_label_html = f'<div style="position: absolute; left: {fill_width}%; top: 50%; transform: translate(calc(-100% - 8px), -50%); color: #000; font-size: 14px; font-weight: 800; z-index: 20;">{actual_share_int}%</div>'
        
    html = f'<div style="width: 100%; padding: 10px 15px 30px 10px; box-sizing: border-box; font-family: \'Manrope\', sans-serif;"><div style="position: relative; width: 100%; height: 28px; background-color: {track_color}; border-radius: 0px;"><div style="position: absolute; top: 0; left: 0; height: 100%; width: {fill_width}%; background-color: {bar_color}; transition: width 0.5s;"></div><div style="position: absolute; right: 0; top: -6px; bottom: -6px; width: 3px; background-color: #FF0000; z-index: 10;"></div>{progress_label_html}</div><div style="position: relative; width: 100%; height: 20px; margin-top: 6px;"><span style="position: absolute; left: 0; font-size: 15px; color: #888; font-weight: 600;">0%</span><span style="position: absolute; right: -10px; font-size: 15px; font-weight: 800; color: #888;">{target_int}% Goal</span></div></div>'
    return html


# --- 6. DASHBOARD UI ---
# Dynamically pull ONLY the categories the selected user has a target for
active_categories = list(USER_TARGETS[TRACKED_USER].keys())

cols = st.columns(len(active_categories))

for idx, cat in enumerate(active_categories):
    with cols[idx]:
        with st.container(border=True):
            st.markdown(f"<h3 style='text-align:center; font-weight:600; margin-top:0;'>{cat}</h3>", unsafe_allow_html=True)
            
            cat_df = team_df[team_df['Category'] == cat]
            total_team = len(cat_df)
            
            user_done = len(cat_df[(cat_df['Assignee'].str.lower().str.strip() == TRACKED_USER.lower().strip()) & (cat_df['Is_Closed'])])
            share = (user_done / total_team * 100) if total_team > 0 else 0
            
            m1, m2 = st.columns(2)
            m1.markdown(f"<div class='custom-metric-box'><p class='custom-metric-value val-green'>{user_done}</p><p class='custom-metric-label'>Done</p></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='custom-metric-box'><p class='custom-metric-value val-orange'>{total_team}</p><p class='custom-metric-label'>Total</p></div>", unsafe_allow_html=True)
            
            target_val = USER_TARGETS[TRACKED_USER].get(cat, 0)
            
            if total_team > 0:
                st.markdown(render_custom_progress_bar(share, target_val), unsafe_allow_html=True)

st.divider()

# --- 7. DATA TABLES ---
st.markdown("### Summary")
summary_list = []
for cat in active_categories:
    c_df = team_df[team_df['Category'] == cat]
    t = len(c_df)
    d = len(c_df[(c_df['Assignee'].str.lower().str.strip() == TRACKED_USER.lower().strip()) & (c_df['Is_Closed'])])
    share_val = (d/t*100) if t > 0 else 0
    target_val = USER_TARGETS[TRACKED_USER].get(cat, 0)
    
    summary_list.append({
        "Category": cat,
        "Total Team Tickets": t,
        f"{TRACKED_USER.split()[0]} Completed": d,
        "Current Share": f"{share_val:.1f}%",
        "Target": f"{target_val}%",
        "Status": "On Track" if share_val >= target_val else "Needs Attention"
    })

summary_df = pd.DataFrame(summary_list)
summary_html = summary_df.to_html(index=False, classes="custom-audit-table", escape=False)
st.markdown(f'<div class="static-table">{summary_html}</div>', unsafe_allow_html=True)

# --- 8. AUDIT LOG WITH DYNAMIC CALENDAR FILTERS ---
st.markdown("### Ticket Audit Log")

# Filter exactly to the categories the active user owns
audit_df = team_df[
    (team_df['Assignee'].str.lower().str.strip() == TRACKED_USER.lower().strip()) & 
    (team_df['Category'].isin(active_categories))
].drop(columns=['Is_Closed'])

if not audit_df.empty:
    audit_df['DateObj'] = pd.to_datetime(audit_df['Created Date'], format='%d %b %Y').dt.date
    min_date = audit_df['DateObj'].min()
    max_date = audit_df['DateObj'].max()
else:
    min_date, max_date = None, None

# Setup the filters UI
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("📅 From", value=None, min_value=min_date, max_value=max_date)
    with date_col2:
        end_date = st.date_input("📅 To", value=None, min_value=min_date, max_value=max_date)
        
with filter_col2:
    type_filter = st.multiselect("Filter by TKTS-Type", sorted(audit_df['TKTS-Type'].unique()))

with filter_col3:
    cat_filter = st.multiselect("Filter by Category", sorted(audit_df['Category'].unique()))

# Apply Date Filter
if start_date and end_date:
    audit_df = audit_df[(audit_df['DateObj'] >= start_date) & (audit_df['DateObj'] <= end_date)]
elif start_date:
    audit_df = audit_df[audit_df['DateObj'] >= start_date]
elif end_date:
    audit_df = audit_df[audit_df['DateObj'] <= end_date]

# Apply Multiselect Dropdown Filters
if type_filter:
    audit_df = audit_df[audit_df['TKTS-Type'].isin(type_filter)]
if cat_filter:
    audit_df = audit_df[audit_df['Category'].isin(cat_filter)]

if 'DateObj' in audit_df.columns:
    audit_df = audit_df.drop(columns=['DateObj'])

if audit_df.empty:
    st.info("No tickets match the selected filters.")
else:
    audit_html = audit_df.to_html(index=False, classes="custom-audit-table", escape=False)
    st.markdown(f'<div class="scrollable-table">{audit_html}</div>', unsafe_allow_html=True)
