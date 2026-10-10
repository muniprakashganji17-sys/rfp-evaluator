"""Agentic RFP Evaluation & Supplier Ranking - Streamlit UI."""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src import database
from src.llm_client import DEFAULT_MODELS, LLMClient, LLMConfig
from src.orchestrator import run_evaluation

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📑", layout="wide")
database.init_db()  # creates tables + seeds criteria on first start (works on Streamlit Cloud)

SAMPLE_DIR = Path(__file__).parent / "sample_rfps"
SAMPLE_META = {  # default metadata for the bundled synthetic RFPs
    "Apex_Systems": ("Apex Systems", date(2026, 9, 10), 4.2),
    "BrightPath_Tech": ("BrightPath Tech", date(2026, 9, 12), 3.0),
    "NexaWorks": ("NexaWorks", date(2026, 9, 9), 4.5),
    "Orbit_Digital": ("Orbit Digital", date(2026, 9, 11), 4.8),
}


def secret(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ LLM settings")
    providers = ["mock", "anthropic", "openai"]
    default = secret("LLM_PROVIDER", "anthropic" if secret("ANTHROPIC_API_KEY") else "mock")
    provider = st.selectbox("Provider", providers, index=providers.index(default) if default in providers else 0,
                            help="'mock' is an offline keyword scorer for demos - no API key needed.")
    key_name = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    api_key = st.text_input("API key", type="password", value=secret(key_name) if key_name else "",
                            disabled=provider == "mock", help="Stored in memory only.")
    model = st.text_input("Model", value=secret("LLM_MODEL"), placeholder=DEFAULT_MODELS[provider])
    base_url = st.text_input("Base URL (OpenAI-compatible)", value=secret("OPENAI_BASE_URL"),
                             disabled=provider != "openai")
    inject = st.checkbox("Simulate malformed LLM output", disabled=provider != "mock",
                         help="Demo the validation layer: out-of-range, non-numeric and missing scores.")
    llm_cfg = LLMConfig(provider, api_key, model, base_url, inject)

    st.divider()
    st.header("🗂️ Saved runs")
    runs = [r for r in database.list_runs() if r["status"] == "COMPLETED"]
    choice = st.selectbox("View run", ["Latest in this session"] + [r["rfp_run_id"] for r in runs])


def current_result():
    if choice != "Latest in this session":
        return database.load_run(choice)
    return st.session_state.get("result")


st.title("📑 Agentic RFP Evaluation & Supplier Ranking")
st.caption("The LLM judges proposal content. Python does every formula, benchmark, tie-break and rank.")
tab_crit, tab_in, tab_lb, tab_card, tab_run = st.tabs(
    ["1 · Criteria", "2 · Supplier input", "3 · Leaderboard", "4 · Scorecards", "5 · Run details"])

# ------------------------------------------------------------------ 1. criteria
with tab_crit:
    all_crit = pd.DataFrame(database.get_criteria(active_only=False))
    active = all_crit[all_crit["is_active"] == 1]
    total = float(active["weight"].sum())
    st.subheader("Active evaluation criteria")
    st.dataframe(active[["criterion_id", "name", "description", "weight", "max_score"]], hide_index=True,
                 width="stretch")
    if abs(total - 100) < 1e-6:
        st.success(f"Active weights total {total:g}% ✔")
    else:
        st.warning(f"Active weights total {total:g}%, not 100%. They will be normalised to 100% when scoring.")
    with st.expander("✏️ Edit criteria (activate / deactivate / change weights)"):
        edited = st.data_editor(
            all_crit, hide_index=True, width="stretch", key="crit_editor",
            disabled=["criterion_id", "name", "description"],
            column_config={"is_active": st.column_config.CheckboxColumn("active"),
                           "weight": st.column_config.NumberColumn(min_value=0.0, max_value=100.0),
                           "max_score": st.column_config.NumberColumn(min_value=1.0)})
        if st.button("Save criteria"):
            database.update_criteria(edited.to_dict("records"))
            st.success("Saved. The next evaluation uses these values.")
            st.rerun()

# ------------------------------------------------------------------ 2. input
with tab_in:
    st.subheader("Upload supplier RFP responses")
    use_samples = st.checkbox("Use the 4 bundled synthetic RFPs", value=False)
    files = []
    if use_samples:
        for f in sorted(SAMPLE_DIR.glob("*.pdf")):
            files.append((f.name, f.read_bytes()))
    else:
        for up in st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True) or []:
            files.append((up.name, up.getvalue()))

    entries, errors = [], []
    for fname, data in files:
        key = fname.replace("_RFP_Response.pdf", "")
        dname, ddate, dexp = SAMPLE_META.get(key, (Path(fname).stem.replace("_", " "), date.today(), 3.0)) \
            if use_samples else (Path(fname).stem.replace("_", " "), date.today(), 3.0)
        c1, c2, c3 = st.columns([3, 2, 2])
        name = c1.text_input(f"Supplier name · {fname}", value=dname, key=f"n_{fname}_{use_samples}").strip()
        sdate = c2.date_input("Submission date", value=ddate, key=f"d_{fname}_{use_samples}")
        exp = c3.number_input("Experience rating (1-5)", 1.0, 5.0, float(dexp), 0.1, key=f"e_{fname}_{use_samples}")
        entries.append(dict(supplier_name=name, submission_date=sdate, experience_rating=exp,
                            pdf_bytes=data, filename=fname))

    # validation messages
    names = [e["supplier_name"].casefold() for e in entries]
    if not entries:
        errors.append("Upload at least two supplier PDFs (or tick the sample option).")
    elif len(entries) < 2:
        errors.append("At least two suppliers are needed for peer benchmarking.")
    if any(not e["supplier_name"] for e in entries):
        errors.append("Every supplier needs a name.")
    if len(set(names)) != len(names):
        errors.append("Supplier names must be unique.")
    for e in entries:
        if not e["pdf_bytes"].startswith(b"%PDF"):
            errors.append(f"{e['filename']} is not a valid PDF.")
        if e["submission_date"] > date.today():
            errors.append(f"{e['supplier_name'] or e['filename']}: submission date is in the future.")
    if provider != "mock" and not api_key:
        errors.append(f"Enter an API key for '{provider}' in the sidebar (or switch to 'mock').")
    if not database.get_criteria():
        errors.append("No active criteria - activate at least one on the Criteria tab.")
    for m in errors:
        st.error(m)

    if st.button("🚀 Evaluate", type="primary", disabled=bool(errors)):
        bar = st.progress(0.0, text="Starting...")
        try:
            st.session_state["result"] = run_evaluation(
                entries, LLMClient(llm_cfg), progress=lambda p, msg: bar.progress(min(p, 1.0), text=msg))
            bar.progress(1.0, text="Done")
            st.success(f"Run {st.session_state['result']['rfp_run_id']} completed - see the other tabs.")
        except Exception as exc:
            bar.empty()
            st.error(f"Evaluation failed: {exc}")

