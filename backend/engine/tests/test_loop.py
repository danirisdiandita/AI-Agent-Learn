import unittest

from engine.loop import run
from engine.testing import FakeClient, calls, reply
from engine.types import (
    AssistantMessage,
    Finished,
    ModelError,
    SystemMessage,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    ToolError,
    ToolMessage,
    ToolSpec,
    UserMessage,
)

QUESTION = [SystemMessage("Be brief."), UserMessage("Book a room")]


def tool(name, *, requires_approval, run=None, prepare=None):
    def refuse(arguments):
        raise AssertionError(f"{name} ran")

    return Tool(
        spec=ToolSpec(name, f"The {name} tool", {"type": "object"}),
        requires_approval=requires_approval,
        prepare=prepare or (lambda arguments: arguments),
        run=run or refuse,
    )


def require_room(arguments):
    if not arguments.get("room"):
        raise ToolError("Name the room.")
    return {"room": arguments["room"].strip()}


class LoopTests(unittest.TestCase):
    def test_a_reply_streams_its_text_then_finishes(self):
        client = FakeClient(reply("Hello there"))
        events = list(run(client=client, messages=QUESTION, tools=[]))
        self.assertEqual(events, [TextDelta("Hello"), TextDelta(" there"), Finished("Hello there", "fake/model")])
        self.assertEqual(client.sent, [(QUESTION, [])])

    def test_the_model_sees_the_specs_of_the_tools(self):
        book = tool("book_room", requires_approval=True)
        client = FakeClient(reply("Which room?"))
        list(run(client=client, messages=QUESTION, tools=[book]))
        self.assertEqual(client.sent[0][1], [book.spec])

    def test_a_tool_that_needs_approval_stops_the_run_without_running(self):
        book = tool("book_room", requires_approval=True, prepare=require_room)
        asked = ToolCall("call-1", "book_room", {"room": " Lisbon "})
        client = FakeClient(calls(asked, text="Booking it."))
        events = list(run(client=client, messages=QUESTION, tools=[book]))
        self.assertEqual(
            events,
            [
                TextDelta("Booking it."),
                ToolCallRequested("call-1", "book_room", {"room": "Lisbon"}),
                Finished("Booking it.", "fake/model", (asked,)),
            ],
        )
        self.assertEqual(len(client.sent), 1)

    def test_a_tool_without_approval_runs_and_the_model_reads_its_result(self):
        clock = tool("clock", requires_approval=False, run=lambda arguments: {"time": "15:00"})
        asked = ToolCall("call-1", "clock", {})
        client = FakeClient(calls(asked), reply("It is 3pm."))
        events = list(run(client=client, messages=QUESTION, tools=[clock]))
        self.assertEqual(
            events,
            [
                ToolCallCompleted("call-1", "clock", {}, {"time": "15:00"}, failed=False),
                Finished("", "fake/model", (asked,)),
                TextDelta("It"),
                TextDelta(" is"),
                TextDelta(" 3pm."),
                Finished("It is 3pm.", "fake/model"),
            ],
        )
        self.assertEqual(
            client.sent[1][0],
            [*QUESTION, AssistantMessage("", (asked,)), ToolMessage("call-1", {"time": "15:00"})],
        )

    def test_unusable_arguments_go_back_to_the_model_without_asking_the_user(self):
        book = tool("book_room", requires_approval=True, prepare=require_room)
        bad = ToolCall("call-1", "book_room", {"room": ""})
        good = ToolCall("call-2", "book_room", {"room": "Oslo"})
        client = FakeClient(calls(bad), calls(good))
        events = list(run(client=client, messages=QUESTION, tools=[book]))
        self.assertEqual(events[0], ToolCallCompleted("call-1", "book_room", {"room": ""}, {"error": "Name the room."}, True))
        self.assertIn(ToolMessage("call-1", {"error": "Name the room."}), client.sent[1][0])
        self.assertEqual(events[2], ToolCallRequested("call-2", "book_room", {"room": "Oslo"}))
        self.assertEqual(len(client.sent), 2)

    def test_a_call_to_a_tool_that_was_not_offered_fails(self):
        asked = ToolCall("call-1", "delete_everything", {})
        client = FakeClient(calls(asked), reply("Sorry."))
        events = list(run(client=client, messages=QUESTION, tools=[]))
        failure = ToolCallCompleted("call-1", "delete_everything", {}, {"error": "There is no tool named delete_everything."}, True)
        self.assertEqual(events[0], failure)
        self.assertEqual(events[-1], Finished("Sorry.", "fake/model"))

    def test_a_tool_that_fails_reports_the_error_to_the_model(self):
        def broken(arguments):
            raise ToolError("The clock is broken.")

        clock = tool("clock", requires_approval=False, run=broken)
        client = FakeClient(calls(ToolCall("call-1", "clock", {})), reply("I could not tell the time."))
        events = list(run(client=client, messages=QUESTION, tools=[clock]))
        self.assertEqual(events[0], ToolCallCompleted("call-1", "clock", {}, {"error": "The clock is broken."}, True))
        self.assertIn(ToolMessage("call-1", {"error": "The clock is broken."}), client.sent[1][0])

    def test_a_step_with_any_call_that_needs_approval_settles_the_others_and_stops(self):
        book = tool("book_room", requires_approval=True)
        clock = tool("clock", requires_approval=False, run=lambda arguments: {"time": "15:00"})
        client = FakeClient(calls(ToolCall("a", "clock", {}), ToolCall("b", "book_room", {"room": "Oslo"})))
        events = list(run(client=client, messages=QUESTION, tools=[book, clock]))
        self.assertEqual(
            [type(event) for event in events], [ToolCallCompleted, ToolCallRequested, Finished]
        )
        self.assertEqual(len(client.sent), 1)

    def test_the_step_limit_stops_a_model_that_keeps_calling_tools(self):
        clock = tool("clock", requires_approval=False, run=lambda arguments: {"time": "15:00"})
        client = FakeClient(*(calls(ToolCall(f"call-{i}", "clock", {})) for i in range(3)))
        with self.assertRaises(ModelError):
            list(run(client=client, messages=QUESTION, tools=[clock], max_steps=3))
        self.assertEqual(len(client.sent), 3)

    def test_a_model_error_ends_the_run_after_the_text_that_arrived(self):
        client = FakeClient([TextDelta("Hel"), ModelError("Cannot reach OpenRouter.")])
        events = run(client=client, messages=QUESTION, tools=[])
        self.assertEqual(next(events), TextDelta("Hel"))
        with self.assertRaises(ModelError):
            next(events)

    def test_a_stream_that_ends_without_finishing_is_an_error(self):
        client = FakeClient([TextDelta("Hel")])
        with self.assertRaises(ModelError):
            list(run(client=client, messages=QUESTION, tools=[]))
