"""
Evidence ledger: ONE central, code-verified evidence step that feeds EVERY report size (short / standard / long).

Why: a paid audit report must let the client see, for every requirement element, WHERE in his own
documentation the evidence is. The LLM only finds candidate quotes; this module (code) verifies them
against the source text, downgrades anything it cannot find, and derives statuses and scores
deterministically. All tiers read the same ledger, so numbers never contradict each other.

DRAFT NOTICE: the CHECKLIST below was written from the structure of Regulation (EU) 2024/1689
(Art. 9-15 + Annex IV). It MUST be reviewed against the Official Journal text by a legal reviewer
before commercial use. Edit CHECKLIST only; nothing else in the code depends on its content.
"""
import re

ALLOWED_STATUS = ["Evidenced", "Partially evidenced", "Insufficient evidence", "Not applicable"]
POINTS = {"Evidenced": 1.0, "Partially evidenced": 0.5, "Insufficient evidence": 0.0}

# article -> (title, [(id, requirement element)])
CHECKLIST = {
    "Art. 9": ("Risk management system", [
        ("A9-1",  "Risk management system established, documented and maintained throughout the lifecycle (Art. 9(1))"),
        ("A9-2a", "Identification and analysis of known and reasonably foreseeable risks to health, safety and fundamental rights under intended use (Art. 9(2)(a))"),
        ("A9-2b", "Estimation and evaluation of risks under reasonably foreseeable misuse (Art. 9(2)(b))"),
        ("A9-2c", "Evaluation of further risks using post-market monitoring data (Art. 9(2)(c))"),
        ("A9-2d", "Targeted risk management measures adopted and residual risk judged acceptable (Art. 9(2)(d), 9(5))"),
        ("A9-8",  "Testing against prior-defined metrics and thresholds during development and before placing on the market (Art. 9(6), 9(8))"),
        ("A9-9",  "Consideration of impact on persons under 18 and other vulnerable groups (Art. 9(9))"),
    ]),
    "Art. 10": ("Data and data governance", [
        ("A10-2a", "Relevant design choices for data (Art. 10(2)(a))"),
        ("A10-2b", "Data collection processes and origin of data, original purpose for personal data (Art. 10(2)(b))"),
        ("A10-2c", "Data preparation operations such as annotation, labelling, cleaning, aggregation (Art. 10(2)(c))"),
        ("A10-2d", "Assumptions about what the data measure and represent (Art. 10(2)(d))"),
        ("A10-2e", "Assessment of availability, quantity and suitability of data sets (Art. 10(2)(e))"),
        ("A10-2f", "Examination of data for possible biases (Art. 10(2)(f))"),
        ("A10-2g", "Measures to detect, prevent and mitigate identified biases (Art. 10(2)(g))"),
        ("A10-2h", "Identification of data gaps or shortcomings and how they are addressed (Art. 10(2)(h))"),
        ("A10-3",  "Training, validation and testing data relevant, sufficiently representative, as error-free and complete as possible, with appropriate statistical properties (Art. 10(3))"),
    ]),
    "Art. 11": ("Technical documentation", [
        ("A11-1", "Technical documentation drawn up before placing on the market and kept up to date (Art. 11(1))"),
        ("A11-2", "General description: intended purpose, provider, version, hardware/software it interacts with (Annex IV point 1)"),
        ("A11-3", "Detailed description of elements and development process: design specifications, architecture, data, training methods (Annex IV point 2)"),
        ("A11-4", "Information on monitoring, functioning and control, including accuracy for specific groups and foreseeable unintended outcomes (Annex IV point 3)"),
        ("A11-5", "Appropriateness of the performance metrics (Annex IV point 4)"),
        ("A11-6", "Description of the risk management system (Annex IV point 5)"),
        ("A11-7", "Description of relevant changes made through the lifecycle (Annex IV point 6)"),
        ("A11-8", "Description of the post-market performance evaluation system / monitoring plan (Annex IV point 9)"),
    ]),
    "Art. 12": ("Record-keeping", [
        ("A12-1", "Automatic recording of events (logs) over the lifetime of the system (Art. 12(1))"),
        ("A12-2", "Logging that allows identifying risk situations, supports post-market monitoring and monitoring of operation (Art. 12(2))"),
    ]),
    "Art. 13": ("Transparency and information to deployers", [
        ("A13-1",  "Operation sufficiently transparent for deployers to interpret output and use it appropriately (Art. 13(1))"),
        ("A13-2",  "Instructions for use provided in an appropriate digital format (Art. 13(2))"),
        ("A13-3a", "Provider identity and contact details in the instructions (Art. 13(3)(a))"),
        ("A13-3b", "Characteristics, capabilities and limitations: intended purpose, accuracy metrics, foreseeable misuse, performance for specific groups, input data specifications (Art. 13(3)(b))"),
        ("A13-3c", "Pre-determined changes to the system and its performance (Art. 13(3)(c))"),
        ("A13-3d", "Human oversight measures, including technical measures that help interpret outputs (Art. 13(3)(d))"),
        ("A13-3e", "Computational and hardware resources, expected lifetime, maintenance and updates (Art. 13(3)(e))"),
        ("A13-3f", "Description of mechanisms for collecting, storing and interpreting logs (Art. 13(3)(f))"),
    ]),
    "Art. 14": ("Human oversight", [
        ("A14-1",  "Designed so that natural persons can effectively oversee it, with appropriate human-machine interface tools (Art. 14(1))"),
        ("A14-3",  "Oversight measures built in by the provider and/or identified for the deployer, proportionate to risk and context (Art. 14(3))"),
        ("A14-4a", "Overseers can understand the system's capacities and limitations and monitor its operation (Art. 14(4)(a))"),
        ("A14-4b", "Overseers are made aware of automation bias (Art. 14(4)(b))"),
        ("A14-4c", "Overseers can correctly interpret the system's output (Art. 14(4)(c))"),
        ("A14-4d", "Overseers can decide not to use, disregard, override or reverse the output (Art. 14(4)(d))"),
        ("A14-4e", "Overseers can intervene or interrupt the system, for example with a stop function (Art. 14(4)(e))"),
    ]),
    "Art. 15": ("Accuracy, robustness and cybersecurity", [
        ("A15-1", "Appropriate level of accuracy, robustness and cybersecurity throughout the lifecycle (Art. 15(1))"),
        ("A15-2", "Accuracy levels and metrics declared in the instructions for use (Art. 15(3))"),
        ("A15-3", "Resilience to errors, faults and inconsistencies, including technical redundancy or fail-safe measures (Art. 15(4))"),
        ("A15-4", "Mitigation of feedback loops for systems that keep learning after deployment (Art. 15(4))"),
        ("A15-5", "Protection against attempts to alter use, outputs or performance by exploiting vulnerabilities: data poisoning, adversarial examples, model evasion (Art. 15(5))"),
    ]),
}

