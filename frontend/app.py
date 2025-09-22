import streamlit as st
import requests
import os

# -------------------------
# Configuration
# -------------------------
API_URL = os.getenv("API_URL", "https://your-backend-url")  # Replace with your backend Render URL

st.title("Translation & Editing Tool 🎓")

role = st.radio("Select Role:", ["Student", "Instructor"])

if role == "Student":
    student_name = st.text_input("Your Name:")
    translation = st.text_area("Enter your translation here:", "")
    score = st.number_input("Enter your score:", 0, 100)
    time_taken = st.number_input("Time taken (seconds):", 0, 3600)
    
    if st.button("Submit"):
        if student_name and translation:
            payload = {
                "student": student_name,
                "translation": translation,
                "score": score,
                "time_taken": time_taken
            }
            try:
                response = requests.post(f"{API_URL}/submissions/", json=payload)
                st.success(response.json().get("message", "Submitted!"))
            except:
                st.error("Could not connect to backend.")
        else:
            st.warning("Please enter your name and translation.")

elif role == "Instructor":
    st.subheader("All Submissions")
    try:
        response = requests.get(f"{API_URL}/submissions/")
        if response.status_code == 200:
            submissions = response.json()
            if submissions:
                st.table(submissions)
            else:
                st.info("No submissions yet.")
        else:
            st.error(f"Error fetching submissions: {response.text}")
    except:
        st.error("Could not connect to backend.")
