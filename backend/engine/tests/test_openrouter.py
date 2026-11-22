import io
import json
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from engine.openrouter import OpenRouterClient, assemble, sse_data
from engine.types import (
    AssistantMessage,
    Finished,
    ModelError,
    SystemMessage,
    TextDelta,
    ToolCall,
    ToolMessage,
    ToolSpec,
    UserMessage,
)

# Streams that OpenRouter sent for openai/gpt-5.6-luna, recorded byte for byte.
FIXTURES = Path(__file__).parent / "fixtures"


def recorded(name):
    return (FIXTURES / name).read_bytes().splitlines(keepends=True)


def chunk(delta=None, **fields):
    return json.dumps({"model": "vendor/model", "choices": [{"index": 0, "delta": delta or {}}], **fields})


def tool_part(index, *, id=None, name=None, arguments=None):
    function = {key: value for key, value in (("name", name), ("arguments", arguments)) if value is not None}
    return {"index": index, **({"id": id, "type": "function"} if id else {}), "function": function}


class RecordedStreamTests(unittest.TestCase):
    def test_a_text_reply_arrives_in_pieces_that_add_up_to_the_whole(self):
        events = list(assemble(sse_data(recorded("text.sse")), model="requested/model"))
        deltas, finished = events[:-1], events[-1]
        self.assertGreater(len(deltas), 1)
        self.assertTrue(all(isinstance(event, TextDelta) for event in deltas))
        self.assertEqual(finished, Finished("Hello! Nice to meet you today.", "openai/gpt-5.6-luna"))
        self.assertEqual("".join(delta.text for delta in deltas), finished.content)

    def test_a_tool_call_is_assembled_from_its_fragments(self):
        events = list(assemble(sse_data(recorded("tool_call.sse")), model="requested/model"))
        self.assertEqual(
            events,
            [
                Finished(
                    "",
                    "openai/gpt-5.6-luna",
                    (
                        ToolCall(
                            "call_ba206f8723fc4699b450cd2c71e2ece0",
                            "create_calendar_event",
                            {
                                "summary": "Design review",
                                "start": "2026-11-23T15:00:00",
                                "end": "2026-11-23T15:30:00",
                                "time_zone": "Asia/Jakarta",
                            },
                        ),
                    ),
                )
            ],
        )


class SseTests(unittest.TestCase):
    def test_comments_are_skipped_and_done_ends_the_stream(self):
        lines = [b": OPENROUTER PROCESSING\n", b"\n", b'data: {"a": 1}\n', b"\n", b"data: [DONE]\n", b"\n", b'data: {"late": 1}\n', b"\n"]
        self.assertEqual(list(sse_data(lines)), ['{"a": 1}'])

    def test_data_lines_of_one_event_are_joined_and_crlf_is_accepted(self):
        lines = [b"data: {\"a\":\r\n", b"data: 1}\r\n", b"\r\n"]
        self.assertEqual(list(sse_data(lines)), ['{"a":\n1}'])

    def test_an_event_without_a_closing_blank_line_still_counts(self):
        self.assertEqual(list(sse_data([b'data: {"a": 1}\n'])), ['{"a": 1}'])


