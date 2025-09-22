import os
import streamlit as st
import pandas as pd
import requests
import time
import difflib
import Levenshtein

# -------------------------
# Configuration
# -------------------------
API_URL = "https://editing-and-translation-tool.onrender.com"
# -------------------------
# Helper Functions
# -------------------------
def highlight_differences(original, edited):
    diff = difflib.ndiff(original.split(), edited.split())
    highlighted = []
    for word in diff:
        if word.startswith("+"):
            highlighted.append(f"🟢 **{word[2:]}**")
        elif word.startswith("-"):
            highlighted.append(f"🔴 ~~{word[2:]}~~")
        else:
            highlighted.append(word[2:])
    return " ".join(highlighted)

def calculate_score(student_translation, reference):
    # Basic BLEU-like score (replace with backend metrics if needed)
    edit_distance = Levenshtein.distance(student_translation, reference)
    score = max(0, 100 - edit_distance)
    return round(score, 2)

# -------------------------
# App Interface
# -------------------------
st.title("Translation & Editing Training Tool 🎓✨")

role = st.radio("Select Role:", ["Student", "Instructor"])

# -------------------------
# Student Interface
# -------------------------
if role == "Student":
    student_name = st.text_input("Your Name", "")
    reference = st.text_area("Reference Translation", "This is the gold standard translation.", height=100)
    mt_output = st.text_area("Machine Translation Output", "This is machine translation.", height=100)

    mode = st.radio("Choose Translation Mode:", ["Edit Machine Translation", "Write From Scratch"])
    if mode == "Edit Machine Translation":
        student_translation = st.text_area("Edit the Machine Translation:", mt_output, height=150)
    else:
        student_translation = st.text_area("Write Your Own Translation:", "", height=150)

    if st.button("Submit Translation"):
        if not student_name.strip():
            st.warning("Please enter your name.")
        else:
            score = calculate_score(student_translation, reference)
            diff_text = highlight_differences(reference, student_translation)

            st.subheader("📊 Translation Evaluation")
            st.write(f"Score: **{score}**")
            st.write("🔍 Differences:")
            st.markdown(diff_text, unsafe_allow_html=True)

            # Send submission to backend
            payload = {
                "student_name": student_name,
                "reference": reference,
                "mt_output": mt_output,
                "student_translation": student_translation,
                "score": score,
                "timestamp": time.time()
            }
            try:
                response = requests.post(f"{API_URL}/submit/", json=payload)
                if response.status_code == 200:
                    st.success("✅ Submission sent to instructor.")
                else:
                    st.error(f"Error submitting: {response.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to backend: {e}")

# -------------------------
# Instructor Interface
# -------------------------
else:
    st.subheader("Instructor Dashboard")

    # Fetch submissions from backend
    try:
        response = requests.get(f"{API_URL}/submissions/")
        if response.status_code == 200:
            submissions = response.json()
            if submissions:
                df = pd.DataFrame(submissions)
                st.table(df)

                # Download CSV
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Submissions CSV",
                    data=csv,
                    file_name="submissions.csv",
                    mime="text/csv"
                )
            else:
                st.info("No submissions yet.")
        else:
            st.error(f"Error fetching submissions: {response.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to backend: {e}")

