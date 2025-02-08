import streamlit as st
import requests
import os

st.set_page_config(page_title="AI Resume Screener", layout="centered")

st.title("AI-Based Resume Screening System")
st.write("Upload your resume and compare it against a job description.")

uploaded_file = st.file_uploader("Upload your resume (PDF format)", type=["pdf"])
job_description = st.text_area("Enter the Job Description", height=150)

if st.button("Analyze Resume"):
    if uploaded_file and job_description:
        temp_file_path = f"temp_{uploaded_file.name}"
        try:
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(uploaded_file.read())

            with open(temp_file_path, "rb") as file:
                files = {"file": file}
                data = {"job_description": job_description}
                response = requests.post("http://127.0.0.1:8000/upload_resume/", files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                st.success(f"Match Percentage: {result['match_percentage']:.2f}%")
                st.text_area("Extracted Resume Text:", result["resume_text"], height=200)
            else:
                st.error(f"Error processing resume: {response.json().get('error', 'Unknown error')}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        st.warning("Please upload a resume and enter a job description.")

st.subheader("Search Resumes")
search_query = st.text_input("Enter search keywords:")
if st.button("Search"):
    if search_query:
        search_response = requests.get(f"http://127.0.0.1:8000/search_resumes/?query={search_query}")
        if search_response.status_code == 200:
            results = search_response.json()
            if not results["resumes"]:
                st.info("No matching resumes found")
            else:
                for res in results["resumes"]:
                    st.write(f"**{res['filename']}**")
                    st.write(f"Match: {res['match_percentage']:.2f}%")
                    st.write(f"Snippet: {res['snippet']}")
                    st.write("---")
        else:
            st.error("Error searching resumes.")