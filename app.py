import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH (Exact same as your main tool) ---
try:
    JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira secrets missing.")
    st.stop()

# --- UI STYLE ---
st.set_page_config(page_title=f"{TRACKED_USER} OKR", layout="wide", page_icon="✦")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700&display=swap');
html, body, [class*="st-"] { font-family: 'Manrope', sans-serif; }
.header-box { background: #0f2027; padding: 20px; border-radius: 4px; color: white; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (Mirroring the Main Tool's Logic) ---
@st.cache_data(ttl=1800)
def load_h1_data():
    # Use the EXACT same endpoint as your main tool
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    
    # Updated JQL: We use the ~ (contains) operator. 
    # This searches the whole ticket for "Celtra", "Display", etc. 
    # This is the ONLY way to catch those 58 tickets from your CSV.
    jql = f"""
    project = TKTS 
    AND (text ~ "Display" OR text ~ "Video" OR text ~ "Celtra")
    AND created >= "{OKR_GO_LIVE_DATE}"
    ORDER BY created DESC
    """
    
    # Exact same payload structure as the main tool
    payload = {
        "jql": jql,
        "fields": ["key", "issuetype", "assignee", "status", "summary"],
        "maxResults": 1000
    }
    
    # Use the exact same POST method as the main tool
    response = requests.post(url, json=payload, auth=JIRA_AUTH)
    
    if not response.ok:
        st.error(f"Jira Error: {response.text}")
        st.stop()
        
    issues = response.json().get('issues', [])
    
    # Status logic: ensure "Campaign/request closed" is included
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    
    results = []
    for i in issues:
        f = i['fields']
        # We look at the Summary and IssueType to categorize
        summary_text = f.get('summary', '')
        type_name = f.get('issuetype', {}).get('name', '')
        combined_text = (summary_text + " " + type_name).lower()
        
        # Determine Category
        cat = "Other"
        if "display" in combined_text: cat = "Display"
        elif "video" in combined_text: cat = "Video"
        elif "celtra" in combined_text: cat = "Celtra"
        
        results.append({
            "key": i['key'],
            "category": cat,
            "assignee": f['assignee']['displayName'] if f.get('assignee') else "Unassigned",
            "is_closed": f['status']['name'].lower() in done_statuses
        })
    return pd.DataFrame(results)

# --- 2. EXECUTION ---
with st.spinner("✦ Syncing with Jira..."):
    df = load_h1_data()

# --- 3. UI DISPLAY ---
st.markdown(f'<div class="header-box"><h1>✦ {TRACKED_USER}\'s OKR Status</h1></div>', unsafe_allow_html=True)

categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, cat in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {cat}")
            
            # Filter the logic
            cat_df = df[df['category'] == cat]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%")
            m2.metric("Done", user_closed)
            m3.metric("Pool", total_pool)
            
            if total_pool > 0:
                chart_data = pd.DataFrame({'Share': [share], 'Goal': [TARGET_PERCENTAGE]})
                bar = alt.Chart(chart_data).mark_bar(size=30, color='#00E676' if share >= TARGET_PERCENTAGE else '#FFCA28').encode(
                    x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None)
                ).properties(height=80)
                st.altair_chart(bar, use_container_width=True)

st.divider()
st.markdown("### 📋 Verification List (Jingyao's Work)")
# This table lets you see the tickets to confirm the count of 4 for Celtra
st.dataframe(df[(df['assignee'] == TRACKED_USER) & (df['category'] != "Other")], use_container_width=True, hide_index=True)
