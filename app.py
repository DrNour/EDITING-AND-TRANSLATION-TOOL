import streamlit as st
import pandas as pd
import random
import difflib
import Levenshtein
import os

# Optional metrics (if installed)
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

# -----------------------
# Helper Functions
# -----------------------
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
            highlighted.append(f"[+]{word[2:]}")
        elif word.startswith("-"):
            highlighted.append(f"[-]{word[2:]}")
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

def generate_exercises(errors, text):
    exercises = []
    for e in errors:
        exercises.append(f"Correct this: {e}")
    # Dynamic exercise example
    words = text.split()
    if len(words) > 5:
        sample_words = random.sample(words, 2)
        masked = " ".join(["____" if w in sample_words else w for w in words])
        exercises.append(f"Fill in the blanks: {masked}")
    return exercises or ["Rewrite the translation."]

def generate_collocations(text):
    words = text.split()
    collos = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
    return collos[:3]

def generate_idioms():
    idioms = [
        "Break the ice – to start a conversation.",
        "Hit the books – to study hard.",
        "Under the weather – feeling sick."
    ]
    return random.sample(idioms, 2)

def fun_activity():
    activities = [
        "Create a short story using 'break the ice'.",
        "Translate a proverb into English.",
        "Read aloud and record yourself."
    ]
    return random.choice(activities)

# -----------------------
# Streamlit App
# -----------------------
st.title("Translation & Editing Tool")

role = st.sidebar.selectbox("Select Role", ["Student", "Instructor"])

if role == "Student":
    student_name = st.text_input("Your Name")
    reference = st.text_area("Reference Translation")
    mt_output = st.text_area("Machine Translation Output")
    student_translation = st.text_area("Your Translation")

    if st.button("Submit"):
        if student_translation.strip() == "":
            st.warning("Enter a translation first.")
        else:
            metrics = calculate_metrics(student_translation, reference)
            edit_distance = Levenshtein.distance(student_translation, reference)
            diff_text = highlight_differences(reference, student_translation)
            errors = classify_errors(student_translation, reference)
            exercises = generate_exercises(errors, student_translation)
            collos = generate_collocations(student_translation)
            idioms = generate_idioms()
            activity = fun_activity()

            # Display results
            st.subheader("Metrics")
            st.json(metrics)
            st.write(f"Edit Distance: {edit_distance}")
            st.write("Differences:", diff_text)
            st.write("Errors:", errors)
            st.write("Exercises:")
            for ex in exercises:
                st.write(f"- {ex}")
            st.write("Collocations:", collos)
            st.write("Idioms:", idioms)
            st.write("Fun Activity:", activity)

            # Save submission
            new_data = {
                "Student": student_name,
                "Reference": reference,
                "MT Output": mt_output,
                "Translation": student_translation,
                "BLEU": metrics.get("BLEU"),
                "Edit Distance": edit_distance,
                "Errors": "; ".join(errors)
            }
            if os.path.exists("submissions.csv"):
                df = pd.read_csv("submissions.csv")
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            else:
                df = pd.DataFrame([new_data])
            df.to_csv("submissions.csv", index=False)
            st.success("Submission saved!")

elif role == "Instructor":
    st.subheader("Instructor Dashboard")
    if os.path.exists("submissions.csv"):
        df = pd.read_csv("submissions.csv")
        st.dataframe(df)
        st.download_button(
            label="Download Submissions",
            data=df.to_csv(index=False),
            file_name="submissions.csv",
            mime="text/csv"
        )
    else:
        st.info("No submissions yet.")
