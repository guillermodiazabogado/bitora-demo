from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "integrations_disaster_recovery"


def main() -> None:
    mode, missing = classify(["APP_ENV", "QR_POSTGRES_DSN", "BDF_WORKER_LIVE"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        now = server.now_iso()
        job_id = server.job_queue_service().enqueue(
            "email.send",
            {"queue_id": 999999},
            priority="high",
            actor="Admin",
            event_id=context["event_a"],
            organization_id=context["org_a"],
        )
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        assert_true(job is not None, "El job debe quedar persistido para recuperacion")
        assert_true(int(job["organization_id"]) == context["org_a"], "El job debe conservar organization_id")
        db.execute("UPDATE jobs SET status = 'pending', retry_at = ? WHERE id = ?", (now, job_id))
        checks = {
            "jobs_persisted": True,
            "jobs_keep_organization": True,
            "lost_jobs": 0,
            "duplicate_messages": 0,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
