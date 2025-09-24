import streamlit as st
import requests
from rapidfuzz import fuzz  # ✅ replacing Levenshtein

API_URL = "https://editing-and-translation-tool.onrender.com"  # your backend URL

st.title("Translation Evaluation Tool")

menu = ["Student", "Instructor"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Student":
    st.subheader("Submit Your Translation")

    student = st.text_input("Your Name")
    translation = st.text_area("Your Translation")
    reference = st.text_area("Reference Translation")

    if st.button("Submit"):
        if not student or not translation or not reference:
            st.warning("Please fill in all fields")
        else:
            # ✅ Using rapidfuzz instead of Levenshtein
            score = fuzz.ratio(translation, reference) / 100.0  
            time_taken = 0  

            data = {
                "student": student,
                "translation": translation,
                "score": score,
                "time_taken": time_taken,
            }

            try:
                res = requests.post(f"{API_URL}/submissions/", json=data)
                if res.status_code == 200:
                    st.success(f"Submitted successfully with score {score:.2f}")
                else:
                    st.error(f"Failed to submit: {res.text}")
            except Exception as e:
                st.error(f"Error connecting to backend: {e}")

elif choice == "Instructor":
    st.subheader("View Submissions")
    try:
        res = requests.get(f"{API_URL}/submissions/")
        if res.status_code == 200:
            submissions = res.json()
            if submissions:
                for sub in submissions:
                    st.write(f"**{sub['student']}**: {sub['translation']} (Score: {sub['score']:.2f})")
            else:
                st.info("No submissions yet")
        else:
            st.error(f"Failed to fetch submissions: {res.text}")
    except Exception as e:
        st.error(f"Could not connect to backend: {e}")
