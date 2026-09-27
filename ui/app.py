"""A local passenger-facing demo; forms collect facts and the API owns all assessment logic."""

from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from copilot.api.client import assess_remote, fetch_model_status
from copilot.schemas.flight import DISCLAIMER, CopilotResponse
from copilot.schemas.requests import CopilotRequest, IntakeFacts

TEXT_FIELDS = {
    "airline": "Operating airline (code preferred, e.g. LH)",
    "flight_number": "Flight number (optional)",
    "departure_airport": "Departure airport code (e.g. FRA)",
    "arrival_airport": "Arrival airport code (e.g. CDG)",
    "flight_date": "Flight date (YYYY-MM-DD)",
    "scheduled_departure": "Scheduled departure, local time (YYYY-MM-DDTHH:MM, optional)",
    "scheduled_arrival": "Scheduled arrival (YYYY-MM-DDTHH:MM, optional)",
    "airline_reason": "Reason given by the airline",
    "arrival_delay_minutes": "Actual delay at final arrival (minutes)",
    "cancellation_notice_days": "Days of notice before cancellation",
    "one_way_fare_usd": "Actual one-way fare (USD)",
    "rerouting_departure_advance_minutes": "Alternative departure: minutes earlier (- if later)",
    "rerouting_arrival_delay_minutes": "Alternative planned arrival: minutes later (- if earlier)",
}
BOOL_FIELDS = {
    "is_eu_carrier": "Is the operating airline an EU carrier?",
    "was_rerouted": "Was alternative travel offered?",
    "volunteered_seat": "Did you volunteer to give up your seat?",
    "denied_due_to_overbooking": "Were you denied boarding due to overbooking?",
    "met_checkin_requirements": "Valid documents, reservation and on-time check-in?",
    "declined_alternative_travel": "Did you decline alternative travel AND vouchers or credits?",
}


def copy_facts() -> None:
    """Preserve known facts when moving from extracted prose to editable follow-up fields."""
    response = st.session_state.get("result")
    if response is None:
        return
    facts = dict(response.collected_facts)
    facts.update(facts.pop("flight", {}))
    for key in TEXT_FIELDS:
        st.session_state[key] = str(facts[key]) if facts.get(key) is not None else ""
    for key in BOOL_FIELDS:
        value = facts.get(key)
        st.session_state[key] = "Not sure" if value is None else "Yes" if value else "No"
    st.session_state["disruption_type"] = facts.get("disruption_type") or "delay"
    st.session_state["mode"] = "Flight details"


def render_result(result: CopilotResponse) -> None:
    """Keep unresolved entitlement and prediction uncertainty visible beside any draft."""
    st.subheader("Your assessment")
    labels = {
        "complete": "Assessment complete",
        "needs_information": "More information needed",
        "review_required": "Manual review needed",
        "error": "Assessment unavailable",
    }
    st.info(labels[result.status])
    for warning in result.warnings:
        st.warning(warning)
    for question in result.questions:
        st.write(f"• {question}")
    if result.collected_facts:
        st.button("Edit facts / answer questions", on_click=copy_facts)
    assessments = (
        [result.eligibility] if result.eligibility else []
    ) + result.additional_assessments
    for assessment in assessments:
        name = assessment.regulation.value.upper() if assessment.regulation else "Coverage"
        st.markdown(f"**{name}**")
        st.write(assessment.reasoning)
        if assessment.review_required:
            st.warning("Review the circumstances and supporting evidence before using this result.")
        if assessment.compensation_amount is not None:
            st.metric(
                "Estimated compensation",
                f"{assessment.compensation_currency} {assessment.compensation_amount:,.2f}",
            )
        if assessment.refund_eligible is not None:
            st.write(
                "Refund supported by supplied facts."
                if assessment.refund_eligible
                else "Refund not established by supplied facts."
            )
    if result.delay_prediction:
        prediction = result.delay_prediction
        st.subheader("Delay prediction — separate from passenger rights")
        st.warning(
            "Data source: "
            + ("REAL BTS" if prediction.data_source == "bts" else prediction.data_source.upper())
        )
        st.metric(
            "Estimated chance of arrival delay of 15+ minutes",
            f"{prediction.probability_delayed:.0%}",
        )
        for limitation in prediction.limitations:
            st.caption(limitation)
    if result.claim_letter:
        st.subheader("Draft claim letter")
        st.caption("Check every fact and replace personal placeholders before using this draft.")
        st.text_area("Draft for review", result.claim_letter, height=300, disabled=True)
        st.download_button(
            "Download original draft",
            result.claim_letter,
            file_name="claim-draft.txt",
            mime="text/plain",
        )
    st.caption(result.disclaimer)


