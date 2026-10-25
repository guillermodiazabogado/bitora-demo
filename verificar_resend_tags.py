from backend.services.email import ResendEmailProvider


def main():
    provider = ResendEmailProvider(api_key="test", from_email="test@example.com")
    captured = {}

    def request(method, path, payload):
        captured.update(payload)
        return {"id": "test-id"}

    provider._request = request
    result = provider.send_email(
        to="test@example.com", subject="Test", html="Test",
        metadata={"integration_id": "", "event_id": "18", "event name": "Neuquen / test", "zero": 0, "missing": None},
    )
    assert result.ok
    assert captured["tags"] == [
        {"name": "event_id", "value": "18"},
        {"name": "event_name", "value": "Neuquen___test"},
        {"name": "zero", "value": "0"},
    ], captured
    print("Resend tag regression: PASS")


if __name__ == "__main__":
    main()
