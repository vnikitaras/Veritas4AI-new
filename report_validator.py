"""
Post-processing validator for generated EU AI Act reports.

Goal: everything that CAN be computed or checked deterministically is taken away from the LLM.
 - counts are derived from the real lists
 - scores are derived from a fixed rubric over the compliance matrix (no free-form numbers)
 - article numbers are checked against a fixed map of Regulation (EU) 2024/1689
 - Art. 50 is shown as an additional obligation, never as "High Risk System"
Every correction / finding is appended to run_log["warnings"] so nothing is changed silently.
"""
import re

# Fixed map: article number -> (short name, keywords that identify its topic)
ARTICLE_MAP = {
    6:  ("Classification of AI systems", ["classification", "high-risk classification"]),
    9:  ("Risk management system", ["risk management"]),
    10: ("Data and data governance", ["data governance", "training data", "validation data", "bias monitoring"]),
    11: ("Technical documentation", ["technical documentation"]),
    12: ("Record-keeping", ["record-keeping", "record keeping", "logging", "event log"]),
    13: ("Transparency and provision of information to deployers", ["transparency", "instructions for use", "interpretab"]),
    14: ("Human oversight", ["human oversight", "automation bias"]),
    15: ("Accuracy, robustness and cybersecurity", ["accuracy", "robustness", "cybersecurity", "adversarial"]),
    50: ("Transparency obligations for certain AI systems", ["transparency obligations", "interaction with natural persons", "deepfake", "synthetic content"]),
}

_ART_RE = re.compile(r"\b(?:Article|Art\.?)\s*(\d{1,3})\b", re.IGNORECASE)

# Rubric: matrix status -> points (fixed, documented, reproducible)
STATUS_POINTS = {
    "evidenced": 100,
    "partially evidenced": 50,
    "insufficient evidence": 0,
    "not evidenced": 0,
}
# score key -> article it is derived from
SCORE_SOURCES = {
    "RISK_SCORE": "Art. 9",
    "DATA_GOVERNANCE_SCORE": "Art. 10",
    "TRANSPARENCY_SCORE": "Art. 13",
    "HUMAN_OVERSIGHT_SCORE": "Art. 14",
    "PERF_SAFETY_SCORE": "Art. 15",
    "TECH_DOCS_SCORE": "Art. 11",
}


def _clean(s):
    return re.sub(r"[*_]", "", str(s or "")).strip()


def _walk_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def check_article_mentions(final_data: dict) -> list:
    """Flags 'Article N' followed (same sentence) by the topic of a DIFFERENT article.
    Example caught: 'Article 10 ... mandates risk management systems' (that is Art. 9)."""
    warnings = []
    for path, text in _walk_strings(final_data):
        for m in _ART_RE.finditer(text):
            n = int(m.group(1))
            window = text[m.end(): m.end() + 120]
            window = re.split(r"[.;]\s", window)[0].lower()
            if n not in ARTICLE_MAP:
                continue
            own = ARTICLE_MAP[n][1]
            if any(k in window for k in own):
                continue
            for other, (name, kws) in ARTICLE_MAP.items():
                if other != n and other != 6 and any(k in window for k in kws):
                    warnings.append(
                        f"ARTICLE MISMATCH at {path}: 'Article {n}' ({ARTICLE_MAP[n][0]}) is followed by "
                        f"text about Art. {other} ({name}): '...{window[:70].strip()}...'")
                    break
    return warnings


def _matrix_status(final_data: dict) -> dict:
    out = {}
    for row in final_data.get("COMPLIANCE_MATRIX", []) or []:
        if isinstance(row, dict):
            art = _clean(row.get("ARTICLE"))
            out[art] = _clean(row.get("STATUS")).lower()
    return out