class AssembleTests(unittest.TestCase):
    def test_two_tool_calls_interleaved_by_index(self):
        payloads = [
            chunk({"tool_calls": [tool_part(0, id="c0", name="first", arguments="")]}),
            chunk({"tool_calls": [tool_part(1, id="c1", name="second", arguments='{"b"')]}),
            chunk({"tool_calls": [tool_part(0, arguments='{"a": 1}')]}),
            chunk({"tool_calls": [tool_part(1, arguments=": 2}")]}),
        ]
        finished = list(assemble(payloads, model="requested"))[-1]
        self.assertEqual(finished.tool_calls, (ToolCall("c0", "first", {"a": 1}), ToolCall("c1", "second", {"b": 2})))

    def test_arguments_that_are_not_a_json_object_become_empty(self):
        for arguments in ('{"a": ', "[1, 2]"):
            with self.subTest(arguments=arguments), self.assertLogs("engine.openrouter"):
                payloads = [chunk({"tool_calls": [tool_part(0, id="c0", name="tool", arguments=arguments)]})]
                self.assertEqual(list(assemble(payloads, model="m"))[-1].tool_calls, (ToolCall("c0", "tool", {}),))

    def test_a_call_without_an_id_gets_one_from_its_index(self):
        payloads = [chunk({"tool_calls": [tool_part(2, name="tool", arguments="{}")]})]
        self.assertEqual(list(assemble(payloads, model="m"))[-1].tool_calls, (ToolCall("call_2", "tool", {}),))

    def test_a_stream_that_names_no_model_reports_the_requested_one(self):
        payloads = [json.dumps({"choices": [{"delta": {"content": "Hi"}}]})]
        self.assertEqual(list(assemble(payloads, model="requested")), [TextDelta("Hi"), Finished("Hi", "requested")])

    def test_an_error_chunk_stops_the_reply(self):
        payloads = [chunk({"content": "Hel"}), json.dumps({"error": {"code": 502, "message": "Provider returned error"}})]
        events = assemble(payloads, model="m")
        self.assertEqual(next(events), TextDelta("Hel"))
        with self.assertLogs("engine.openrouter"), self.assertRaisesRegex(ModelError, "Provider returned error"):
            next(events)

    def test_a_chunk_that_is_not_json_is_an_error(self):
        with self.assertRaises(ModelError):
            list(assemble(["not json"], model="m"))


class FakeStream(io.BytesIO):
    def __init__(self, body):
        super().__init__(body)


class ClientTests(unittest.TestCase):
    client = OpenRouterClient(api_key="test-key", model="vendor/model")
    spec = ToolSpec("create_calendar_event", "Create an event.", {"type": "object", "properties": {}})

    def stream(self, urlopen, messages=(UserMessage("Hi"),), tools=()):
        with mock.patch("urllib.request.urlopen", urlopen) as patched:
            events = list(self.client.stream(messages=list(messages), tools=list(tools)))
        return events, patched

    def test_the_request_asks_for_a_stream_with_the_key_and_the_model(self):
        urlopen = mock.Mock(return_value=FakeStream(b"".join(recorded("text.sse"))))
        events, _ = self.stream(urlopen)
        self.assertEqual(events[-1].content, "Hello! Nice to meet you today.")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual((body["model"], body["stream"]), ("vendor/model", True))
        self.assertNotIn("tools", body)

    def test_the_conversation_and_tools_go_out_in_the_openai_format(self):
        urlopen = mock.Mock(return_value=FakeStream(b"data: [DONE]\n\n"))
        call = ToolCall("call-1", "create_calendar_event", {"summary": "Standup"})
        messages = [
            SystemMessage("Be brief."),
            UserMessage("Book it"),
            AssistantMessage("", (call,)),
            ToolMessage("call-1", {"declined": True}),
            AssistantMessage("Okay."),
        ]
        self.stream(urlopen, messages=messages, tools=[self.spec])
        body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(
            body["messages"],
            [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": "Book it"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "create_calendar_event", "arguments": '{"summary": "Standup"}'},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "content": '{"declined": true}'},
                {"role": "assistant", "content": "Okay."},
            ],
        )
        self.assertEqual(
            body["tools"],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "create_calendar_event",
                        "description": "Create an event.",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )

    def test_a_refused_request_is_a_model_error_and_is_logged(self):
        refused = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b"rate limited"))
        with self.assertLogs("engine.openrouter") as logs, self.assertRaisesRegex(ModelError, "HTTP 429"):
            self.stream(mock.Mock(side_effect=refused))
        self.assertIn("rate limited", logs.output[0])

    def test_an_unreachable_server_is_a_model_error_and_logs_the_reason(self):
        failure = urllib.error.URLError("certificate verify failed")
        with self.assertLogs("engine.openrouter") as logs, self.assertRaisesRegex(ModelError, "Cannot reach"):
            self.stream(mock.Mock(side_effect=failure))
        self.assertIn("certificate verify failed", logs.output[0])

    def test_a_stream_that_breaks_off_is_a_model_error(self):
        class Broken(FakeStream):
            def __iter__(self):
                yield b'data: {"choices": [{"delta": {"content": "Hel"}}]}\n'
                yield b"\n"
                raise TimeoutError("timed out")

        with self.assertLogs("engine.openrouter"), self.assertRaisesRegex(ModelError, "broke off"):
            self.stream(mock.Mock(return_value=Broken(b"")))
