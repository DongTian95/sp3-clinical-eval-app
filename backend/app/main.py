from __future__ import annotations

import os
import random
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER, HTTP_403_FORBIDDEN

from .db import get_db
from .models import (
    Case,
    ModelOutput,
    PerOutputEvaluation,
    OverallPreference,
    PairwiseComparison,
)
from .seed import init_and_seed

from fastapi.templating import Jinja2Templates


app = FastAPI(title="Clinical Model Evaluation Interface (Sample)")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"))

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    # create tables + seed sample data on first run
    init_and_seed()


def current_user(request: Request) -> Optional[str]:
    return request.session.get("user")


def require_user(request: Request) -> Optional[RedirectResponse]:
    if not current_user(request):
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    return None


def is_admin(user: str) -> bool:
    admins = [u.strip() for u in os.getenv("ADMIN_USERS", "admin").split(",") if u.strip()]
    return user in admins


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> Any:
    if not current_user(request):
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/queue", status_code=HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request) -> Any:
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login_post(request: Request, user: str = Form(...)) -> Any:
    user = user.strip()
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Please enter a name."},
        )
    request.session["user"] = user
    return RedirectResponse(url="/queue", status_code=HTTP_303_SEE_OTHER)


@app.get("/logout")
def logout(request: Request) -> Any:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)


@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)

    cases = db.scalars(select(Case).order_by(Case.id)).all()

    # progress: whether overall preference exists for (case, user)
    completed_case_ids = set(
        db.scalars(
            select(OverallPreference.case_id).where(OverallPreference.annotator == user)
        ).all()
    )

    # quick stats
    total_completed = len(completed_case_ids)
    total_cases = len(cases)

    # next case: first not completed
    next_case = next((c for c in cases if c.id not in completed_case_ids), None)

    return templates.TemplateResponse(
        "queue.html",
        {
            "request": request,
            "user": user,
            "cases": cases,
            "completed_case_ids": completed_case_ids,
            "total_completed": total_completed,
            "total_cases": total_cases,
            "next_case": next_case,
        },
    )


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def view_case(case_id: int, request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)

    case = db.get(Case, case_id)
    if not case:
        return HTMLResponse(f"Case {case_id} not found", status_code=404)

    outputs = list(case.outputs)

    # If user already submitted, load existing values to prefill
    existing_overall = db.scalar(
        select(OverallPreference).where(
            OverallPreference.case_id == case_id,
            OverallPreference.annotator == user,
        )
    )
    existing_per_output = {
        ev.output_id: ev
        for ev in db.scalars(
            select(PerOutputEvaluation).where(
                PerOutputEvaluation.case_id == case_id,
                PerOutputEvaluation.annotator == user,
            )
        ).all()
    }

    issue_options = [
        "hallucinated_finding",
        "wrong_laterality",
        "missed_critical_finding",
        "contradiction",
        "unclear_recommendation",
        "bad_formatting",
        "other",
    ]

    preference_reason_options = [
        "more_accurate",
        "more_complete",
        "clearer_language",
        "better_structure",
        "safer_recommendation",
    ]

    return templates.TemplateResponse(
        "case.html",
        {
            "request": request,
            "user": user,
            "case": case,
            "outputs": outputs,
            "existing_overall": existing_overall,
            "existing_per_output": existing_per_output,
            "issue_options": issue_options,
            "preference_reason_options": preference_reason_options,
        },
    )


@app.post("/cases/{case_id}/submit")
async def submit_case(case_id: int, request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)

    case = db.get(Case, case_id)
    if not case:
        return HTMLResponse(f"Case {case_id} not found", status_code=404)

    form = await request.form()
    best_output_id = int(form.get("best_output_id"))

    # Overall preference
    preference_tags = form.getlist("preference_tags")  # checkbox list
    overall_comment = (form.get("overall_comment") or "").strip()

    # Upsert overall preference
    existing_overall = db.scalar(
        select(OverallPreference).where(
            OverallPreference.case_id == case_id,
            OverallPreference.annotator == user,
        )
    )
    if existing_overall:
        existing_overall.best_output_id = best_output_id
        existing_overall.rationale_tags = {"tags": preference_tags}
        existing_overall.overall_comment = overall_comment
    else:
        db.add(
            OverallPreference(
                case_id=case_id,
                annotator=user,
                best_output_id=best_output_id,
                rationale_tags={"tags": preference_tags},
                overall_comment=overall_comment,
            )
        )

    # Per-output evaluations
    for out in case.outputs:
        acc = int(form.get(f"accuracy_{out.id}", "3"))
        comp = int(form.get(f"completeness_{out.id}", "3"))
        read = int(form.get(f"readability_{out.id}", "3"))
        tags = form.getlist(f"issues_{out.id}")
        correction = (form.get(f"correction_{out.id}") or "").strip()
        comment = (form.get(f"comment_{out.id}") or "").strip()

        existing_ev = db.scalar(
            select(PerOutputEvaluation).where(
                PerOutputEvaluation.case_id == case_id,
                PerOutputEvaluation.output_id == out.id,
                PerOutputEvaluation.annotator == user,
            )
        )
        if existing_ev:
            existing_ev.accuracy = acc
            existing_ev.completeness = comp
            existing_ev.readability = read
            existing_ev.issue_tags = {"tags": tags}
            existing_ev.suggested_correction = correction
            existing_ev.comment = comment
        else:
            db.add(
                PerOutputEvaluation(
                    case_id=case_id,
                    output_id=out.id,
                    annotator=user,
                    accuracy=acc,
                    completeness=comp,
                    readability=read,
                    issue_tags={"tags": tags},
                    suggested_correction=correction,
                    comment=comment,
                )
            )

    db.commit()
    return RedirectResponse(url="/queue", status_code=HTTP_303_SEE_OTHER)


