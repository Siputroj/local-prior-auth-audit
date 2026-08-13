"""
Cotiviti Prior Authorization Audit AI System - Streamlit Web Application.

Healthcare Topic 2: Clinical Decision Making and Pattern Recognition in Health Care.
Examines Synthea FHIR JSON patient records against SNOMED-aligned coverage policies,
executes local Ollama (qwen2.5:7b) AI audits with Chain-of-Thought explainability,
and provides Human-in-the-Loop decision controls.

STRICT DESIGN RULE: Zero emojis. Minimalist modern corporate aesthetic.
"""
import datetime
import streamlit as st

from src.audit_engine import run_audit, warm_up_model, DEFAULT_MODEL
from src.cases import get_all_demo_cases, get_demo_case, get_patient_filepath
from src.fhir_parser import (
    extract_patient_summary,
    format_clinical_summary_markdown,
    load_fhir_bundle,
)
from src.policies import get_policy


# Page configuration
st.set_page_config(
    page_title="Prior Authorization Audit AI | Cotiviti Demo",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


# Minimalist Corporate CSS Styling
STYLING_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #1E293B;
}

/* Header */
.main-header {
    background: #0F172A;
    color: #FFFFFF;
    padding: 20px 28px;
    border-radius: 8px;
    margin-bottom: 20px;
}
.main-header h1 {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: #FFFFFF;
    letter-spacing: -0.01em;
}
.main-header p {
    font-size: 13px;
    color: #94A3B8;
    margin: 0;
    font-weight: 400;
}

/* Content Card */
.content-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0;
    margin-bottom: 16px;
    overflow: hidden;
}
.card-header {
    background: #F9FAFB;
    padding: 12px 18px;
    border-bottom: 1px solid #E5E7EB;
}
.card-eyebrow {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B7280;
    margin: 0 0 2px 0;
}
.card-title {
    font-size: 15px;
    font-weight: 600;
    color: #111827;
    margin: 0;
    letter-spacing: -0.01em;
}
.card-body {
    padding: 16px 18px;
}

/* Definition-style rows inside cards */
.dl-row {
    display: flex;
    flex-direction: column;
    padding: 8px 0;
    border-bottom: 1px solid #F3F4F6;
}
.dl-row:last-child {
    border-bottom: none;
}
.dl-label {
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9CA3AF;
    margin-bottom: 3px;
}
.dl-value {
    font-size: 13.5px;
    color: #1F2937;
    font-weight: 500;
    line-height: 1.5;
}
.dl-value code {
    background: #F3F4F6;
    color: #374151;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'SF Mono', Menlo, monospace;
}

/* Section subheader within a card */
.section-sub {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
    margin: 12px 0 6px 0;
    padding-top: 8px;
    border-top: 1px solid #F3F4F6;
}
.section-sub:first-child {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
}
.list-item {
    font-size: 13px;
    color: #374151;
    padding: 4px 0;
    line-height: 1.5;
}
.list-item code {
    background: #F3F4F6;
    color: #4B5563;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 11.5px;
    font-family: 'SF Mono', Menlo, monospace;
}
.list-empty {
    font-size: 12.5px;
    color: #9CA3AF;
    font-style: italic;
    padding: 4px 0;
}

/* Risk Badges */
.badge-low-risk, .badge-mod-risk, .badge-high-risk {
    display: inline-flex;
    align-items: center;
    padding: 5px 12px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 12.5px;
    letter-spacing: 0.01em;
}
.badge-low-risk {
    background-color: #ECFDF5;
    color: #065F46;
    border: 1px solid #A7F3D0;
}
.badge-low-risk::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    background-color: #10B981;
    border-radius: 50%;
    margin-right: 8px;
}
.badge-mod-risk {
    background-color: #FFFBEB;
    color: #92400E;
    border: 1px solid #FDE68A;
}
.badge-mod-risk::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    background-color: #F59E0B;
    border-radius: 50%;
    margin-right: 8px;
}
.badge-high-risk {
    background-color: #FEF2F2;
    color: #991B1B;
    border: 1px solid #FCA5A5;
}
.badge-high-risk::before {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    background-color: #EF4444;
    border-radius: 50%;
    margin-right: 8px;
}

