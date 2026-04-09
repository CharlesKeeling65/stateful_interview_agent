import unittest

from app.services.opencode_execution_service import (
    extract_opencode_error,
    parse_opencode_sse_data,
    wait_for_opencode_response_from_events,
)


class OpenCodeExecutionServiceTests(unittest.TestCase):
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
