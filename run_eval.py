#!/usr/bin/env python3
"""
run_eval.py - repeatable evaluation of the AI Assessor pipeline (no Word/PDF step).

What it does
  For every case in a JSON file it runs the real pipeline (app.generate_final_data) N times per
  report tier and writes
    <out>/results.csv        one row per run (classification, agreement, tokens, seconds, failures)
    <out>/summary.csv        one row per case x tier (majority class, run-to-run consistency, match rate)
    <out>/summary.md         the same as a table you can paste into the paper
    <out>/raw/*.json         final report data + run log of every run (for the human/expert review)

Usage (needs OPENAI_API_KEY in the environment or in .env)
  python run_eval.py --cases eval/cases.json --tiers short standard long --runs 3
  python run_eval.py --cases eval/cases.json --classification-only --runs 5      # cheap: only the classification step
  python run_eval.py --cases eval/cases.json --tiers standard --runs 3 --price-in 2.5 --price-out 10

Prices are USD per 1M tokens. They are NOT built in on purpose (they change): pass the current ones
if you want a cost column.

cases.json format (see eval/cases.example.json)
  [{"id": "D-01", "name": "CheXNet", "docs": ["docs/chexnet.pdf"], "role": "AI provider",
    "language": "en",
    "expected_class": null | one of app.ALLOWED_CLASSES,
    "expected_annex": null | "Annex III, point 4(a)"}]
  expected_* are YOUR reference labels (decide them from the intended purpose of each source).
  Leave them null to skip the comparison.
"""
import argparse
import copy
import csv
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class _Upload:
    """Minimal stand-in for werkzeug FileStorage, so the app's own text extraction is used."""
    def __init__(self, path):
        self.filename = os.path.basename(path)
        with open(path, "rb") as f:
            self._b = io.BytesIO(f.read())

    def seek(self, *a): return self._b.seek(*a)
    def read(self, *a): return self._b.read(*a)
    def tell(self): return self._b.tell()


def build_params(A, case, tier):
    uploads = [_Upload(os.path.join(case.get("base_dir", "."), p)) for p in case["docs"]]
    text, names = A.extract_supporting_docs_text(uploads)
    if not text.strip():
        raise SystemExit(f"No text could be extracted from the documents of case {case['id']}: {case['docs']}")
    date = datetime.now().strftime("%d/%m/%Y")
    p = {
        "details": tier, "AUTHOR": "run_eval", "DATE": date, "REPORT_DATE": date, "CURRENT_DATE": date,
        "input_mode": "files", "LANGUAGE": case.get("language", "en"),
        "APPLICATION_NAME": case.get("name") or case["id"],
        "SUPPORTING_DOCS_TEXT": text, "supporting_filenames": names,
        "organization_role": case.get("role", ""), "risk_category": "",
        "application_summary": "", "application_area": "Determined by Documentation",
    }
    p["APPLICATION_URL"] = ""
    p["APPLICATION_DESCRIPTION"] = ""
    p["APPLICATION_AREA"] = p["application_area"]
    p["ORGANIZATION_ROLE"] = p["organization_role"]
    p["RISK_CATEGORY"] = "Not classified"
    p["WEBSITE_URL"] = ""
    return p


def usage_totals(run_log):
    pt = sum((m.get("prompt_tokens") or 0) for m in run_log.get("modules", []))
    ct = sum((m.get("completion_tokens") or 0) for m in run_log.get("modules", []))
    return pt, ct


def annex_base(ref):
    """'Annex III, point 4(a)' -> 'annex iii, point 4' (match on the point, ignore the sub-letter)."""
    r = (ref or "").lower().replace("(", " (").split(" (")[0].strip()
    return r


def one_run(A, case, tier, classification_only):
    params = build_params(A, case, tier)
    t0 = time.time()
    if classification_only:
        run_log = A.new_run_log(params, tier)
        cls = A.run_classification_core(params, run_log)
        final_data = {"CLASSIFICATION": cls}
        run_log["total_seconds"] = round(time.time() - t0, 1)
        A.write_run_log(run_log)
    else:
        final_data, run_log = A.generate_final_data(params)
        cls = run_log.get("classification") or {}
    secs = round(time.time() - t0, 1)
    pt, ct = usage_totals(run_log)
    return cls, final_data, run_log, secs, pt, ct


