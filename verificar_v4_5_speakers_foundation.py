import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_5_speakers.sqlite3")
os.environ["BITORA_SPEAKERS_V4_ENABLED"] = "true"
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def seed(db):
    now = server.now_iso()
    orgs = []
    events = []
    activities = {}
    for org_name in ("Alfa Speakers", "Beta Speakers"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    for org_index, org_id in enumerate(orgs):
        for event_index in range(2):
            event = db.execute(
                "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (org_id, f"Evento Speakers {org_index}-{event_index}", "2026-11-01T09:00:00+00:00", "2026-11-01T18:00:00+00:00", now),
            )
            event_id = int(event.lastrowid)
            events.append(event_id)
            space = db.execute("INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, ?, 100, 'active', ?)", (event_id, f"Sala {event_id}", now))
            activity = db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, starts_at, ends_at, capacity,
                    reservation_mode, requiere_asistencia, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 100, 'optional', 1, 'published', ?)
                """,
                (event_id, int(space.lastrowid), "Panel principal", "2026-11-01T10:00:00+00:00", "2026-11-01T11:00:00+00:00", now),
            )
            activities[event_id] = int(activity.lastrowid)
    return {"orgs": orgs, "events": events, "activities": activities}


def main():
    server.init_db()
    service = server.speaker_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id = data["orgs"][0]
    other_org_id = data["orgs"][1]
    event_id = data["events"][0]
    other_event_id = data["events"][2]
    activity_id = data["activities"][event_id]
    other_activity_id = data["activities"][other_event_id]

    with server.connect() as db:
        assert_true(server.speakers_v4_enabled(db, event_id), "feature flag de speakers no habilitado")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        profile = service.create_profile(
            db,
            organization_id=org_id,
            actor="Admin",
            data={
                "display_name": "Dra. Ada Speaker",
                "first_name": "Ada",
                "last_name": "Speaker",
                "professional_name": "Ada S.",
                "title": "Keynote",
                "position": "Directora",
                "company": "BITORA Labs",
                "short_bio": "Especialista en eventos.",
                "long_bio": "Biografia extendida controlada.",
                "email": "ada.speaker@example.test",
                "phone": "+5491100000000",
                "document_id": "DOC-123",
                "technical_needs": "HDMI",
                "links": [{"label": "Sitio", "url": "https://example.test/ada"}],
                "visibility": "PUBLIC",
            },
        )["item"]
        assert_true(profile["private"]["email"] == "ada.speaker@example.test", "datos privados no guardados")
        try:
            service.create_profile(db, organization_id=org_id, actor="Admin", data={"display_name": "<script>x</script>"})
            raise AssertionError("perfil inseguro aceptado")
        except server.SpeakerDomainError as exc:
            assert_true(exc.code == "SPEAKER_TEXT_UNSAFE", "sanitizacion incorrecta")

        published = service.publish_profile(db, organization_id=org_id, profile_id=profile["id"], actor="Admin")["item"]
        service.update_profile(db, organization_id=org_id, profile_id=profile["id"], actor="Admin", data={"short_bio": "Cambio posterior"})
        published_again = service.publish_profile(db, organization_id=org_id, profile_id=profile["id"], actor="Admin")["item"]
        assert_true(published_again["version_number"] == published["version_number"] + 1, "versionado publicado no avanza")
        first_snapshot = db.execute("SELECT snapshot_json FROM speaker_profile_versions WHERE id = ?", (published["id"],)).fetchone()["snapshot_json"]
        assert_true("Especialista en eventos" in first_snapshot, "version publicada no conserva snapshot")

        event_assignment = service.assign_to_event(db, organization_id=org_id, event_id=event_id, profile_id=profile["id"], actor="Admin", roles=["SPEAKER", "PANELIST"])["item"]
        assert_true("PANELIST" in event_assignment["roles"], "roles multiples no guardados")
        activity_assignment = service.assign_to_activity(db, organization_id=org_id, event_id=event_id, profile_id=profile["id"], activity_id=activity_id, actor="Admin", role="MODERATOR")["item"]
        assert_true(activity_assignment["activity_id"] == activity_id, "asignacion a actividad incorrecta")
        try:
            service.assign_to_activity(db, organization_id=org_id, event_id=event_id, profile_id=profile["id"], activity_id=other_activity_id, actor="Admin", role="SPEAKER")
            raise AssertionError("actividad de otro evento aceptada")
        except server.SpeakerDomainError as exc:
            assert_true(exc.code == "SPEAKER_SCOPE_MISMATCH", "actividad cross-event no rechazada")
        try:
            service.list_profiles(db, organization_id=other_org_id, event_id=event_id)
            raise AssertionError("listado cross-org aceptado")
        except server.SpeakerDomainError:
            pass

        doc = service.add_document(
            db,
            organization_id=org_id,
            event_id=event_id,
            profile_id=profile["id"],
            actor="Admin",
            filename="foto.png",
            mime_type="image/png",
            content=b"\x89PNG\r\nBITORA",
            document_type="PHOTO",
            visibility="PUBLIC",
        )["item"]
        assert_true("storage_key" not in doc, "documento expone ruta de storage")
        try:
            service.add_document(db, organization_id=org_id, event_id=event_id, profile_id=profile["id"], actor="Admin", filename="../x.png", mime_type="image/png", content=b"x")
            raise AssertionError("path traversal aceptado")
        except server.SpeakerDomainError as exc:
            assert_true(exc.code == "SPEAKER_DOCUMENT_INVALID", "path traversal no rechazado")

        token = service.create_access_token(db, organization_id=org_id, profile_id=profile["id"], actor="Admin")["token"]
        token_row = db.execute("SELECT token_hash, token_hint FROM speaker_access_tokens WHERE speaker_profile_id = ?", (profile["id"],)).fetchone()
        assert_true(token not in token_row["token_hash"], "token completo almacenado")
        public_self = service.self_service_profile(db, token=token)
        assert_true("private" not in public_self["profile"], "autogestion expone datos privados")
        service.self_service_update(db, token=token, data={"short_bio": "Actualizacion autogestiva", "email": "leak@example.test"})
        private_after = db.execute("SELECT email FROM speaker_private_details WHERE speaker_profile_id = ?", (profile["id"],)).fetchone()["email"]
        assert_true(private_after == "ada.speaker@example.test", "autogestion modifico dato privado")

        public_event = service.public_event_speakers(db, event_id=event_id)
        assert_true(public_event["items"] and "private" not in public_event["items"][0], "endpoint publico expone privado")
        public_profile = service.public_profile(db, public_id=profile["public_id"])
        assert_true(public_profile["profile"]["public_id"] == profile["public_id"], "perfil publico no disponible")

        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action LIKE 'speakers.%'").fetchone()["c"]
        assert_true(int(audit_count) >= 7, "auditoria insuficiente")
        db.execute("COMMIT")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    restored = server.event_restore_service().restore_bytes(bundle.read_bytes(), mode="new_event", actor="test", new_event_name="Evento speakers restaurado")
    assert_true(restored["ok"], "restore de speakers fallo")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_counts = {
            table: db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            for table in ("speaker_event_assignments", "speaker_activity_assignments", "speaker_documents")
        }
        assert_true(all(int(value) > 0 for value in restored_counts.values()), f"restore incompleto: {restored_counts}")
        restored_token = db.execute(
            """
            SELECT sat.status
            FROM speaker_access_tokens sat
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = sat.speaker_profile_id
            WHERE sea.event_id = ?
            LIMIT 1
            """,
            (restored_event_id,),
        ).fetchone()
        assert_true(restored_token and restored_token["status"] == "RESTORED_INACTIVE", "token restaurado no quedo inactivo")
        restored_doc = db.execute("SELECT storage_key FROM speaker_documents WHERE event_id = ? LIMIT 1", (restored_event_id,)).fetchone()
        assert_true(f"events/{restored_event_id}/" in restored_doc["storage_key"], "storage de documento no fue remapeado")

    print("V4.5 speakers foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