/* Result panel */
.result-panel {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 18px 20px;
    margin-bottom: 16px;
}
.result-metric {
    display: flex;
    flex-direction: column;
}
.result-metric .rm-label {
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9CA3AF;
    margin-bottom: 6px;
}
.result-metric .rm-value {
    font-size: 15px;
    font-weight: 600;
    color: #111827;
}
.progress-bar-bg {
    background-color: #E5E7EB;
    border-radius: 4px;
    height: 6px;
    width: 100%;
    margin-top: 8px;
    overflow: hidden;
}
.progress-bar-fill {
    background-color: #2563EB;
    height: 100%;
    border-radius: 4px;
}

/* Citation Box */
.citation-box {
    background-color: #F9FAFB;
    border-left: 3px solid #0EA5E9;
    padding: 10px 14px;
    margin-bottom: 8px;
    border-radius: 0 6px 6px 0;
    font-size: 12.5px;
    color: #374151;
    line-height: 1.5;
}
.citation-box-policy {
    border-left-color: #6366F1;
}

/* CoT Step Cards */
.cot-step-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 3px solid #2563EB;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.cot-step-header {
    font-size: 10.5px;
    font-weight: 700;
    color: #1E40AF;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 5px;
}
.cot-step-body {
    font-size: 13px;
    color: #374151;
    line-height: 1.6;
}

/* Section heading */
.section-heading {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
    margin: 24px 0 12px 0;
}

