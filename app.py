import streamlit as st
import sqlite3
import time
from datetime import datetime
from difflib import SequenceMatcher
import sacrebleu

# Optional semantic scoring
try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER,
            student_name TEXT,
            submission_type TEXT,
            student_text TEXT,
            time_spent REAL,
            keystrokes INTEGER,
            edit_distance INTEGER,
            bleu REAL,
            chrf REAL,
            ter REAL,
            bert_f1 REAL,
            points REAL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= UTILS =================
def compute_scores(hyp, ref):
    results = {}
    if ref.strip():
        try:
            results['BLEU'] = sacrebleu.corpus_bleu([hyp], [[ref]]).score
            results['chrF'] = sacrebleu.corpus_chrf([hyp], [[ref]]).score
            results['TER'] = sacrebleu.corpus_ter([hyp], [[ref]]).score
        except:
            results['BLEU'] = results['chrF'] = results['TER'] = None
    else:
        results['BLEU'] = results['chrF'] = results['TER'] = None

    if bert_score and ref.strip():
        try:
            P,R,F1 = bert_score([hyp],[ref],lang='en',rescale_with_baseline=True)
            results['BERT_F1'] = float(F1[0])
        except:
            results['BERT_F1'] = None
    else:
        results['BERT_F1'] = None

    # simple points: sum BLEU + BERT_F1 (0 if missing)
    points = (results['BLEU'] or 0) + (results['BERT_F1'] or 0)
    results['points'] = round(points,2)
    return results

def compute_edit_distance(a,b):
    return int(SequenceMatcher(None,a,b).ratio()*100)

def highlight_errors(student_text, reference):
    errors = []
    if not reference:
        return errors
    student_words = student_text.split()
    ref_words = reference.split()
    matcher = SequenceMatcher(None, ref_words, student_words)
    for tag, i1,i2,j1,j2 in matcher.get_opcodes():
        if tag!='equal':
            errors.append({'type':tag,'ref':' '.join(ref_words[i1:i2]),'student':' '.join(student_words[j1:j2])})
    return errors

def suggest_idioms(text):
    # very simple mock suggestions
    idioms = []
    common_idioms = ["break the ice", "hit the sack", "piece of cake", "under the weather"]
    for idiom in common_idioms:
        if idiom in text.lower():
            idioms.append(idiom)
    return idioms

# ================= APP =================
st.sidebar.title("Navigation")
role = st.sidebar.selectbox("I am a", ["Student","Instructor"])

# -------- INSTRUCTOR --------
if role=="Instructor":
    st.title("📚 Instructor Dashboard")
    menu = st.sidebar.radio("Choose Action", ["Create Exercise","View Submissions","Leaderboard"])

    if menu=="Create Exercise":
        st.subheader("Create a New Exercise")
        source = st.text_area("Source Text")
        mt_output = st.text_area("Machine Translation Output (optional)")
        reference = st.text_area("Reference Translation (optional)")
        instructor = st.text_input("Your Name")
        if st.button("Save Exercise"):
            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("INSERT INTO exercises (source, mt_output, reference, created_by) VALUES (?,?,?,?)",
                      (source, mt_output, reference, instructor))
            conn.commit()
            conn.close()
            st.success("✅ Exercise created successfully!")

    elif menu=="View Submissions":
        st.subheader("Student Submissions")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("""
            SELECT s.id,e.source,e.mt_output,e.reference,s.student_name,s.submission_type,
                   s.student_text,s.time_spent,s.keystrokes,s.edit_distance,
                   s.bleu,s.chrf,s.ter,s.bert_f1,s.points,s.submitted_at
            FROM submissions s
            JOIN exercises e ON s.exercise_id=e.id
            ORDER BY s.submitted_at DESC
        """)
        rows = c.fetchall()
        conn.close()
        for r in rows:
            st.markdown(f"""
**Student:** {r[4]}  
**Submitted At:** {r[14]}  
**Type:** {r[5]}  
**Source:** {r[1]}  
**MT Output:** {r[2]}  
**Student Submission:** {r[6]}  

📊 **Scores:**  
- BLEU: {r[10]}  
- chrF: {r[11]}  
- TER: {r[12]}  
- BERT F1: {r[13]}  
- Points: {r[14]}  

⌛ Time Spent: {r[7]} sec  
⌨️ Keystrokes: {r[8]}  
✏️ Edit Distance: {r[9]}  

⚠️ Errors: {highlight_errors(r[6],r[3])}  
💡 Idioms Detected: {suggest_idioms(r[6])}
            """)
            st.markdown("---")

    elif menu=="Leaderboard":
        st.subheader("Leaderboard")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("SELECT student_name,SUM(points) as total_points FROM submissions GROUP BY student_name ORDER BY total_points DESC")
        rows = c.fetchall()
        conn.close()
        for idx,r in enumerate(rows,1):
            st.write(f"{idx}. {r[0]} - {r[1]:.2f} points")

# -------- STUDENT --------
elif role=="Student":
    st.title("✍️ Student Exercises")
    student = st.text_input("Enter your name")
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT id,source,mt_output,reference FROM exercises ORDER BY created_at DESC")
    exercises = c.fetchall()
    conn.close()

    if not exercises:
        st.warning("⚠️ No exercises available yet.")
    else:
        choice = st.selectbox("Choose Exercise", [f"Exercise {e[0]}" for e in exercises])
        selected = exercises[int(choice.split()[1])-1]

        st.markdown(f"**Source Text:** {selected[1]}")
        if selected[2]:
            st.markdown(f"**Machine Translation:** {selected[2]}")

        submission_type = st.radio("Choose submission type", ["Edit MT Output","New Translation"])
        start_time = time.time()
        if submission_type=="Edit MT Output" and selected[2]:
            text_input = st.text_area("Edit the MT output here ✍️", value=selected[2])
        else:
            text_input = st.text_area("Write your translation here ✍️", value="")

        keystrokes = len(text_input)

        if st.button("Submit"):
            end_time = time.time()
            time_spent = round(end_time-start_time,2)
            edit_distance = compute_edit_distance(text_input, selected[2] or "")
            scores = compute_scores(text_input, selected[3] or "")

            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO submissions (exercise_id, student_name, submission_type, student_text,
                                         time_spent, keystrokes, edit_distance, bleu, chrf, ter, bert_f1, points)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,(selected[0],student,submission_type,text_input,time_spent,keystrokes,edit_distance,
                 scores['BLEU'],scores['chrF'],scores['TER'],scores['BERT_F1'],scores['points']))
            conn.commit()
            conn.close()

            st.success("✅ Submission saved!")
            st.json(scores)
            st.markdown(f"⚠️ Errors Detected: {highlight_errors(text_input, selected[3])}")
            st.markdown(f"💡 Idioms Detected: {suggest_idioms(text_input)}")
