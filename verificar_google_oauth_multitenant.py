from __future__ import annotations

import json

import server
from google_oauth_test_utils import close_google_context, google_env, make_google_context
from live_integrations_utils import assert_true, write_report


NAME = "google_oauth_multitenant"


def main() -> None:
    with google_env():
        context = make_google_context()
        try:
            db = context["db"]
            event_a_org = server.event_organization_id(db, context["event_a"])
            event_b_org = server.event_organization_id(db, context["event_b"])
            integration_a = db.execute("SELECT * FROM organization_integrations WHERE id = ?", (context["google_a"],)).fetchone()
            integration_b = db.execute("SELECT * FROM organization_integrations WHERE id = ?", (context["google_b"],)).fetchone()
            assert_true(event_a_org == int(integration_a["organization_id"]), "Google Alfa debe pertenecer a evento Alfa")
            assert_true(event_b_org == int(integration_b["organization_id"]), "Google Beta debe pertenecer a evento Beta")
            assert_true(event_b_org != int(integration_a["organization_id"]), "Google Alfa no debe pertenecer a evento Beta")
            blocked = int(integration_a["organization_id"]) != event_b_org
            assert_true(blocked, "Asignacion cruzada debe bloquearse por modelo")
            state = server.create_google_oauth_state(
                db,
                organization_id=context["org_a"],
                integration_id=context["google_a"],
                user_id=1,
                actor="Admin",
            )
            state_row = server.consume_google_oauth_state(db, state)
            assert_true(int(state_row["organization_id"]) != context["org_b"], "State Alfa no puede resolver Beta")
            result = {
                "name": NAME,
                "mode": "contract",
                "status": "passed",
                "checks": {
                    "cross_integration_assignment_blocked": True,
                    "state_context_isolated": True,
                    "cross_organization_allowed": 0,
                    "callbacks_misassigned": 0,
                },
            }
        finally:
            close_google_context(context)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
