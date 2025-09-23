import streamlit as st
import requests
import os
import difflib
import pandas as pd

# Optional metrics
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

# -------------------------
# Configuration
# -------------------------
API_URL = os.getenv("API_URL", "https://<your-backend-service>.onrender.com")

st.set_page_config(page_title="Editing & Translation Tool", layout="centered")
st.title("Editing & Translation Tool 🎓")

# -------------------------
# Helper Functions
# -------------------------
def edit_distance(a, b):
    return int((1 - difflib.SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b), 1))

def calculate_metrics(hypothesis, reference):
    results = {}
    if sacrebleu:
        bleu = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        results["BLEU"] = round(bleu.score, 2)
    else:
        results["BLEU"] = None
    results["Edit_Distance"] = edit_distance(hypothesis, reference)
    return results

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

def fetch_submissions():
    try:
        response = requests.get(f"{API_URL}/submissions/")
        if response.status_code == 200:
            return response.json()
        st.error(f"Error fetching submissions: {response.text}")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to backend: {e}")
        return []

def post_submission(student, translation, score, time_taken):
    try:
        payload = {"student": student, "translation": translation, "score": score, "time_taken": time_taken}
        response = requests.post(f"{API_URL}/submissions/", json=payload)
        if response.status_code == 200:
            st.success("Submission added successfully")
        else:
            st.error(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to backend: {e}")

# -------------------------
# Streamlit App
# -------------------------
role = st.sidebar.radio("Select your role:", ["Student", "Instructor"])

if role == "Student":
    st.header("Student Submission")
    student_name = st.text_input("Your Name")
    reference_text = st.text_area("Reference Translation", "This is the gold standard translation.", height=100)
    translation_text = st.text_area("Your Translation", height=150)
    time_taken = st.number_input("Time Taken (seconds)", min_value=0.0, step=1.0)

    if st.button("Submit"):
        if student_name and translation_text:
            metrics = calculate_metrics(translation_text, reference_text)
            diff_text = highlight_differences(reference_text, translation_text)
            score = metrics.get("BLEU", 0) or 0
            post_submission(student_name, translation_text, score, time_taken)

            st.subheader("📊 Evaluation")
            st.json(metrics)
            st.write("🔍 Differences:")
            st.markdown(diff_text, unsafe_allow_html=True)

elif role == "Instructor":
    st.header("Instructor Dashboard")
    submissions = fetch_submissions()
    if submissions:
        df = pd.DataFrame(submissions)
        st.subheader("All Submissions")
        st.dataframe(df)
        st.download_button(
            label="📥 Download Submissions as CSV",
            data=df.to_csv(index=False),
            file_name="submissions.csv",
            mime="text/csv"
        )
    else:
        st.info("No submissions yet.")
