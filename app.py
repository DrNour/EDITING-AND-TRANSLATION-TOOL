import streamlit as st
import sqlite3
import time
from datetime import datetime
from difflib import SequenceMatcher

# --- Crash-proof imports ---
try:
    import sacrebleu
except ImportError:
    sacrebleu = None
    st.warning("⚠️ sacrebleu not installed, BLEU/chrF/TER disabled.")

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None
    st.warning("⚠️ bert-score not installed, semantic scoring disabled.")

# ====== DATABASE SETUP ======
def init_db():
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    # Exercises table
    c.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            mt_output TEXT,
            reference TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Submissions table
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER,
            student_name TEXT,
            submission_type TEXT,
            text TEXT,
            time_spent REAL,
            keystrokes INTEGER,
            edit_distance INTEGER,
            bleu REAL,
            chrf REAL,
            ter REAL,
            bert_f1 REAL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ====== UTILS ======
def compute_edit_distance(s1, s2):
    return int(sum(1 for i in SequenceMatcher(None, s1, s2).get_opcodes() if i[0] != 'equal'))

def compute_scores(hypothesis, reference):
    results = {"BLEU": None, "chrF": None, "TER": None, "BERT_F1": None}

    if sacrebleu and reference.strip():
        try:
            results["BLEU"] = sacrebleu.corpus_bleu([hypothesis], [[reference]]).score
            results["chrF"] = sacrebleu.corpus_chrf([hypothesis], [[reference]]).score
            results["TER"] = sacrebleu.corpus_ter([hypothesis], [[reference]]).score
        except:
            pass

    if bert_score and reference.strip():
        try:
            P, R, F1 = bert_score([hypothesis], [reference], lang="en", rescale_with_baseline=True)
            results["BERT_F1"] = float(F1[0])
        except:
            pass

    return results

# ====== APP ======
st.sidebar.title("Navigation")
role = st.sidebar.selectbox("I am a", ["Student", "Instructor"])

if role == "Instructor":
    st.title("📚 Instructor Dashboard")
    menu = st.sidebar.radio("Choose Action", ["Create Exercise", "View Submissions", "Leaderboard"])

    if menu == "Create Exercise":
        st.subheader("Create a New Exercise")
        source = st.text_area("Source Text")
        mt_output = st.text_area("Machine Translation Output (optional)")
        reference = st.text_area("Reference Translation (optional)")
        instructor_name = st.text_input("Instructor Name")

        if st.button("Save Exercise"):
            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("INSERT INTO exercises (source, mt_output, reference, created_by) VALUES (?,?,?,?)",
                      (source, mt_output, reference, instructor_name))
            conn.commit()
            conn.close()
            st.success("✅ Exercise created!")

    elif menu == "View Submissions":
        st.subheader("Student Submissions")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("""
            SELECT s.id, s.student_name, s.submission_type, s.text, s.time_spent, s.keystrokes, s.edit_distance,
                   s.bleu, s.chrf, s.ter, s.bert_f1, e.source, e.mt_output, e.reference
            FROM submissions s
            JOIN exercises e ON s.exercise_id = e.id
            ORDER BY s.submitted_at DESC
        """)
        rows = c.fetchall()
        conn.close()

        for r in rows:
            st.markdown(f"""
**Student:** {r[1]}  
**Submitted as:** {r[2]}  
**Source Text:** {r[11]}  
**MT Output:** {r[12]}  
**Student Submission:** {r[3]}  
**Reference:** {r[13]}  

⌛ Time Spent: {r[4]} sec  
⌨️ Keystrokes: {r[5]}  
✏️ Edit Distance: {r[6]}  

📊 Scores:
- BLEU: {r[7]}
- chrF: {r[8]}
- TER: {r[9]}
- BERT_F1: {r[10]}
""")
            st.markdown("---")

    elif menu == "Leaderboard":
        st.subheader("Leaderboard")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("SELECT student_name, SUM(COALESCE(bleu,0)+COALESCE(bert_f1,0)) as total_score FROM submissions GROUP BY student_name ORDER BY total_score DESC")
        leaderboard = c.fetchall()
        conn.close()
        for idx, student in enumerate(leaderboard, 1):
            st.write(f"{idx}. {student[0]} - Score: {student[1]:.2f}")

elif role == "Student":
    st.title("✍️ Student Submission")
    student_name = st.text_input("Your Name")
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT id, source, mt_output, reference FROM exercises ORDER BY created_at DESC")
    exercises = c.fetchall()
    conn.close()

    if not exercises:
        st.warning("⚠️ No exercises available yet.")
    else:
        choice = st.selectbox("Choose Exercise", [f"Exercise {e[0]}" for e in exercises])
        selected = exercises[int(choice.split()[1])-1]

        st.markdown(f"**Source:** {selected[1]}")
        st.markdown(f"**MT Output:** {selected[2]}")

        submission_type = st.radio("Submission Type", ["Edit MT", "Add Your Translation"])
        student_text = st.text_area("Your Translation Here", value=selected[2] if submission_type=="Edit MT" else "")

        start_time = time.time()
        keystrokes = len(student_text)

        if st.button("Submit"):
            end_time = time.time()
            time_spent = round(end_time - start_time,2)
            edit_dist = compute_edit_distance(student_text, selected[2] if submission_type=="Edit MT" else "")

            scores = compute_scores(student_text, selected[3] or "")

            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO submissions (exercise_id, student_name, submission_type, text, time_spent, keystrokes, edit_distance, bleu, chrf, ter, bert_f1)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (selected[0], student_name, submission_type, student_text, time_spent, keystrokes, edit_dist,
                  scores.get("BLEU"), scores.get("chrF"), scores.get("TER"), scores.get("BERT_F1")))
            conn.commit()
            conn.close()
            st.success("✅ Submission saved!")
            st.json(scores)