# ------------------------------------------------------------------ results
result = current_result()
STATUS_ICON = {"ok": "✅", "clipped": "✂️", "missing": "❓", "malformed": "⚠️"}

with tab_lb:
    if not result:
        st.info("Run an evaluation (tab 2) or pick a saved run in the sidebar.")
    else:
        st.subheader(f"Leaderboard · {result['rfp_run_id']}")
        lb = pd.DataFrame([{"Rank": s["final_rank"], "Supplier": s["supplier_name"],
                            "Absolute score (/100)": s["absolute_score"], "PPI": round(s["ppi"], 2),
                            "Submission date": s["submission_date"], "Experience rating": s["experience_rating"]}
                           for s in result["suppliers"]])
        st.dataframe(lb, hide_index=True, width="stretch")
        st.bar_chart(lb.set_index("Supplier")[["Absolute score (/100)", "PPI"]])
        st.markdown("**Relative performance % by criterion** (100 = best supplier on that criterion)")
        matrix = pd.DataFrame({s["supplier_name"]: {r["name"]: r["relative_pct"] for r in s["criteria_results"]}
                               for s in result["suppliers"]})
        st.dataframe(matrix.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100).format("{:.1f}"),
                     width="stretch")

with tab_card:
    if not result:
        st.info("No results yet.")
    else:
        names = [s["supplier_name"] for s in result["suppliers"]]
        pick = st.selectbox("Supplier", names, format_func=lambda n: f"#{names.index(n) + 1} {n}")
        s = next(x for x in result["suppliers"] if x["supplier_name"] == pick)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Final rank", s["final_rank"])
        m2.metric("Absolute score", f"{s['absolute_score']:.2f}")
        m3.metric("PPI", f"{s['ppi']:.2f}")
        m4.metric("Experience", s["experience_rating"])
        st.write(s["overall_summary"])
        table = pd.DataFrame([{"Criterion": r["name"], "Score": r["score"], "Max": r["max_score"],
                               "Benchmark": r["benchmark"], "Gap": r["gap"], "Relative %": r["relative_pct"],
                               "Weight %": r["weight"], "Weighted pts": round(r["weighted_contribution"], 2),
                               "Status": STATUS_ICON.get(r["status"], r["status"])}
                              for r in s["criteria_results"]])
        st.dataframe(table, hide_index=True, width="stretch")
        st.markdown("#### Evidence and justification")
        for r in s["criteria_results"]:
            with st.expander(f"{STATUS_ICON.get(r['status'], '')} {r['name']} — {r['score']:g}/{r['max_score']:g}"):
                st.markdown(f"**Justification:** {r['justification'] or '—'}")
                st.markdown(f"**Evidence:** {r['evidence'] or '— none provided —'}")
                st.caption(f"Contribution: {r['score']:g}/{r['max_score']:g} × {r['weight']:.1f}% = "
                           f"{r['weighted_contribution']:.2f} pts")
        if s["risks"]:
            st.markdown("**Risks identified**")
            for risk in s["risks"]:
                st.markdown(f"- {risk}")
        for w in s["warnings"]:
            st.warning(w)

with tab_run:
    if not result:
        st.info("No results yet.")
    else:
        st.subheader("Run details")
        c1, c2, c3 = st.columns(3)
        c1.metric("RFP_RUN_ID", result["rfp_run_id"])
        c2.metric("Created (UTC)", result["created_at"])
        c3.metric("LLM", f"{result['llm']['provider']} / {result['llm']['model']}")
        st.markdown("**Criteria snapshot used**")
        st.dataframe(pd.DataFrame(result["criteria"]), hide_index=True, width="stretch")
        st.markdown("**Tie-break order:** 1) higher PPI → 2) earlier submission date → "
                    "3) higher experience rating → 4) supplier name A–Z")
        for line in result["tie_break_explanation"]:
            st.markdown(f"- {line}")
        st.markdown(f"**Warnings ({len(result['warnings'])})**")
        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)
        else:
            st.success("No validation warnings.")
        with st.expander("Workflow trace"):
            st.dataframe(pd.DataFrame(result["trace"]), hide_index=True, width="stretch")
        st.download_button("⬇️ Download complete result (JSON)", json.dumps(result, indent=2),
                           file_name=f"{result['rfp_run_id']}.json", mime="application/json")
