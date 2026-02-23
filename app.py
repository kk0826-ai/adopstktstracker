import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth
from datetime import datetime

# --- CONFIGURATION ---
# Set your Go-Live date here. Only tickets created after this date are counted.
OKR_GO_LIVE_DATE = "2026-02-01" 

# --- JIRA AUTH (Uses your existing secrets) ---
JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)

st.set_page_config(page_title="H1 OKR Performance Tracker", layout="wide")

st.title("🏆 H1 2026 Performance Tracker")
st.info(f"Tracking tickets created from Go-Live Date: **{OKR_GO_LIVE_DATE}** onwards.")

# --- 1. DATA LOADING ---
@st.cache_data(ttl=3600)
def load_h1_data():
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    # Pulling all tickets since OKR start date
    jql = f'project = TKTS AND created >= "{OKR_GO_LIVE_DATE}"'
    fields = ["key", "issuetype", "assignee", "status", "resolutiondate"]
    
    payload = {"jql": jql, "fields": fields, "maxResults": 1000}
    response = requests.post(url, json=payload, auth=JIRA_AUTH)
    response.raise_for_status()
    
    issues = []
    for i in response.json().get('issues', []):
        f = i['fields']
        issues.append({
            "key": i['key'],
            "type": f['issuetype']['name'],
            "assignee": f['assignee']['displayName'] if f['assignee'] else "Unassigned",
            "status": f['status']['name'],
            "is_closed": f['status']['name'].lower() in ["closed", "done", "resolved"]
        })
    return pd.DataFrame(issues)

# --- 2. LOGIC & CALCULATIONS ---
df = load_h1_data()

if df.empty:
    st.warning("No tickets found for the current OKR period.")
else:
    # Get list of unique team members for selection
    team_members = sorted(df['assignee'].unique())
    selected_user = st.selectbox("Select Team Member to Track:", team_members)

    # Filter for Display Tickets specifically (as per your OKR example)
    # Note: Using a case-insensitive 'contains' to catch ANZ - Display, UK - Display, etc.
    display_df = df[df['type'].str.contains("Display", case=False)]
    
    # Calculate Totals
    total_display_pool = len(display_df)
    user_closed_display = len(display_df[(display_df['assignee'] == selected_user) & (display_df['is_closed'])])
    
    # Live Percentage Calculation
    share_percentage = (user_closed_display / total_display_pool * 100) if total_display_pool > 0 else 0

    # --- 3. UI DISPLAY ---
    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric(label="Your Display Market Share", value=f"{share_percentage:.1f}%")
        st.write(f"**Total Pool:** {total_display_pool} Display TKTS raised team-wide.")
        st.write(f"**Your Work:** {user_closed_display} tickets completed.")
    
    with col2:
        # Progress Bar Chart
        goal_value = 20.0 # Your 20% OKR goal
        chart_data = pd.DataFrame({'Share': [share_percentage], 'Goal': [goal_value]})
        
        # Determine color based on goal
        bar_color = '#00CC66' if share_percentage >= goal_value else '#FF9933'
        
        progress_bar = alt.Chart(chart_data).mark_bar(size=40, cornerRadiusEnd=5).encode(
            x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title="Percentage Completed"),
            color=alt.value(bar_color),
            tooltip=['Share']
        ).properties(height=100)
        
        # Add a goal line at 20%
        goal_line = alt.Chart(pd.DataFrame({'x': [goal_value]})).mark_rule(color='red', strokeDash=[5,5], size=2).encode(x='x:Q')
        
        st.altair_chart(progress_bar + goal_line, use_container_width=True)
        st.caption(f"Red dashed line represents the {goal_value}% target.")

    st.divider()
    
    # Breakdown Table
    st.subheader("Your Share Across All Categories")
    summary = []
    # Identify broad categories (Display, Video, Pixel, etc.)
    for cat in ["Display", "Video", "Pixel", "Bespoke"]:
        cat_pool = df[df['type'].str.contains(cat, case=False)]
        total_cat = len(cat_pool)
        user_cat = len(cat_pool[(cat_pool['assignee'] == selected_user) & (cat_pool['is_closed'])])
        perc = (user_cat / total_cat * 100) if total_cat > 0 else 0
        summary.append({"Category": cat, "Team Total": total_cat, "Your Completed": user_cat, "Current Share %": f"{perc:.1f}%"})
    
    st.table(summary)