# score placeholders used by the Word templates -> article they summarise
SCORE_SOURCES = {
    "RISK_SCORE": "Art. 9",
    "DATA_GOVERNANCE_SCORE": "Art. 10",
    "TECH_DOCS_SCORE": "Art. 11",
    "TRANSPARENCY_SCORE": "Art. 13",
    "HUMAN_OVERSIGHT_SCORE": "Art. 14",
    "PERF_SAFETY_SCORE": "Art. 15",
}

_ITEM_INDEX = {iid: (art, desc) for art, (_t, items) in CHECKLIST.items() for iid, desc in items}


def render_checklist() -> str:
    out = []
    for art, (title, items) in CHECKLIST.items():
        out.append(f"{art} - {title}")
        for iid, desc in items:
            out.append(f"  [{iid}] {desc}")
    return "\n".join(out)


def _squash(s) -> str:
    return re.sub(r"[\W_]+", "", str(s or "").lower())


def _quote_in_source(quote: str, source_sq: str) -> str:
    """Returns 'exact', 'fuzzy' or '' (not found)."""
    q = _squash(quote)
    if len(q) < 25:
        return ""
    if q in source_sq:
        return "exact"
    try:  # optional: tolerate OCR / PDF-extraction noise
        from rapidfuzz import fuzz
        if len(q) >= 40 and fuzz.partial_ratio(q, source_sq) >= 96:
            return "fuzzy"
    except Exception:
        pass
    return ""


