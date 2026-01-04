import os
import time
import json
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from notion_client import Client
from datetime import datetime
import requests

# --- CONFIGURATION & SETUP ---
load_dotenv()

st.set_page_config(
    page_title="CareerBridge AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🎨 CUSTOM STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #2563EB, #10B981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .section-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    
    .job-card {
        border-left: 4px solid #2563EB;
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.5rem;
    }
    
    /* Success/Error message styling */
    .stSuccess, .stError { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

## --- BACKEND LOGIC (UPDATED) ---

# Configure Gemini
api_status = "🟢 Systems Online"
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    api_status = "🔴 AI Config Error"

# Notion Configuration
NOTION_KEY = os.getenv("NOTION_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

def fetch_jobs_from_notion():
    """Fetches jobs matching the EXACT schema from your screenshot."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    try:
        response = requests.post(url, headers=notion_headers(), json={})
        
        # 1. Handle Auth Errors
        if response.status_code == 401:
            st.error("🛑 Authentication Error: Notion rejected the key. Check for hidden spaces in .env")
            return []
            
        data = response.json()
        jobs = []
        for page in data.get("results", []):
            props = page.get("properties", {})
            
            # --- EXTRACT DATA BASED ON YOUR SCREENSHOT ---
            
            # 1. 'Title' column (Type: Title) -> "Software Engineer Intern"
            title_list = props.get("Title", {}).get("title", [])
            job_title = title_list[0]["plain_text"] if title_list else "Untitled"
            
            # 2. 'Role' column (Type: Text) -> "Backend Developer"
            role_list = props.get("Role", {}).get("rich_text", [])
            role_detail = role_list[0]["plain_text"] if role_list else ""
            
            # 3. 'Company' column (Type: Text)
            comp_list = props.get("Company", {}).get("rich_text", [])
            company = comp_list[0]["plain_text"] if comp_list else "Unknown"
            
            # 4. 'Required Skills' column (Type: Text)
            skills_list = props.get("Required Skills", {}).get("rich_text", [])
            skills = skills_list[0]["plain_text"] if skills_list else ""
            
            # 5. 'Description' column (Type: Text)
            desc_list = props.get("Description", {}).get("rich_text", [])
            desc = desc_list[0]["plain_text"] if desc_list else ""

            jobs.append({
                "role": f"{job_title} - {role_detail}", # Combine them for better clarity
                "company": company,
                "skills": skills,
                "description": desc
            })
        return jobs
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return []

def post_job_to_notion(title, role_detail, company, skills, description, contact):
    """Corrected to match your 'Title' primary column."""
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            # "Title" is the primary column in your screenshot
            "Title": {"title": [{"text": {"content": title}}]},
            "Role": {"rich_text": [{"text": {"content": role_detail}}]},
            "Company": {"rich_text": [{"text": {"content": company}}]},
            "Required Skills": {"rich_text": [{"text": {"content": skills}}]},
            "Description": {"rich_text": [{"text": {"content": description}}]},
            "Contact": {"rich_text": [{"text": {"content": contact}}]},
        }
    }
    # ... keep the rest of your try/except block ...
    
    try:
        response = requests.post(url, headers=notion_headers(), json=payload)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Failed to post: {response.text}")
            return False
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return False
    
# 3. Gemini Analysis Function
def get_career_guidance(student_profile, job_market_data):
    """
    Uses Gemini to match student profile against fetched Notion jobs
    and provide gap analysis.
    """
    prompt = f"""
    You are an expert AI Career Counselor. 
    
    1. ANALYZE the Student Profile:
    {student_profile}
    
    2. ANALYZE the Current Job Market (data fetched from real-time database):
    {json.dumps(job_market_data)}
    
    3. PROVIDE OUTPUT in strictly valid Markdown format:
    - **Match Analysis**: Compare the student's skills to the specific jobs listed in the market data.
    - **Skill Gap**: Identify exactly what skills (Python, SQL, Communication, etc.) the student lacks for the best matching roles.
    - **Recommended Jobs**: List the top 2-3 specific roles from the market data that fit best.
    - **Learning Path**: A short, bulleted list of what they should learn next.
    
    Tone: Encouraging, professional, and specific.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "Sorry, I couldn't generate an analysis at this moment."

# --- MAIN UI ---

st.markdown('<div class="main-title">CareerBridge AI</div>', unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.header("Mode Selection")
    user_mode = st.radio("I am a:", ["🎓 Student", "🏢 Industry Recruiter"])
    st.markdown("---")
    st.caption(f"System Status: {api_status}")
    st.info("This tool connects students with real-time industry opportunities using AI.")

# --- INDUSTRY RECRUITER VIEW ---
if user_mode == "🏢 Industry Recruiter":
    st.subheader("📢 Post a New Opportunity")
    st.markdown("Fill out the details below to add a job to the student database.")
    
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            company_name = st.text_input("Company Name")
            role_title = st.text_input("Job Role / Title")
            contact_info = st.text_input("Contact Email/Link")
        with col2:
            req_skills = st.text_area("Required Skills (comma separated)", placeholder="Python, React, Data Analysis...")
            job_desc = st.text_area("Job Description", height=135)
        
        if st.button("🚀 Post Job", use_container_width=True):
            if company_name and role_title and req_skills:
                with st.spinner("Validating and posting to Notion..."):
                    success = post_job_to_notion(role_title, company_name, req_skills, job_desc, contact_info)
                    if success:
                        st.success("Job posted successfully! It is now visible to students.")
                        time.sleep(2)
                        st.rerun()
            else:
                st.warning("Please fill in Company, Role, and Skills.")
    
    st.markdown("---")
    st.markdown("### 📋 Current Active Listings")
    # Quick view of what's currently in DB
    current_jobs = fetch_jobs_from_notion()
    if current_jobs:
        for job in current_jobs:
            with st.expander(f"{job['role']} at {job['company']}"):
                st.write(f"**Skills:** {job['skills']}")
                st.write(job['description'])
    else:
        st.info("No active jobs found in the database.")


# --- STUDENT VIEW ---
elif user_mode == "🎓 Student":
    st.subheader("🚀 Career Guidance & Job Match")
    st.markdown("Tell us about yourself, and AI will match you with real open positions.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### 👤 Your Profile")
        s_name = st.text_input("Name")
        s_skills = st.text_area("Your Current Skills", placeholder="e.g. Python, Public Speaking, Excel, Basic Java")
        s_interests = st.text_area("Interests / Desired Roles", placeholder="e.g. Data Scientist, Marketing Intern, Web Dev")
        analyze_btn = st.button("✨ Analyze & Find Jobs", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        if analyze_btn and s_skills and s_interests:
            with st.spinner("Fetching market data & analyzing profile..."):
                # 1. Get Real Data
                market_data = fetch_jobs_from_notion()
                
                # 2. Build Profile Dict
                student_profile = {
                    "name": s_name,
                    "skills": s_skills,
                    "interests": s_interests
                }
                
                # 3. Get AI Analysis
                guidance = get_career_guidance(student_profile, market_data)
                
                # 4. Display Results
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("#### 🤖 AI Career Report")
                st.markdown(guidance)
                st.markdown('</div>', unsafe_allow_html=True)
        elif analyze_btn:
            st.warning("Please enter your skills and interests to get an analysis.")
        else:
            # Placeholder content
            st.info("👈 Enter your details on the left to get started.")
            st.markdown("#### Recently Posted Jobs")
            recent_jobs = fetch_jobs_from_notion()[:3] # Show last 3
            if recent_jobs:
                for job in recent_jobs:
                    st.markdown(f"""
                    <div class="job-card">
                        <b>{job['role']}</b> @ {job['company']}<br>
                        <small>{job['skills']}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("*No jobs currently available.*")