import unittest

from app.services.opencode_execution_service import (
    OpenCodeEventState,
    _send_opencode_message_request,
    extract_opencode_error,
    extract_opencode_status_message,
    parse_opencode_sse_data,
    process_opencode_event,
    should_defer_opencode_sender_error,
    wait_for_opencode_response_from_events,
)


class OpenCodeExecutionServiceTests(unittest.TestCase):
    def test_defers_sender_read_timeout_while_waiting_for_events(self):
        import httpx

        self.assertTrue(
            should_defer_opencode_sender_error(httpx.ReadTimeout("timed out"))
        )
        self.assertFalse(
            should_defer_opencode_sender_error(RuntimeError("boom"))
        )

    def test_process_event_accumulates_text_until_idle(self):
        session_id = "ses_123"
        state = OpenCodeEventState()

        answer = process_opencode_event(
            state=state,
            event={
                "payload": {
                    "type": "message.updated",
                    "properties": {
                        "sessionID": session_id,
                        "info": {"id": "msg_assistant", "role": "assistant"},
                    },
                }
            },
            session_id=session_id,
        )
        self.assertIsNone(answer)

        answer = process_opencode_event(
            state=state,
            event={
                "payload": {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": session_id,
                        "part": {
                            "id": "part_1",
                            "messageID": "msg_assistant",
                            "type": "text",
                            "text": "Q3: Explain retries.",
                        },
                    },
                }
            },
            session_id=session_id,
        )
        self.assertIsNone(answer)

        answer = process_opencode_event(
            state=state,
            event={
                "payload": {
                    "type": "session.status",
                    "properties": {
                        "sessionID": session_id,
                        "status": {"type": "idle"},
                    },
                }
            },
            session_id=session_id,
        )
        self.assertEqual(answer, "Explain retries.")

    def test_extracts_status_message_from_session_status_payload(self):
        payload = {
            "type": "session.status",
            "properties": {
                "sessionID": "ses_123",
                "status": {
                    "type": "retry",
                    "attempt": 3,
                    "message": "auth_unavailable: no auth available",
                },
            },
        }

        self.assertEqual(
            extract_opencode_status_message(payload),
            "auth_unavailable: no auth available",
        )

    def test_send_message_request_omits_string_model_from_payload(self):
        class FakeResponse:
            content = b""

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {}

        class FakeClient:
            def __init__(self) -> None:
                self.request_json: dict | None = None

            def post(self, url: str, json: dict) -> FakeResponse:
                self.request_json = {"url": url, "json": json}
                return FakeResponse()

        client = FakeClient()

        payload = _send_opencode_message_request(
            client=client,
            session_id="ses_123",
            question_text="Reply with exactly OK.",
        )

        self.assertIsNone(payload)
        self.assertEqual(client.request_json["url"], "/session/ses_123/message")
        self.assertEqual(
            client.request_json["json"],
            {
                "agent": "plan",
                "parts": [{"type": "text", "text": "Reply with exactly OK."}],
                "stream": False,
            },
        )

    def test_extracts_payload_error_from_info_block(self):
        payload = {
            "info": {
                "error": {
                    "name": "APIError",
                    "data": {"message": "upstream provider rejected request"},
                }
            },
            "parts": [],
        }

        self.assertEqual(
            extract_opencode_error(payload),
            "upstream provider rejected request",
        )

    def test_parses_sse_data_lines_only(self):
        self.assertEqual(
            parse_opencode_sse_data('data: {"payload":{"type":"server.connected"}}'),
            {"payload": {"type": "server.connected"}},
        )
        self.assertIsNone(parse_opencode_sse_data("event: ping"))
        self.assertIsNone(parse_opencode_sse_data(""))

    def test_waits_for_assistant_text_parts_and_returns_cleaned_text(self):
        session_id = "ses_123"
        assistant_message_id = "msg_assistant"
        events = iter(
            [
                {
                    "directory": "/tmp/project",
                    "payload": {
                        "type": "message.updated",
                        "properties": {
                            "sessionID": session_id,
                            "info": {
                                "id": assistant_message_id,
                                "role": "assistant",
                            },
                        },
                    },
                },
                {
                    "directory": "/tmp/project",
                    "payload": {
                        "type": "message.part.updated",
                        "properties": {
                            "sessionID": session_id,
                            "part": {
                                "id": "part_1",
                                "messageID": assistant_message_id,
                                "type": "text",
                                "text": "Q2: Explain the runtime architecture.",
                            },
                        },
                    },
                },
                {
                    "directory": "/tmp/project",
                    "payload": {
                        "type": "session.status",
                        "properties": {
                            "sessionID": session_id,
                            "status": {"type": "idle"},
                        },
                    },
                },
            ]
        )

        answer = wait_for_opencode_response_from_events(
            event_iter=events,
            session_id=session_id,
        )

        self.assertEqual(answer, "Explain the runtime architecture.")

    def test_raises_when_assistant_error_arrives_over_event_stream(self):
        session_id = "ses_123"
        events = iter(
            [
                {
                    "directory": "/tmp/project",
                    "payload": {
                        "type": "message.updated",
                        "properties": {
                            "sessionID": session_id,
                            "info": {
                                "id": "msg_assistant",
                                "role": "assistant",
                                "error": {
                                    "name": "APIError",
                                    "data": {"message": "subscription missing"},
                                },
                            },
                        },
                    },
                }
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "subscription missing"):
            wait_for_opencode_response_from_events(
                event_iter=events,
                session_id=session_id,
            )


if __name__ == "__main__":
    unittest.main()
