import streamlit as st
import time
import difflib
import Levenshtein
import pandas as pd

# Safe imports for metrics
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

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

# Input reference and machine translation
reference = st.text_area("Reference Translation", "This is the gold standard translation.", height=100)
mt_output = st.text_area("Machine Translation Output", "This is machine translation.", height=100)

# Student translation mode
mode = st.radio("Choose Translation Mode:", ["Edit Machine Translation", "Write From Scratch"])

student_translation = ""
if mode == "Edit Machine Translation":
    student_translation = st.text_area("Edit the Machine Translation:", mt_output, height=150)
else:
    student_translation = st.text_area("Write Your Own Translation:", "", height=150)

# Track keystrokes, edits, and time
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

if st.button("Submit Translation"):
    end_time = time.time()
    duration = round(end_time - st.session_state.start_time, 2)

    # Metrics
    metrics = calculate_metrics(student_translation, reference)

    # Edit distance
    edit_distance = Levenshtein.distance(student_translation, reference)

    # Differences
    diff_text = highlight_differences(reference, student_translation)

    # Error classification
    errors = classify_errors(student_translation, reference)

    # Display results
    st.subheader("📊 Translation Evaluation")
    st.json(metrics)

    st.write(f"⏱️ Time Taken: **{duration} seconds**")
    st.write(f"⌨️ Edit Distance: **{edit_distance}**")
    st.write("🔍 Differences:")
    st.markdown(diff_text, unsafe_allow_html=True)

    if errors:
        st.write("⚠️ Errors Detected:")
        for e in errors:
            st.write(f"- {e}")
    else:
        st.write("✅ No major errors found!")

    # Leaderboard
    if "leaderboard" not in st.session_state:
        st.session_state.leaderboard = []

    score = metrics.get("BLEU", 0) or 0
    st.session_state.leaderboard.append({
        "Student": f"Student {len(st.session_state.leaderboard)+1}",
        "Score": score,
        "Time": duration
    })

    df = pd.DataFrame(st.session_state.leaderboard)
    df = df.sort_values(by=["Score"], ascending=False)
    st.subheader("🏆 Leaderboard")
    st.table(df)

    # Fun gamification badges
    if score > 70:
        st.success("🌟 Badge Earned: Master Translator!")
    elif score > 40:
        st.info("⭐ Badge Earned: Rising Translator!")
    else:
        st.warning("💡 Keep Practicing to earn badges!")