def verify_ledger(raw_items, source_text: str, run_log: dict) -> list:
    """Every checklist item appears exactly once. 'Evidenced' / 'Partially evidenced' survive only
    with a quote that is really in the source; anything else becomes 'Insufficient evidence'."""
    source_sq = _squash(source_text)
    by_id = {}
    for it in raw_items or []:
        if isinstance(it, dict):
            it = {str(k).upper(): v for k, v in it.items()}
            by_id[str(it.get("ID", "")).strip()] = it

    ledger, downgraded, missing = [], 0, 0
    for art, (title, items) in CHECKLIST.items():
        for iid, desc in items:
            it = by_id.get(iid)
            status, quote, src, note, match = "Insufficient evidence", "", "", "", ""
            if it is None:
                missing += 1
                note = "Not returned by the analysis step."
            else:
                raw_status = re.sub(r"[*_]", "", str(it.get("STATUS", ""))).strip()
                status = next((s for s in ALLOWED_STATUS if s.lower() == raw_status.lower()), "Insufficient evidence")
                quote = str(it.get("EVIDENCE_QUOTE", "") or "").strip()
                src = str(it.get("SOURCE", "") or "").strip()
                note = str(it.get("NOTE", "") or "").strip()
                if status in ("Evidenced", "Partially evidenced"):
                    match = _quote_in_source(quote, source_sq)
                    if not match:
                        downgraded += 1
                        run_log["warnings"].append(
                            f"LEDGER {iid}: model claimed '{status}' but the quote was not found in the documentation; set to 'Insufficient evidence'.")
                        note = "A supporting passage could not be verified in the documentation."
                        status, quote, src = "Insufficient evidence", "", ""
                elif status == "Not applicable":
                    if not note:
                        status = "Insufficient evidence"
                        run_log["warnings"].append(f"LEDGER {iid}: 'Not applicable' without justification; set to 'Insufficient evidence'.")
                    quote = ""
                else:
                    quote, src = "", ""
            ledger.append({"ID": iid, "ARTICLE": art, "REQUIREMENT": desc, "STATUS": status,
                           "EVIDENCE_QUOTE": quote, "SOURCE": src, "NOTE": note,
                           "VERIFIED": bool(match), "MATCH": match})
    run_log["evidence_ledger"] = {"items": len(ledger), "downgraded": downgraded, "missing": missing}
    if missing:
        run_log["warnings"].append(f"Evidence ledger: {missing} checklist item(s) were not returned by the model.")
    return ledger


def coverage(ledger: list, article: str = None):
    """Evidence-coverage 0-100 (Evidenced=1, Partially=0.5, Insufficient=0; 'Not applicable' excluded)."""
    rows = [r for r in ledger if (article is None or r["ARTICLE"] == article) and r["STATUS"] in POINTS]
    if not rows:
        return None
    return int(round(100 * sum(POINTS[r["STATUS"]] for r in rows) / len(rows)))


def article_status(ledger: list, article: str) -> str:
    rows = [r for r in ledger if r["ARTICLE"] == article and r["STATUS"] in POINTS]
    if not rows:
        return "Not applicable"
    if all(r["STATUS"] == "Evidenced" for r in rows):
        return "Evidenced"
    if all(r["STATUS"] == "Insufficient evidence" for r in rows):
        return "Insufficient evidence"
    return "Partially evidenced"


def _short(desc: str) -> str:
    return re.split(r"\s\((?:Art\.|Annex)", desc)[0]


def format_ledger_block(ledger: list, truncated: bool = False) -> str:
    out = ["\n\n=======================================================",
           "   ESTABLISHED EVIDENCE LEDGER (binding for ALL modules - code-verified, do not re-assess)",
           "=======================================================",
           "Statuses below were verified against the documentation by code. Use them verbatim. Do not upgrade a status,",
           "do not describe a requirement as implemented unless its status here is Evidenced or Partially evidenced,",
           "and do not state any score: scores are computed by the system from this ledger."]
    if truncated:
        out.append("NOTICE: the documentation was truncated for processing; an 'Insufficient evidence' item may be covered in the omitted part.")
    for art, (title, _items) in CHECKLIST.items():
        out.append(f"\n{art} - {title}: coverage {coverage(ledger, art)}/100 ({article_status(ledger, art)})")
        for r in [x for x in ledger if x["ARTICLE"] == art]:
            line = f"  [{r['ID']}] {r['STATUS']} - {_short(r['REQUIREMENT'])}"
            if r["EVIDENCE_QUOTE"]:
                line += f' | evidence: "{r["EVIDENCE_QUOTE"]}"'
                if r["SOURCE"]:
                    line += f" ({r['SOURCE']})"
            elif r["NOTE"]:
                line += f" | {r['NOTE']}"
            out.append(line)
    return "\n".join(out) + "\n"