def main() -> None:
    """Submit only explicit user actions; rerenders must never trigger extra model calls."""
    st.set_page_config(page_title="Flight Disruption Copilot", page_icon="✈", layout="wide")
    # LEARN: Load a local stylesheet rather than remote assets, keeping the demo
    # self-contained. Only static, developer-authored markup is rendered as HTML.
    st.html("<style>" + Path(__file__).with_name("styles.css").read_text() + "</style>")
    st.html("""
        <div class="brand"><span class="brand-mark" aria-hidden="true">↗</span>
        <span>Flight Disruption Copilot</span>
        <span class="brand-note">Passenger clarity</span></div>
        <section class="hero"><div class="eyebrow">A clearer way forward</div>
        <h1>Disrupted flight.<br>Understand your options.</h1>
        <p>A little clarity when travel doesn’t go to plan. Check your passenger rights,
        understand the next steps, and prepare a considered claim.</p></section>
    """)
    st.caption(DISCLAIMER)
    model = fetch_model_status()
    if model.data_source == "synthetic":
        st.warning("Delay model: " + model.message)
    else:
        st.info("Delay model: " + model.message)
    mode = st.radio(
        "How would you like to start?",
        ["Flight details", "Describe what happened"],
        key="mode",
        horizontal=True,
    )
    st.caption(
        "Flight details work without an AI key. Descriptions are sent to the configured "
        "AI provider; avoid passport numbers, booking references, and other personal details."
    )
    with st.form("assessment"):
        values = {}
        text = None
        if mode == "Describe what happened":
            text = st.text_area("Describe your flight and what happened", max_chars=12000)
        else:
            st.caption(
                "Leave unknown values blank. Use actual final-arrival delay, not departure "
                "delay. For alternatives, use the offered schedule."
            )
            st.html('<div class="section-label">01 / Your journey</div>')
            columns = st.columns(2, gap="medium")
            for index, (key, label) in enumerate(list(TEXT_FIELDS.items())[:5]):
                with columns[index % 2]:
                    values[key] = st.text_input(label, key=key)
            with columns[1]:
                values["disruption_type"] = st.selectbox(
                    "Disruption",
                    ["delay", "cancellation", "denied_boarding"],
                    key="disruption_type",
                )
            with st.expander("Timing and airline explanation", expanded=True):
                timing_columns = st.columns(2, gap="medium")
                for index, (key, label) in enumerate(list(TEXT_FIELDS.items())[5:]):
                    with timing_columns[index % 2]:
                        values[key] = st.text_input(label, key=key)
            with st.expander("Coverage, boarding and refund details"):
                for key, label in BOOL_FIELDS.items():
                    answer = st.selectbox(label, ["Not sure", "Yes", "No"], key=key)
                    values[key] = {"Not sure": None, "Yes": True, "No": False}[answer]
        st.html('<div class="section-label">02 / Your assessment</div>')
        want_letter = st.checkbox("Prepare a draft claim letter when supported", value=True)
        want_prediction = st.checkbox("Include a delay prediction (US domestic flights only)")
        allow_synthetic = st.checkbox("Allow synthetic-data prediction for demonstration only")
        submitted = st.form_submit_button(
            "Assess my flight", type="primary", use_container_width=True
        )
    if submitted:
        # LEARN: Session state survives Streamlit reruns for this browser session.
        # Clear the previous result before validation so an invalid new submission
        # cannot leave an old compensation award looking like the latest answer.
        st.session_state.pop("result", None)
        try:
            options = dict(
                want_letter=want_letter,
                want_prediction=want_prediction,
                allow_synthetic_prediction=allow_synthetic,
            )
            if text is not None:
                request = CopilotRequest(text=text, **options)
            else:
                facts = IntakeFacts.model_validate({k: v for k, v in values.items() if v != ""})
                request = CopilotRequest(disruption=facts.to_disruption(), **options)
            progress = st.empty()
            # LEARN: The API returns one completed response, so this is a truthful
            # pending state rather than invented stages or a fake percentage counter.
            progress.markdown(
                '<div class="progress-card" role="status" aria-live="polite">'
                "<strong>Looking into your flight.</strong><p>Checking the details and applicable "
                "passenger-rights rules. Your assessment will appear here when ready.</p></div>",
                unsafe_allow_html=True,
            )
            try:
                st.session_state.result = assess_remote(request)
            finally:
                progress.empty()
        except ValidationError as exc:
            fields = sorted(
                {str(error["loc"][-1]) if error["loc"] else "input" for error in exc.errors()}
            )
            st.error(
                "Please check these fields: "
                + ", ".join(fields)
                + ". Supply the route, airline, date and disruption; "
                "use the shown date formats and numbers for minutes, days and fare."
            )
    if st.session_state.get("result"):
        with st.container(key="results"):
            render_result(st.session_state.result)
    st.html(
        '<div class="footer">Flight Disruption Copilot · Built for clarity, not certainty.</div>'
    )


if __name__ == "__main__":
    main()