/* Hide Streamlit Default Components */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Demo Case Overview Banner */
.demo-overview-card {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
    color: #F8FAFC;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}
.demo-overview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #334155;
    padding-bottom: 10px;
    margin-bottom: 10px;
}
.demo-overview-title {
    font-size: 14px;
    font-weight: 600;
    color: #F8FAFC;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.demo-overview-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
}
.badge-outcome-approve {
    background-color: #065F46;
    color: #34D399;
    border: 1px solid #059669;
}
.badge-outcome-review {
    background-color: #78350F;
    color: #FBBF24;
    border: 1px solid #D97706;
}
.badge-outcome-deny {
    background-color: #7F1D1D;
    color: #F87171;
    border: 1px solid #B91C1C;
}
.demo-overview-body {
    font-size: 13.5px;
    line-height: 1.5;
    color: #CBD5E1;
}
.demo-overview-label {
    font-weight: 600;
    color: #F8FAFC;
}
</style>
"""

st.markdown(STYLING_CSS, unsafe_allow_html=True)


# Initialize Session State
if "audit_results" not in st.session_state:
    st.session_state.audit_results = {}

if "hitl_decisions" not in st.session_state:
    st.session_state.hitl_decisions = {}

if "model_warmed" not in st.session_state:
    st.session_state.model_warmed = False
    st.session_state.warm_up_result = None


@st.cache_resource(show_spinner=False)
def _cached_warm_up(model_name):
    """Warm up the Ollama model exactly once per Streamlit session."""
    return warm_up_model(model=model_name)


def render_header():
    st.markdown(
        """
        <div class="main-header">
            <h1>Cotiviti Prior Authorization Audit AI</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_cot_steps(cot_steps):
    """Parses and renders Chain-of-Thought steps as distinct clinical cards."""
    if not cot_steps:
        st.info("No Chain-of-Thought steps available.")
        return

    paired_steps = []
    for i, step_text in enumerate(cot_steps):
        step_text = str(step_text).strip()
        if not step_text:
            continue
            
        title = f"Step {i + 1}: Clinical Evaluation"
        body = step_text

        # Try to parse 'Step 1 - Description: body'
        if step_text.lower().startswith("step "):
            if ":" in step_text:
                parts = step_text.split(":", 1)
                # Ensure title uses a colon consistently as requested
                raw_title = parts[0].strip()
                title = raw_title.replace(" - ", ": ", 1)
                body = parts[1].strip()
            elif " - " in step_text:
                parts = step_text.split(" - ", 1)
                raw_title = parts[0].strip()
                title = f"{raw_title}: Clinical Evaluation"
                body = parts[1].strip()

        if not body:
             body = "Completed evaluation step: No clinical red flags or contraindications identified on record."
             
        paired_steps.append((title, body))

    for title, body in paired_steps:
        st.markdown(
            f"""
            <div class="cot-step-card">
                <div class="cot-step-header">{title}</div>
                <div class="cot-step-body">{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar():
    st.sidebar.markdown("### Audit Control Panel")

    demo_cases = get_all_demo_cases()
    case_options = {
        f"{c['id']}: {c['patient_name']} ({c['policy_id']})": c["id"]
        for c in demo_cases
    }

    selected_label = st.sidebar.selectbox(
        "Select Case",
        options=list(case_options.keys()),
        index=0,
    )
    case_id = case_options[selected_label]
    current_case = get_demo_case(case_id)

    return current_case


def _dl_row(label, value):
    return f'<div class="dl-row"><div class="dl-label">{label}</div><div class="dl-value">{value}</div></div>'


def render_demo_overview(case):
    """Renders a high-level case objective and rationale banner for demo purposes."""
    rec = case.get("expected_recommendation", "Approve")
    tier = case.get("expected_risk_tier", "Low Risk")
    rationale = case.get("rationale", "")

    badge_class = "badge-outcome-approve"
    if "deny" in rec.lower():
        badge_class = "badge-outcome-deny"
    elif "review" in rec.lower():
        badge_class = "badge-outcome-review"

    st.markdown(
        f"""
        <div class="demo-overview-card">
            <div class="demo-overview-header">
                <span class="demo-overview-title">📋 Demonstration Guide & Expected Outcome</span>
                <span class="demo-overview-badge {badge_class}">{tier} / {rec}</span>
            </div>
            <div class="demo-overview-body">
                <span class="demo-overview-label">Clinical Rationale:</span> {rationale}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_input_cards(case, summary_dict, summary_md, policy):
    col1, col2, col3 = st.columns(3)

    with col1:
        claim = case["claim"]
        rows = "".join([
            _dl_row("Claim ID", f"<code>{case['id']}</code>"),
            _dl_row("Patient", case["patient_name"]),
            _dl_row("Requested Item", claim["procedure"]),
            _dl_row("SNOMED / RxNorm", f"<code>{claim['snomed_code']}</code>"),
            _dl_row("Requesting Provider", claim["requesting_provider"]),
            _dl_row("Reason", claim["reason"]),
        ])
        st.markdown(
            f"""
            <div class="content-card">
                <div class="card-header">
                    <div class="card-eyebrow">Card A</div>
                    <div class="card-title">Prior Authorization Claim</div>
                </div>
                <div class="card-body">{rows}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        d = summary_dict["demographics"]
        demo_val = f"{d['age']}y {d['gender']} &middot; DOB {d['birth_date']}"

        cond_items = "".join([
            f'<div class="list-item">{c["display"]} <code>SNOMED: {c["snomed_code"]}</code></div>'
            for c in summary_dict["active_conditions"][:4]
        ]) or '<div class="list-empty">None on record</div>'

        if summary_dict["medications_active"]:
            med_items = "".join([
                f'<div class="list-item">{m["display"]} <code>RxNorm: {m["rxnorm_code"]}</code></div>'
                for m in summary_dict["medications_active"][:3]
            ])
        else:
            med_items = '<div class="list-empty">None on record</div>'

        proc_items = "".join([
            f'<div class="list-item">{p["display"]} <code>{p["date"]}</code></div>'
            for p in summary_dict["procedures"][:3]
        ]) or '<div class="list-empty">None on record</div>'

        st.markdown(
            f"""
            <div class="content-card">
                <div class="card-header">
                    <div class="card-eyebrow">Card B</div>
                    <div class="card-title">Patient FHIR Clinical History</div>
                </div>
                <div class="card-body">
                    {_dl_row("Demographics", demo_val)}
                    <div class="section-sub">Active Diagnoses ({len(summary_dict['active_conditions'])})</div>
                    {cond_items}
                    <div class="section-sub">Active Medications ({len(summary_dict['medications_active'])})</div>
                    {med_items}
                    <div class="section-sub">Recent Procedures ({len(summary_dict['procedures'])})</div>
                    {proc_items}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        crit_items = "".join([
            f'<div class="list-item"><code>{crit["id"]}</code> &middot; {crit["description"]}</div>'
            for crit in policy["mandatory_criteria"]
        ])

        st.markdown(
            f"""
            <div class="content-card">
                <div class="card-header">
                    <div class="card-eyebrow">Card C &middot; {policy["id"]}</div>
                    <div class="card-title">Coverage Policy</div>
                </div>
                <div class="card-body">
                    {_dl_row("Policy Title", policy["title"])}
                    {_dl_row("Domain", policy["domain"])}
                    {_dl_row("Version", f"{policy['version']} (Effective {policy['effective_date']})")}
                    <div class="section-sub">Mandatory Criteria</div>
                    {crit_items}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_audit_section(case, summary_dict, summary_md, policy):
    st.markdown('<div class="section-heading">AI Audit Execution</div>', unsafe_allow_html=True)

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        run_button = st.button("Run Local AI Audit", type="primary", use_container_width=True)

    case_id = case["id"]

    if run_button or case_id in st.session_state.audit_results:
        if run_button:
            with st.spinner(f"Executing local Ollama ({DEFAULT_MODEL}) clinical audit..."):
                audit_res = run_audit(case)
                st.session_state.audit_results[case_id] = {"audit": audit_res}

        stored_data = st.session_state.audit_results[case_id]
        audit_res = stored_data["audit"]

        if audit_res["status"] != "success":
            st.error(f"Audit Error: {audit_res.get('error_message')}")
            return

        parsed = audit_res["parsed_json"]
        risk_tier = parsed.get("risk_tier", "Moderate Risk")
        confidence = parsed.get("confidence_score", 50)
        recommendation = parsed.get("recommendation", "Manual Review Required")

        # Results Header - clean 3-column layout
        res_col1, res_col2, res_col3 = st.columns([2, 2, 2])

        with res_col1:
            if risk_tier == "Low Risk":
                badge_html = f'<div class="badge-low-risk">LOW RISK &middot; {recommendation}</div>'
            elif risk_tier == "High Risk":
                badge_html = f'<div class="badge-high-risk">HIGH RISK &middot; {recommendation}</div>'
            else:
                badge_html = f'<div class="badge-mod-risk">MODERATE RISK &middot; {recommendation}</div>'

            st.markdown(
                f"""
                <div class="result-panel">
                    <div class="result-metric">
                        <div class="rm-label">AI Risk Classification</div>
                        {badge_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with res_col2:
            st.markdown(
                f"""
                <div class="result-panel">
                    <div class="result-metric">
                        <div class="rm-label">Model Confidence (self-reported)</div>
                        <div class="rm-value">{confidence}%</div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: {confidence}%;"></div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with res_col3:
            st.markdown(
                f"""
                <div class="result-panel">
                    <div class="result-metric">
                        <div class="rm-label">Inference Latency</div>
                        <div class="rm-value">{audit_res.get('latency_seconds', 0)}s <span style="font-size:12px; font-weight:400; color:#9CA3AF;">local Ollama</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Chain-of-Thought Reasoning
        with st.expander("Chain-of-Thought Clinical Reasoning", expanded=True):
            cot_steps = parsed.get("chain_of_thought", [])
            render_cot_steps(cot_steps)

        # Verbatim Citations & Evidence
        ev_col1, ev_col2 = st.columns(2)

        with ev_col1:
            st.markdown('<div class="section-heading" style="margin-top:8px;">Policy Citations</div>', unsafe_allow_html=True)
            policy_quotes = parsed.get("policy_verbatim_citations", [])
            if policy_quotes:
                for q in policy_quotes:
                    st.markdown(
                        f'<div class="citation-box citation-box-policy">"{q}"</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No explicit policy citations returned.")

        with ev_col2:
            st.markdown('<div class="section-heading" style="margin-top:8px;">Patient Record Citations</div>', unsafe_allow_html=True)
            patient_quotes = parsed.get("patient_record_verbatim_citations", [])
            if patient_quotes:
                for q in patient_quotes:
                    st.markdown(
                        f'<div class="citation-box">"{q}"</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No explicit patient citations returned.")

        # Auditor Notes & Clinical Gaps (AI Rationale Summary)
        st.markdown('<div class="section-heading">Auditor Notes & Clinical Gaps (AI Rationale)</div>', unsafe_allow_html=True)
        rule_rationale = parsed.get("rule_rationale")
        if not rule_rationale:
            # Fallback to first Chain-of-Thought step if rule_rationale is missing
            cot_steps = parsed.get("chain_of_thought", [])
            rule_rationale = cot_steps[0] if cot_steps else "No clinical rationale provided."
            
        risk_tier = parsed.get("risk_tier", "Low Risk")
        
        if "high risk" in risk_tier.lower():
            st.error(f"**High Risk:** {rule_rationale}")
        elif "moderate risk" in risk_tier.lower():
            st.warning(f"**Moderate Risk:** {rule_rationale}")
        else:
            st.success(f"**Low Risk:** {rule_rationale}")


def render_hitl_section(case):
    st.markdown('<div class="section-heading">Reviewer Panel</div>', unsafe_allow_html=True)

    case_id = case["id"]
    existing_decision = st.session_state.hitl_decisions.get(case_id, {})

    h_col1, h_col2 = st.columns([2, 1])

    with h_col1:
        reviewer_notes = st.text_area(
            "Auditor Notes / Clinical Rationale",
            value=existing_decision.get("notes", ""),
            placeholder="Enter human auditor notes or justification for override...",
            height=100,
        )

    with h_col2:
        st.markdown("**Reviewer Action**")
        btn_approve = st.button("Approve Claim", use_container_width=True)
        btn_deny = st.button("Deny Claim", use_container_width=True)
        btn_info = st.button("Request More Info", use_container_width=True)

        action_taken = None
        if btn_approve:
            action_taken = "APPROVED"
        elif btn_deny:
            action_taken = "DENIED"
        elif btn_info:
            action_taken = "INFO REQUESTED"

        if action_taken:
            st.session_state.hitl_decisions[case_id] = {
                "action": action_taken,
                "notes": reviewer_notes,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    current_hitl = st.session_state.hitl_decisions.get(case_id)
    if current_hitl:
        st.success(
            f"HITL Decision Recorded: **{current_hitl['action']}** by Auditor at {current_hitl['timestamp']}. "
            f"Notes: '{current_hitl['notes']}'"
        )


def main():
    render_header()

    # Warm up the Ollama model once per session to eliminate cold-start
    # latency on the first audit call.
    if not st.session_state.model_warmed:
        with st.spinner(f"Loading local Ollama model ({DEFAULT_MODEL}) into memory..."):
            st.session_state.warm_up_result = _cached_warm_up(DEFAULT_MODEL)
            st.session_state.model_warmed = True

    case = render_sidebar()

    fpath = get_patient_filepath(case)
    bundle = load_fhir_bundle(fpath)
    summary_dict = extract_patient_summary(bundle)
    summary_md = format_clinical_summary_markdown(summary_dict)
    policy = get_policy(case["policy_id"])

    render_demo_overview(case)
    render_input_cards(case, summary_dict, summary_md, policy)
    render_audit_section(case, summary_dict, summary_md, policy)
    render_hitl_section(case)


if __name__ == "__main__":
    main()