def summarise(rows):
    """rows: list of dicts from results.csv -> list of summary dicts (pure function, unit-tested)."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["case_id"], r["tier"])].append(r)
    out = []
    for (cid, tier), rs in groups.items():
        pairs = [(r["final_class"], r["annex_reference"]) for r in rs]
        (major, major_n) = Counter(pairs).most_common(1)[0]
        n = len(rs)
        exp_c = rs[0].get("expected_class") or ""
        exp_a = rs[0].get("expected_annex") or ""
        cm = [r["class_match"] for r in rs if r["class_match"] != ""]
        am = [r["annex_match"] for r in rs if r["annex_match"] != ""]
        out.append({
            "case_id": cid, "tier": tier, "runs": n,
            "majority_class": major[0], "majority_annex": major[1],
            "consistency": f"{major_n}/{n}",
            "expected_class": exp_c, "expected_annex": exp_a,
            "class_match_rate": f"{sum(1 for x in cm if x == 'yes')}/{len(cm)}" if cm else "",
            "annex_match_rate": f"{sum(1 for x in am if x == 'yes')}/{len(am)}" if am else "",
            "mean_seconds": round(sum(float(r["seconds"]) for r in rs) / n, 1),
            "mean_prompt_tokens": int(sum(int(r["prompt_tokens"]) for r in rs) / n),
            "mean_completion_tokens": int(sum(int(r["completion_tokens"]) for r in rs) / n),
            "runs_with_failed_modules": sum(1 for r in rs if int(r["failed_modules"]) > 0),
        })
    return sorted(out, key=lambda d: (d["case_id"], d["tier"]))


def to_markdown(summary):
    cols = ["case_id", "tier", "runs", "majority_class", "majority_annex", "consistency",
            "expected_class", "class_match_rate", "annex_match_rate", "mean_seconds", "runs_with_failed_modules"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for s in summary:
        lines.append("| " + " | ".join(str(s.get(c, "")) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--tiers", nargs="+", default=["standard"], choices=["short", "standard", "long"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=None, help="output folder (default eval_out/<timestamp>)")
    ap.add_argument("--classification-only", action="store_true")
    ap.add_argument("--only", nargs="*", help="run only these case ids")
    ap.add_argument("--price-in", type=float, default=None, help="USD per 1M prompt tokens")
    ap.add_argument("--price-out", type=float, default=None, help="USD per 1M completion tokens")
    args = ap.parse_args(argv)

    if not os.environ.get("OPENAI_API_KEY"):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")

    import app as A

    with open(args.cases, encoding="utf-8") as f:
        cases = json.load(f)
    cases_dir = os.path.dirname(os.path.abspath(args.cases))
    for c in cases:
        c.setdefault("base_dir", cases_dir)
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]

    out = args.out or os.path.join("eval_out", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(os.path.join(out, "raw"), exist_ok=True)
    tiers = ["short"] if args.classification_only else args.tiers   # tier is irrelevant for classification
    total = len(cases) * len(tiers) * args.runs
    print(f"Running {total} runs -> {out}")
    print(f"model={A.LLM_MODEL} temperature={A.LLM_TEMPERATURE} seed={A.LLM_SEED} votes={A.CLASSIFICATION_VOTES} app={A.APP_VERSION}")

    rows = []
    k = 0
    for case in cases:
        exp_c = case.get("expected_class")
        exp_a = case.get("expected_annex")
        exp_c_norm = A.normalise_class(exp_c) if exp_c else None
        for tier in tiers:
            for run in range(1, args.runs + 1):
                k += 1
                print(f"[{k}/{total}] {case['id']} {tier} run {run} ...", flush=True)
                try:
                    cls, final_data, run_log, secs, pt, ct = one_run(A, case, tier, args.classification_only)
                except Exception as e:
                    print(f"   FAILED: {e}")
                    rows.append({"case_id": case["id"], "tier": tier, "run": run, "final_class": "ERROR",
                                 "annex_reference": str(e)[:80], "agreement": "", "confidence": "",
                                 "expected_class": exp_c or "", "expected_annex": exp_a or "",
                                 "class_match": "", "annex_match": "", "seconds": 0, "prompt_tokens": 0,
                                 "completion_tokens": 0, "est_cost_usd": "", "failed_modules": 1,
                                 "warnings": 1, "docs_truncated": "", "rag_kept": ""})
                    continue
                fc = cls.get("FINAL_CLASS", "")
                ref = str(cls.get("ANNEX_REFERENCE", ""))
                cost = ""
                if args.price_in is not None and args.price_out is not None:
                    cost = round(pt / 1e6 * args.price_in + ct / 1e6 * args.price_out, 4)
                rows.append({
                    "case_id": case["id"], "tier": tier, "run": run,
                    "final_class": fc, "annex_reference": ref,
                    "agreement": cls.get("AGREEMENT", ""), "confidence": cls.get("CONFIDENCE", ""),
                    "expected_class": exp_c or "", "expected_annex": exp_a or "",
                    "class_match": ("" if not exp_c_norm else ("yes" if fc == exp_c_norm else "no")),
                    "annex_match": ("" if not exp_a else ("yes" if annex_base(ref) == annex_base(exp_a) else "no")),
                    "seconds": secs, "prompt_tokens": pt, "completion_tokens": ct, "est_cost_usd": cost,
                    "failed_modules": len(run_log.get("failed_modules", [])),
                    "warnings": len(run_log.get("warnings", [])),
                    "docs_truncated": run_log.get("docs_truncated", ""),
                    "rag_kept": (run_log.get("rag") or {}).get("kept", ""),
                })
                with open(os.path.join(out, "raw", f"{case['id']}_{tier}_run{run}.json"), "w", encoding="utf-8") as f:
                    json.dump({"classification": cls, "final_data": final_data, "run_log": run_log},
                              f, ensure_ascii=False, indent=2, default=str)

    if rows:
        with open(os.path.join(out, "results.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        summary = summarise(rows)
        with open(os.path.join(out, "summary.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
            w.writeheader(); w.writerows(summary)
        with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as f:
            f.write(to_markdown(summary))
        print("\n" + to_markdown(summary))
    print(f"Done. Results in {out}")


if __name__ == "__main__":
    main()
