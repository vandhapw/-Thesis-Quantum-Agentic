"""
E4 User Study — Streamlit App
Operator Decision Quality with AI-Generated Maintenance Alerts

Run with: streamlit run app.py
"""
import json
import time
import uuid
import datetime
import random
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="QASAMAP E4 — Operator Decision Study",
    page_icon="🛠️",
    layout="wide",
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"
SCENARIOS = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]

ACTION_OPTIONS = [
    "Monitor only",
    "Schedule inspection",
    "Schedule maintenance",
    "Immediate shutdown",
]


# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────
def init_state():
    if "phase" not in st.session_state:
        st.session_state.phase = "consent"
    if "rater_id" not in st.session_state:
        st.session_state.rater_id = str(uuid.uuid4())
    if "demographics" not in st.session_state:
        st.session_state.demographics = {}
    if "scenario_order" not in st.session_state:
        # Latin-square randomization: each rater sees different order
        rng = random.Random(hash(st.session_state.rater_id) & 0xFFFFFFFF)
        order = list(range(len(SCENARIOS)))
        rng.shuffle(order)
        # Assign first half to A, second half to B (counterbalanced)
        st.session_state.scenario_order = order
        st.session_state.condition_assignment = (
            ["A"] * (len(order) // 2) + ["B"] * (len(order) - len(order) // 2)
        )
        rng.shuffle(st.session_state.condition_assignment)
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
    if "responses" not in st.session_state:
        st.session_state.responses = []
    if "scenario_start_time" not in st.session_state:
        st.session_state.scenario_start_time = None
    if "tutorial_done" not in st.session_state:
        st.session_state.tutorial_done = 0


init_state()


# ─────────────────────────────────────────────
# Data persistence
# ─────────────────────────────────────────────
def save_responses():
    out_path = DATA_DIR / f"rater_{st.session_state.rater_id}.json"
    payload = {
        "rater_id": st.session_state.rater_id,
        "demographics": st.session_state.demographics,
        "responses": st.session_state.responses,
        "scenario_order": st.session_state.scenario_order,
        "condition_assignment": st.session_state.condition_assignment,
        "completed_at": datetime.datetime.now().isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


# ─────────────────────────────────────────────
# Phase: CONSENT
# ─────────────────────────────────────────────
if st.session_state.phase == "consent":
    st.title("🛠️ QASAMAP E4 — Operator Decision Study")
    st.markdown("### Pukyong National University Research Study")

    st.markdown("""
**Selamat datang / Welcome!**

You are being invited to participate in a research study by Vandha Widartha (PhD Candidate, PKNU)
on AI-generated maintenance alerts for smart manufacturing.

**What you will do:** Evaluate 20 maintenance scenarios (~30 minutes total). For each scenario,
you will read AI-generated alert info and decide what action to take.

**Risks:** Minimal. Mild cognitive fatigue. You may pause or withdraw at any time.

**Benefits:** Contribute to academic research on AI-augmented industrial decision-making.

**Confidentiality:** Anonymous. No personally-identifying information collected.

**Compensation:** Coffee voucher (~5,000 KRW equivalent) on completion.

**IRB approval:** PKNU IRB Approval # _______ (this is a pilot prior to formal IRB).

---
""")

    consent = st.checkbox("✅ I am 18+, have read the above, and voluntarily agree to participate.")
    if st.button("Start study →", disabled=not consent, type="primary"):
        st.session_state.phase = "demographics"
        st.rerun()


# ─────────────────────────────────────────────
# Phase: DEMOGRAPHICS
# ─────────────────────────────────────────────
elif st.session_state.phase == "demographics":
    st.title("Demographic Information")
    st.markdown("Please answer briefly. All responses are anonymous.")

    with st.form("demographics_form"):
        years_exp = st.selectbox(
            "Years of experience in industrial maintenance, PdM research, or smart manufacturing:",
            ["< 1 year (NOT eligible)", "1-3 years", "3-5 years", "5-10 years", "> 10 years"]
        )
        role = st.selectbox(
            "Primary role:",
            ["Maintenance technician", "Plant engineer", "PdM/AI researcher",
             "Graduate student", "Faculty", "Other"]
        )
        ai_familiarity = st.slider(
            "How familiar are you with AI/ML tools? (1=not at all, 5=expert)",
            1, 5, 3
        )
        native_lang = st.selectbox(
            "Native language:",
            ["Bahasa Indonesia", "Korean", "English", "Other"]
        )
        submitted = st.form_submit_button("Continue →", type="primary")
        if submitted:
            if "NOT eligible" in years_exp:
                st.error("Sorry, this study requires ≥1 year of relevant experience. Thank you for your interest.")
            else:
                st.session_state.demographics = {
                    "years_experience": years_exp,
                    "role": role,
                    "ai_familiarity": ai_familiarity,
                    "native_language": native_lang,
                }
                st.session_state.phase = "tutorial"
                st.rerun()


# ─────────────────────────────────────────────
# Phase: TUTORIAL
# ─────────────────────────────────────────────
elif st.session_state.phase == "tutorial":
    st.title("Tutorial — Practice Scenarios (2)")
    st.markdown("""
You will see **20 scenarios**. For each:
1. Read the alert
2. Select what action you would take (4 options)
3. Rate your confidence (1-10)

**Two alert formats** will alternate:
- **Format A**: Anomaly score + top contributing features + threshold breaches
- **Format B**: Same as A + AI-generated explanation, recommended action, and Bahasa Indonesia alert

There is no time pressure but try to decide naturally.

Let's practice with 2 scenarios.
""")

    if st.session_state.tutorial_done < 2:
        # Show one example scenario per format
        if st.session_state.tutorial_done == 0:
            cond = "A"
            st.markdown("### Tutorial 1 — Format A (ML-only)")
        else:
            cond = "B"
            st.markdown("### Tutorial 2 — Format B (Hybrid Agentic)")

        scenario = SCENARIOS[st.session_state.tutorial_done]
        cond_data = scenario[f"condition_{cond}_{'ML_only' if cond=='A' else 'hybrid_agentic'}"]
        present_data = scenario["presented_data"]

        col1, col2 = st.columns([2, 3])
        with col1:
            st.markdown(f"**Machine M-{present_data['machine_id']}** — current readings:")
            st.json(present_data["current_reading"])
        with col2:
            st.markdown("**Alert content:**")
            st.json(cond_data)

        col_action, col_conf = st.columns(2)
        with col_action:
            action = st.radio("What action would you take?", ACTION_OPTIONS, key=f"tut_action_{st.session_state.tutorial_done}")
        with col_conf:
            confidence = st.slider("Confidence (1-10)", 1, 10, 5, key=f"tut_conf_{st.session_state.tutorial_done}")

        if st.button("Submit & see correct answer", type="primary"):
            correct = scenario["ground_truth_action"]
            if action == correct:
                st.success(f"✅ Correct! Ground truth was: **{correct}**")
            else:
                st.warning(f"Ground truth was: **{correct}** (your answer: {action}). This is a tutorial — no penalty.")
            st.session_state.tutorial_done += 1
            time.sleep(2)
            st.rerun()
    else:
        st.success("Tutorial complete! You will now see 20 actual scenarios.")
        if st.button("Start main study →", type="primary"):
            st.session_state.phase = "main"
            st.session_state.scenario_start_time = time.time()
            st.rerun()


# ─────────────────────────────────────────────
# Phase: MAIN STUDY
# ─────────────────────────────────────────────
elif st.session_state.phase == "main":
    idx = st.session_state.current_idx
    if idx >= len(SCENARIOS):
        st.session_state.phase = "post_survey"
        st.rerun()

    scenario_idx = st.session_state.scenario_order[idx]
    scenario = SCENARIOS[scenario_idx]
    cond = st.session_state.condition_assignment[idx]
    cond_data = scenario[f"condition_{cond}_{'ML_only' if cond=='A' else 'hybrid_agentic'}"]
    present_data = scenario["presented_data"]

    # Header (no condition label shown to participant)
    st.title(f"Scenario {idx+1} / {len(SCENARIOS)}")
    progress = (idx + 1) / len(SCENARIOS)
    st.progress(progress)

    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown(f"**Machine M-{present_data['machine_id']}** — current readings:")
        st.json(present_data["current_reading"])
        with st.expander("History (last 8 cycles)"):
            st.json(present_data["history_8_cycles"])

    with col2:
        st.markdown("**🚨 Alert:**")
        st.json(cond_data)

    st.markdown("---")
    col_action, col_conf = st.columns(2)
    with col_action:
        action = st.radio("**What action would you take?**", ACTION_OPTIONS, key=f"action_{idx}")
    with col_conf:
        confidence = st.slider("**Confidence (1=not sure, 10=very sure)**", 1, 10, 5, key=f"conf_{idx}")

    if st.button("Submit →", type="primary", key=f"submit_{idx}"):
        elapsed = time.time() - st.session_state.scenario_start_time
        response = {
            "scenario_id": scenario["scenario_id"],
            "scenario_idx": scenario_idx,
            "condition": cond,
            "action_chosen": action,
            "ground_truth_action": scenario["ground_truth_action"],
            "is_correct": action == scenario["ground_truth_action"],
            "confidence": confidence,
            "decision_time_sec": round(elapsed, 2),
            "timestamp": datetime.datetime.now().isoformat(),
        }
        st.session_state.responses.append(response)
        save_responses()  # save after each scenario for resilience

        st.session_state.current_idx += 1
        st.session_state.scenario_start_time = time.time()
        st.rerun()


# ─────────────────────────────────────────────
# Phase: POST-SURVEY
# ─────────────────────────────────────────────
elif st.session_state.phase == "post_survey":
    st.title("Post-Study Questions")
    st.markdown("Almost done! Please answer the following.")

    with st.form("post_survey"):
        st.markdown("**Recall the two alert formats you saw:**")
        st.markdown("- **Format A**: anomaly score + top features + threshold breaches")
        st.markdown("- **Format B**: same as A + AI explanation + recommended action + alert in Bahasa Indonesia")

        useful_A = st.slider("How useful was Format A? (1=Not, 5=Very)", 1, 5, 3)
        useful_B = st.slider("How useful was Format B? (1=Not, 5=Very)", 1, 5, 3)
        trust_A = st.slider("Trust in Format A? (1=No, 10=Complete)", 1, 10, 5)
        trust_B = st.slider("Trust in Format B? (1=No, 10=Complete)", 1, 10, 5)
        preference = st.radio(
            "Which format would you prefer for daily work?",
            ["Format A (ML-only)", "Format B (Hybrid Agentic)",
             "No preference", "Both have value for different situations"]
        )
        liked = st.text_area("What did you like most about each format?")
        disliked = st.text_area("What did you find difficult or confusing?")
        comments = st.text_area("Any other comments?")

        if st.form_submit_button("Submit study →", type="primary"):
            st.session_state.post_survey = {
                "useful_A": useful_A,
                "useful_B": useful_B,
                "trust_A": trust_A,
                "trust_B": trust_B,
                "preference": preference,
                "liked": liked,
                "disliked": disliked,
                "comments": comments,
            }
            save_responses()
            st.session_state.phase = "thanks"
            st.rerun()


# ─────────────────────────────────────────────
# Phase: THANK YOU
# ─────────────────────────────────────────────
elif st.session_state.phase == "thanks":
    st.title("🎉 Thank you!")
    st.markdown(f"""
Your responses have been saved (rater ID: `{st.session_state.rater_id[:8]}…`).

**Summary of your contribution:**
- {len(st.session_state.responses)} scenarios completed
- Total responses recorded
- Your data will be analyzed in aggregate; no individual identification possible

**Compensation:**
Please email **tiodh.unej@gmail.com** with the subject *"E4 Study Compensation"* to receive your coffee voucher.
Mention rater ID prefix: `{st.session_state.rater_id[:8]}`

Thank you for your time and contribution to academic research!

— Vandha Widartha, PhD Candidate, Pukyong National University
""")
    if st.button("Start over (new participant)"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