def apply_ledger(final_data: dict, ledger: list, run_log: dict, truncated: bool = False):
    """Writes the ledger-derived fields. Safe for every tier: a template only uses the keys it contains."""
    overall = coverage(ledger)
    final_data["EVIDENCE_LEDGER"] = ledger
    final_data["EVIDENCE_COVERAGE_OVERALL"] = f"{overall}/100" if overall is not None else "Not assessed"
    final_data["FINAL_SCORE"] = final_data["EVIDENCE_COVERAGE_OVERALL"]

    for key, art in SCORE_SOURCES.items():
        c = coverage(ledger, art)
        new = f"{c}/100" if c is not None else "Not assessed"
        if key in final_data and str(final_data[key]).strip() != new:
            run_log["warnings"].append(f"{key}: model value '{final_data[key]}' replaced by ledger coverage '{new}'.")
        final_data[key] = new

    matrix = []
    for art, (title, _items) in CHECKLIST.items():
        rows = [r for r in ledger if r["ARTICLE"] == art]
        ev = [r for r in rows if r["STATUS"] in ("Evidenced", "Partially evidenced")]
        gaps = [r for r in rows if r["STATUS"] == "Insufficient evidence"]
        findings = [f'{r["STATUS"]}: {_short(r["REQUIREMENT"])} - "{r["EVIDENCE_QUOTE"]}"' + (f' ({r["SOURCE"]})' if r["SOURCE"] else "")
                    for r in ev[:4]]
        if len(ev) > 4:
            findings.append(f"{len(ev) - 4} further element(s) with supporting evidence (see ledger).")
        if gaps:
            findings.append("No verifiable evidence in the documentation for: " + "; ".join(_short(r["REQUIREMENT"]) for r in gaps) + ".")
        matrix.append({"ARTICLE": art, "REQUIREMENT": title, "STATUS": article_status(ledger, art),
                       "COVERAGE": f"{coverage(ledger, art)}/100", "FINDINGS": findings})
    final_data["COMPLIANCE_MATRIX"] = matrix
    final_data["EVIDENCE_GAPS"] = [{"ID": r["ID"], "ARTICLE": r["ARTICLE"], "GAP": _short(r["REQUIREMENT"])}
                                   for r in ledger if r["STATUS"] == "Insufficient evidence"]
    final_data["EVIDENCE_GAPS_COUNT"] = len(final_data["EVIDENCE_GAPS"])
    run_log["evidence_ledger"]["coverage"] = {art: coverage(ledger, art) for art in CHECKLIST}
    run_log["evidence_ledger"]["overall"] = overall


def run_evidence_ledger(context: str, source_text: str, run_log: dict, call_llm_json, load_prompt):
    """Returns the verified ledger, or None when there is nothing to check or the call failed.
    call_llm_json / load_prompt are passed in by app.py (no circular import)."""
    if not (source_text or "").strip():
        run_log["warnings"].append("Evidence ledger skipped: no documentation or description to check.")
        return None
    prompt = load_prompt("core/evidence_ledger.txt", run_log).replace("[CHECKLIST]", render_checklist())
    system = ("You are an evidence-extraction assistant for an EU AI Act documentation review. "
              "You ALWAYS answer ONLY with a single valid JSON object with exactly the requested keys.")
    items = None
    for attempt, seed in enumerate((None, 1234)):  # one retry with another seed if the answer is incomplete
        data = call_llm_json(system, context + "\n\n" + prompt, 8000,
                             "evidence_ledger" if attempt == 0 else "evidence_ledger-retry",
                             run_log, temperature=0.0, seed=seed)
        data = {str(k).upper(): v for k, v in (data or {}).items()}
        items = data.get("LEDGER")
        returned = {str(i.get("ID", "")).strip() for i in (items or []) if isinstance(i, dict)}
        if len(returned & set(_ITEM_INDEX)) >= 0.9 * len(_ITEM_INDEX):
            break
    if not items:
        run_log["warnings"].append("Evidence ledger step failed; report falls back to module-level assessments (UNVERIFIED).")
        return None
    return verify_ledger(items, source_text, run_log)