@app.get("/cases/{case_id}/compare", response_class=HTMLResponse)
def compare(case_id: int, request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)

    case = db.get(Case, case_id)
    if not case:
        return HTMLResponse(f"Case {case_id} not found", status_code=404)

    outputs = list(case.outputs)
    if len(outputs) < 2:
        return HTMLResponse("Need at least 2 outputs for pairwise comparison", status_code=400)

    # Choose a random pair. In a real system you'd assign tasks deterministically.
    out_a, out_b = random.sample(outputs, 2)

    reason_options = [
        "more_accurate",
        "more_complete",
        "clearer_language",
        "better_structure",
        "safer_recommendation",
        "other",
    ]

    return templates.TemplateResponse(
        "compare.html",
        {
            "request": request,
            "user": user,
            "case": case,
            "out_a": out_a,
            "out_b": out_b,
            "reason_options": reason_options,
        },
    )


@app.post("/cases/{case_id}/compare/submit")
async def compare_submit(case_id: int, request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)

    form = await request.form()
    out_a_id = int(form.get("out_a_id"))
    out_b_id = int(form.get("out_b_id"))
    winner = form.get("winner")
    if winner not in ("a", "b"):
        return HTMLResponse("Please choose A or B", status_code=400)
    winner_output_id = out_a_id if winner == "a" else out_b_id

    reason_tags = form.getlist("reason_tags")
    comment = (form.get("comment") or "").strip()

    db.add(
        PairwiseComparison(
            case_id=case_id,
            annotator=user,
            output_a_id=out_a_id,
            output_b_id=out_b_id,
            winner_output_id=winner_output_id,
            reason_tags={"tags": reason_tags},
            comment=comment,
        )
    )
    db.commit()
    return RedirectResponse(url=f"/cases/{case_id}", status_code=HTTP_303_SEE_OTHER)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, db: Session = Depends(get_db)) -> Any:
    redirect = require_user(request)
    if redirect:
        return redirect
    user = current_user(request)
    if not is_admin(user):
        return HTMLResponse("Forbidden: admin only", status_code=HTTP_403_FORBIDDEN)

    # basic stats
    total_cases = db.scalar(select(func.count(Case.id)))
    total_outputs = db.scalar(select(func.count(ModelOutput.id)))
    total_per_output = db.scalar(select(func.count(PerOutputEvaluation.id)))
    total_overall = db.scalar(select(func.count(OverallPreference.id)))
    total_pairwise = db.scalar(select(func.count(PairwiseComparison.id)))

    # per-annotator progress
    annotators = db.scalars(select(OverallPreference.annotator).distinct()).all()
    annotator_rows = []
    for a in annotators:
        cases_done = db.scalar(
            select(func.count(OverallPreference.id)).where(OverallPreference.annotator == a)
        )
        per_out = db.scalar(
            select(func.count(PerOutputEvaluation.id)).where(PerOutputEvaluation.annotator == a)
        )
        pairwise = db.scalar(
            select(func.count(PairwiseComparison.id)).where(PairwiseComparison.annotator == a)
        )
        annotator_rows.append(
            {"annotator": a, "cases_done": cases_done, "per_output": per_out, "pairwise": pairwise}
        )
    annotator_rows.sort(key=lambda r: (-r["cases_done"], r["annotator"]))

    # simple agreement measure for pairwise: for each (case, unordered pair of outputs) compute fraction of majority
    comparisons = db.scalars(select(PairwiseComparison)).all()
    by_task: Dict[str, List[int]] = {}
    for c in comparisons:
        pair = tuple(sorted([c.output_a_id, c.output_b_id]))
        key = f"{c.case_id}:{pair[0]}:{pair[1]}"
        by_task.setdefault(key, []).append(c.winner_output_id)

    agreement_rows = []
    for key, winners in by_task.items():
        if len(winners) < 2:
            continue
        # majority vote agreement
        counts: Dict[int, int] = {}
        for w in winners:
            counts[w] = counts.get(w, 0) + 1
        majority = max(counts.values())
        agreement = majority / len(winners)
        case_id, a_id, b_id = key.split(":")
        agreement_rows.append(
            {
                "case_id": int(case_id),
                "pair": f"{a_id} vs {b_id}",
                "n": len(winners),
                "agreement": round(agreement, 3),
            }
        )
    agreement_rows.sort(key=lambda r: (-r["n"], -r["agreement"]))

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "stats": {
                "cases": total_cases,
                "outputs": total_outputs,
                "per_output_evals": total_per_output,
                "overall_prefs": total_overall,
                "pairwise": total_pairwise,
            },
            "annotator_rows": annotator_rows,
            "agreement_rows": agreement_rows[:20],
        },
    )
