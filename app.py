# app.py (Streamlit Front End)
import streamlit as st
import requests
import os
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="AI Resume Screener", layout="wide")
st.title("AI-Based Resume Screening System")
col_left, col_right = st.columns([1, 1])

with col_left:
    st.header("Resume Analyzer")

    if "analysis_result" in st.session_state:
        result = st.session_state["analysis_result"]
        st.success(f"Match Percentage: {result['match_percentage']:.2f}%")
        st.text_area("Extracted Resume Text:", result["resume_text"], height=200)

    uploaded_file = st.file_uploader("Upload your resume (PDF format)", type=["pdf"])
    job_description = st.text_area("Enter the Job Description", height=150)
    overwrite = st.checkbox("Overwrite if resume already exists?", value=False)

    if st.button("Analyze Resume"):
        if uploaded_file and job_description:
            temp_file_path = f"temp_{uploaded_file.name}"
            try:
                
                with open(temp_file_path, "wb") as temp_file:
                    temp_file.write(uploaded_file.read())
                
                with open(temp_file_path, "rb") as file:
                    files = {"file": file}
                    data = {"job_description": job_description, "overwrite": str(overwrite)}
                    with st.spinner("Analyzing resume..."):
                        response = requests.post("http://127.0.0.1:8000/upload_resume/", files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    st.session_state["analysis_result"] = result  # Save result in session state.
                    st.success(f"Match Percentage: {result['match_percentage']:.2f}%")
                    st.text_area("Extracted Resume Text:", result["resume_text"], height=200)
                else:
                    error_msg = response.json().get("error", "Unknown error")
                    st.error(f"Error processing resume: {error_msg}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
        else:
            st.warning("Please upload a resume and enter a job description.")




with col_right:
    st.header("Uploaded Resumes & Job Matches")
    st.markdown("#### Filter by Filename or Job Description:")

    
    filename_filter = st.text_input("Filename Filter", key="filename_filter")
    job_desc_filter = st.text_input("Job Description Filter", key="job_desc_filter")

    
    params = {
        "filename": filename_filter,
        "job_description": job_desc_filter,
        "min_match": 0,   # These are still in the API defaults
        "max_match": 100  # but are not exposed in the UI.
    }

    
    with st.spinner("Fetching data..."):
        search_response = requests.get("http://127.0.0.1:8000/uploads/", params=params)
    if search_response.status_code == 200:
        data = search_response.json()
        uploads = data.get("uploads", [])
        if not uploads:
            st.info("No matching resumes found.")
        else:
            
            df_uploads = pd.DataFrame(uploads)
            
            gb = GridOptionsBuilder.from_dataframe(df_uploads)
            gb.configure_default_column(filter=True, editable=False, sortable=True, resizable=True)
            
            gb.configure_pagination(paginationPageSize=20)
            gridOptions = gb.build()
            
            AgGrid(
                df_uploads,
                gridOptions=gridOptions,
                update_mode=GridUpdateMode.NO_UPDATE,
                enable_enterprise_modules=True,
                height=400,
                fit_columns_on_grid_load=True,
            )
    else:
        st.error("Error fetching data.")
