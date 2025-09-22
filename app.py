import streamlit as st
import requests
import pandas as pd

# --------------------------
# Backend URL
# --------------------------
API_URL = "http://127.0.0.1:8000"  # FastAPI backend running locally

# --------------------------
# App title
# --------------------------
st.set_page_config(page_title="Translation Tool", layout="wide")
st.title("Translation & Editing Training Tool 🎓✨")

# --------------------------
# Role selection
# --------------------------
role = st.sidebar.radio("Select Role", ["Student", "Instructor"])

# --------------------------
# Student View
# --------------------------
if role == "Student":
    st.header("📝 Student Submission")

    student_name = st.text_input("Enter your name")
    reference = st.text_area("Reference Translation", height=100)
    mt_output = st.text_area("Machine Translation Output", height=100)
    student_translation = st.text_area("Your Translation", height=150)

    if st.button("Submit Translation"):
        if not student_name or not reference or not student_translation:
            st.warning("Please fill all required fields!")
        else:
            payload = {
                "student_name": student_name,
                "reference": reference,
                "mt_output": mt_output,
                "student_translation": student_translation
            }
            try:
                response = requests.post(f"{API_URL}/submit/", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    st.success("✅ Submission successful!")

                    st.subheader("📊 Metrics")
                    st.json(data["metrics"])

                    st.write(f"⌨️ Edit Distance: {data['edit_distance']}")
                    st.write("🔍 Differences:", data["diff"])
                    st.write("⚠️ Errors:", data["errors"])
                    st.write("📚 Exercises:", data["exercises"])
                    st.write("💡 Collocations:", data["collocations"])
                    st.write("🗣 Idioms:", data["idioms"])
                    st.write("🎮 Fun Activity:", data["fun_activity"])
                else:
                    st.error("❌ Error submitting translation")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Could not connect to backend: {e}")

# --------------------------
# Instructor View
# --------------------------
if role == "Instructor":
    st.header("👩‍🏫 Instructor Dashboard")

    try:
        response = requests.get(f"{API_URL}/submissions/")
        if response.status_code == 200:
            submissions = response.json()
            if submissions:
                df = pd.DataFrame(submissions)
                st.subheader("All Submissions")
                st.dataframe(df)

                # Download CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Submissions",
                    data=csv,
                    file_name='submissions.csv',
                    mime='text/csv'
                )
            else:
                st.info("No submissions yet.")
        else:
            st.error("❌ Could not fetch submissions")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Could not connect to backend: {e}")
