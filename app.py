import streamlit as st
import time
import difflib
import pandas as pd
import requests
import Levenshtein
import os

# Optional metrics imports
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

# -------------------------
# Configuration
# -------------------------
API_URL = os.getenv("API_URL")
if not API_URL:
    st.error("API_URL environment variable is not set!")
    st.stop()

# -------------------------
# Helper Functions
# -------------------------
def calculate_metrics(hypothesis, reference):
    results = {}
    if sacrebleu:
        bleu = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        chrf = sacrebleu.corpus_chrf([hypothesis], [[reference]])
        ter = sacrebleu.corpus_ter([hypothesis], [[reference]])
        results["BLEU"] = round(bleu.score, 2)
        results["chrF"] = round(chrf.score, 2)
        results["TER"] = round(ter.score, 2)
    else:
        results["BLEU"] = None
        results["chrF"] = None
        results["TER"] = None
    if bert_score:
        P, R, F1 = bert_score([hypothesis], [reference], lang="en", verbose=False)
        results["BERT_F1"] = round(F1.mean().item() * 100, 2)
    else:
        results["BERT_F1"] = None
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

def classify_errors(hypothesis, reference):
    errors = []
    hyp_words = hypothesis.split()
    ref_words = reference.split()
    for i, word in enumerate(hyp_words):
        if i < len(ref_words) and word != ref_words[i]:
            errors.append(f"Word mismatch: '{word}' vs '{ref_words[i]}'")
    return errors

# -------------------------
# Streamlit App
# -------------------------
st.title("Translation & Editing Training Tool 🎓✨")

role = st.radio("Select Role:", ["Student", "Instructor"])

# -------------------------
# Student Interface
# -------------------------
if role == "Student":
    reference = st.text_area("Reference Translation", "This is the gold standard translation.", height=100)
    mt_output = st.text_area("Machine Translation Output", "This is machine translation.", height=100)
    mode = st.radio("Choose Translation Mode:", ["Edit Machine Translation", "Write From Scratch"])

    if mode == "Edit Machine Translation":
        student_translation = st.text_area("Edit the Machine Translation:", mt_output, height=150)
    else:
        student_translation = st.text_area("Write Your Own Translation:", "", height=150)

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    if st.button("Submit Translation"):
        duration = round(time.time() - st.session_state.start_time, 2)
        metrics = calculate_metrics(student_translation, reference)
        edit_distance = Levenshtein.distance(student_translation, reference)
        diff_text = highlight_differences(reference, student_translation)
        errors = classify_errors(student_translation, reference)

        st.subheader("📊 Translation Evaluation")
        st.json(metrics)
        st.write(f"⏱️ Time Taken: **{duration} seconds**")
        st.write(f"⌨️ Edit Distance: **{edit_distance}**")
        st.markdown("🔍 Differences:")
        st.markdown(diff_text, unsafe_allow_html=True)

        if errors:
            st.write("⚠️ Errors Detected:")
            for e in errors:
                st.write(f"- {e}")
        else:
            st.write("✅ No major errors found!")

        # Send submission to backend
        try:
            payload = {
                "student_name": f"Student {int(time.time())}",
                "reference": reference,
                "mt_output": mt_output,
                "student_translation": student_translation,
                "score": metrics.get("BLEU", 0) or 0,
                "timestamp": time.time()
            }
            response = requests.post(f"{API_URL}/submit/", json=payload)
            if response.status_code == 200:
                st.success("✅ Submission saved successfully!")
            else:
                st.error(f"Error saving submission: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Could not connect to backend: {e}")

# -------------------------
# Instructor Interface
# -------------------------
elif role == "Instructor":
    st.header("Instructor Dashboard")
    try:
        response = requests.get(f"{API_URL}/submissions/")
        response.raise_for_status()
        submissions = response.json()

        if submissions:
            df = pd.DataFrame(submissions)
            st.table(df)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Submissions CSV", csv, file_name="submissions.csv")
        else:
            st.info("No submissions yet.")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not fetch submissions: {e}")
