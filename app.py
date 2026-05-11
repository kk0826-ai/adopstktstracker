import streamlit as st
import pandas as pd
import requests
import altair as alt
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
OKR_GO_LIVE_DATE = "2026-04-01" 
TRACKED_USER = "Jingyao Wang"
TARGET_PERCENTAGE = 20.0 

# --- JIRA AUTH ---
try:
    JIRA_DOMAIN = st.secrets["JIRA_DOMAIN"]
    JIRA_USER_EMAIL = st.secrets["JIRA_USER_EMAIL"]
    JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
    JIRA_AUTH = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)
except Exception:
    st.error("Jira secrets missing in Settings.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title=f"{TRACKED_USER} OKR", layout="wide", page_icon="✦")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700&display=swap');
html, body, [class*="st-"] { font-family: 'Manrope', sans-serif; }
.header-box {
    background: linear-gradient(90deg, #0f2027, #2c5364);
    padding: 20px; border-radius: 4px; color: white; margin-bottom: 25px;
}
.header-box h1 { margin: 0; font-weight: 700; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- 1. DATA LOADING (Updated to GET /search to avoid API Removal error) ---
@st.cache_data(ttl=1800)
def load_h1_data():
    # Using the standard search endpoint with GET parameters
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    
    # We search both 'issuetype' AND 'Customer Request Type' to catch all 58 Celtra tickets
    jql = f"""
    project = TKTS 
    AND (
        issuetype ~ "Display" OR "Customer Request Type" ~ "Display" OR 
        issuetype ~ "Video" OR "Customer Request Type" ~ "Video" OR 
        issuetype ~ "Celtra" OR "Customer Request Type" ~ "Celtra"
    )
    AND created >= "{OKR_GO_LIVE_DATE}"
    """
    
    params = {
        "jql": jql,
        "fields": "key,issuetype,assignee,status",
        "maxResults": 1000
    }
    
    # Using GET instead of POST to satisfy the new Jira API migration requirements
    response = requests.get(url, auth=JIRA_AUTH, params=params, timeout=20)
    
    if not response.ok:
        st.error(f"Jira API Error: {response.text}")
        st.stop()
        
    data = response.json()
    issues = data.get('issues', [])
    
    # Ensuring "Campaign/request closed" is counted as completed
    done_statuses = ["closed", "done", "resolved", "campaign/request closed"]
    
    results = []
    for i in issues:
        f = i['fields']
        # Extract the type name (either from Issue Type or Custom Request Type)
        type_name = f.get('issuetype', {}).get('name', 'Unknown')
        
        results.append({
            "key": i['key'],
            "type": type_name,
            "assignee": f['assignee']['displayName'] if f.get('assignee') else "Unassigned",
            "is_closed": f['status']['name'].lower() in done_statuses
        })
    return pd.DataFrame(results)

# --- 2. EXECUTION ---
with st.spinner("✦ Fetching Latest Stats..."):
    df = load_h1_data()

# --- 3. UI DISPLAY ---
st.markdown(f'<div class="header-box"><h1>✦ {TRACKED_USER}\'s Performance</h1></div>', unsafe_allow_html=True)

categories = ["Display", "Video", "Celtra"]
cols = st.columns(3)

for idx, category in enumerate(categories):
    with cols[idx]:
        with st.container(border=True):
            st.subheader(f"✦ {category}")
            
            # Filter the dataframe for the category
            cat_df = df[df['type'].str.contains(category, case=False)]
            total_pool = len(cat_df)
            user_closed = len(cat_df[(cat_df['assignee'] == TRACKED_USER) & (cat_df['is_closed'])])
            share = (user_closed / total_pool * 100) if total_pool > 0 else 0
            
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Share %", f"{share:.1f}%")
            m2.metric("Done", user_closed)
            m3.metric("Pool", total_pool)
            
            # Simplified Chart
            if total_pool > 0:
                chart_data = pd.DataFrame({'Share': [share], 'Goal': [TARGET_PERCENTAGE]})
                bar_color = '#00E676' if share >= TARGET_PERCENTAGE else '#FFCA28'
                
                bar = alt.Chart(chart_data).mark_bar(size=30, cornerRadiusEnd=4).encode(
                    x=alt.X('Share:Q', scale=alt.Scale(domain=[0, 100]), title=None),
                    color=alt.value(bar_color)
                ).properties(height=80)
                
                line = alt.Chart(chart_data).mark_rule(color='#FF5252', strokeWidth=2, strokeDash=[4,4]).encode(x='Goal:Q')
                st.altair_chart(bar + line, use_container_width=True)
            else:
                st.info(f"No {category} tickets yet.")

st.divider()
st.markdown("### 📋 Recent Work Log")
# Shows Jingyao's actual tickets to verify the count
st.dataframe(df[df['assignee'] == TRACKED_USER][['key', 'type', 'is_closed']].head(10), use_container_width=True, hide_index=True)