def derive_scores(final_data: dict, run_log: dict):
    """Replace LLM-invented scores by a rubric over the compliance matrix.
    100 = evidenced, 50 = partially evidenced, 0 = insufficient evidence; no matrix row -> 'Not assessed'."""
    if not any(k in final_data for k in SCORE_SOURCES):
        return
    status = _matrix_status(final_data)
    for key, art in SCORE_SOURCES.items():
        if key not in final_data:
            continue
        st = status.get(art)
        if st is None:
            new = "Not assessed (no matrix row)"
        else:
            pts = next((p for s, p in STATUS_POINTS.items() if st.startswith(s)), None)
            new = "Not assessed" if pts is None else f"{pts}/100 (rubric: {st})"
        if str(final_data[key]) != new:
            run_log["warnings"].append(f"{key}: LLM value '{final_data[key]}' replaced by rubric value '{new}'.")
        final_data[key] = new


def derive_counts(final_data: dict, run_log: dict):
    plan = final_data.get("ACTION_PLAN")
    if not isinstance(plan, list):
        return
    p1 = sum(1 for a in plan if isinstance(a, dict) and "P1" in _clean(a.get("PRIORITY")).upper())
    new_gaps, new_recs = f"**{p1} Critical**", f"**{len(plan)} Actions**"
    for key, new in (("CRITICAL_GAPS_COUNT", new_gaps), ("RECOMMENDATIONS_COUNT", new_recs)):
        if key in final_data and final_data[key] != new:
            run_log["warnings"].append(f"{key}: '{final_data[key]}' did not match the action plan; corrected to '{new}'.")
        final_data[key] = new


def fix_applicable_articles(final_data: dict, cls: dict, run_log: dict):
    """Art. 50 is an additional obligation (taken from the classification step), never 'High Risk System'."""
    arts = final_data.get("APPLICABLE_ARTICLES")
    if not isinstance(arts, list):
        return
    extra = " ".join(str(x) for x in (cls or {}).get("ADDITIONAL_OBLIGATIONS", []) or [])
    for a in arts:
        if not isinstance(a, dict):
            continue
        m = _ART_RE.search(_clean(a.get("ARTICLE_NAME")))
        if m and int(m.group(1)) == 50:
            new = "**Additional obligation** (transparency)" if "50" in extra else "**Not established** from the documentation"
            if a.get("APPLICABILITY_STATUS") != new:
                run_log["warnings"].append(f"Art. 50 status corrected to '{new}'.")
            a["APPLICABILITY_STATUS"] = new


def flag_inconsistent_assertions(final_data: dict, run_log: dict):
    """Flags confident descriptions of a mechanism whose article analysis says 'insufficient evidence'."""
    pairs = [("OVERSIGHT_MECHANISM", "ART_14_ANALYSIS", "human oversight"),
             ("DATA_LIFECYCLE_DESC", "ART_10_ANALYSIS", "data lifecycle")]
    for desc_key, analysis_key, label in pairs:
        if desc_key in final_data and "insufficient evidence" in str(final_data.get(analysis_key, "")).lower():
            run_log["warnings"].append(
                f"POSSIBLE UNGROUNDED CONTENT: {desc_key} describes {label} in detail while {analysis_key} reports insufficient evidence. Verify against the source document.")


def flag_boilerplate_inventory(final_data: dict, run_log: dict):
    for row in final_data.get("DOC_INVENTORY_LIST", []) or []:
        if isinstance(row, dict) and "ADDRESSED IN REPORT" in _clean(row.get("STATUS")).upper():
            run_log["warnings"].append(
                "DOC_INVENTORY_LIST marks items 'ADDRESSED IN REPORT' (index of chapters), not a compliance finding; "
                "its Annex IV paragraph references are not verified.")
            return


def validate_and_correct(final_data: dict, cls: dict, run_log: dict, ledger_applied: bool = False) -> dict:
    """Entry point: call once per report after apply_established_classification().
    With a verified evidence ledger the scores already come from it; the matrix-based rubric is only a fallback."""
    derive_counts(final_data, run_log)
    if not ledger_applied:
        derive_scores(final_data, run_log)
    fix_applicable_articles(final_data, cls, run_log)
    # client quotes and ledger-derived rows are verbatim source text, not model prose: do not scan them
    skip = {"EVIDENCE_LEDGER", "COMPLIANCE_MATRIX"}
    run_log["warnings"].extend(check_article_mentions({k: v for k, v in final_data.items() if k not in skip}))
    flag_inconsistent_assertions(final_data, run_log)
    flag_boilerplate_inventory(final_data, run_log)
    return final_data
