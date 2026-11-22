"""The tools the chat can offer the model. Add a tool by adding a ToolDefinition to TOOLS."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from engine.types import JSON, Tool, ToolError, ToolSpec

from apps.integrations import selectors as integration_selectors
from apps.integrations import services as integration_services
from apps.integrations.models import Connection


@dataclass(frozen=True)
class ToolDefinition:
    spec: ToolSpec
    requires_approval: bool
    # Whether the user can use the tool now, such as whether they connected the account it needs.
    available: Callable[[object], bool]
    # What the system prompt tells the model when the tool is offered, and when it is not.
    offered_note: str
    missing_note: str
    # The result of an approved call when the tool stopped being available before it ran. Read by the user too.
    unavailable_error: str
    # Checks and cleans the model's arguments, given the user's time zone. Raises ToolError.
    prepare: Callable[[JSON, str], JSON]
    # Runs the tool as the user with prepared arguments, and returns the result the model reads. Raises ToolError.
    execute: Callable[[object, JSON], JSON]

    def bind(self, *, user, time_zone: str) -> Tool:
        return Tool(
            spec=self.spec,
            requires_approval=self.requires_approval,
            prepare=lambda arguments: self.prepare(arguments, time_zone),
            run=lambda arguments: self.execute(user, arguments),
        )


def offer(*, user, time_zone: str) -> tuple[list[Tool], list[str]]:
    """The tools the user can use now, ready for the engine, and the system prompt's note on every tool."""
    tools, notes = [], []
    for definition in TOOLS.values():
        if definition.available(user):
            tools.append(definition.bind(user=user, time_zone=time_zone))
            notes.append(definition.offered_note)
        else:
            notes.append(definition.missing_note)
    return tools, notes


def run_approved(*, user, name: str, arguments: JSON) -> JSON:
    """Runs a call the user approved, after checking that the tool is still available to them. Raises ToolError."""
    definition = TOOLS.get(name)
    if definition is None:
        raise ToolError(f"There is no tool named {name}.")
    if not definition.available(user):
        raise ToolError(definition.unavailable_error)
    return definition.execute(user, arguments)


def _prepare_event(arguments: JSON, time_zone: str) -> JSON:
    summary = arguments.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ToolError("Give the event a summary, such as its title.")
    zone_name = arguments.get("time_zone") or time_zone
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ToolError(f"{zone_name!r} is not an IANA time zone, such as Europe/Berlin.") from None
    start = _wall_clock(arguments.get("start"), zone, "start")
    end = _wall_clock(arguments.get("end"), zone, "end")
    if end <= start:
        raise ToolError("The event must end after it starts.")
    event = {"summary": summary.strip(), "start": start.isoformat(), "end": end.isoformat(), "time_zone": zone_name}
    description = arguments.get("description")
    if isinstance(description, str) and description.strip():
        event["description"] = description.strip()
    return event


def _wall_clock(value, zone: ZoneInfo, name: str) -> datetime:
    """A date-time as the clock in `zone` shows it, without an offset."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolError(f"Give {name} as an ISO 8601 date-time, such as 2026-11-23T15:00:00.") from None
    if moment.tzinfo is not None:
        moment = moment.astimezone(zone).replace(tzinfo=None)
    return moment.replace(microsecond=0)


def _create_event(user, event: JSON) -> JSON:
    try:
        return integration_services.create_calendar_event(
            user=user,
            summary=event["summary"],
            start=event["start"],
            end=event["end"],
            time_zone=event["time_zone"],
            description=event.get("description"),
        )
    except integration_services.CalendarError as error:
        raise ToolError(str(error)) from error


CREATE_CALENDAR_EVENT = ToolDefinition(
    spec=ToolSpec(
        name="create_calendar_event",
        description=(
            "Create an event in the user's Google Calendar. The user sees the event in the chat and approves or "
            "declines it before it is created. The result says whether it was created, declined, or failed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "The event's title, such as Design review."},
                "start": {
                    "type": "string",
                    "description": "When it starts: an ISO 8601 local date-time without an offset, such as 2026-11-23T15:00:00.",
                },
                "end": {"type": "string", "description": "When it ends, in the same form as start."},
                "time_zone": {
                    "type": "string",
                    "description": "The IANA time zone of start and end, such as Europe/Berlin. Defaults to the user's.",
                },
                "description": {"type": "string", "description": "Notes for the event, if the user gave any."},
            },
            "required": ["summary", "start", "end"],
            "additionalProperties": False,
        },
    ),
    requires_approval=True,
    available=lambda user: integration_selectors.has_connection(
        user=user, provider=Connection.Provider.GOOGLE_CALENDAR
    ),
    offered_note=(
        "You can add events to the user's Google Calendar with create_calendar_event. Use it whenever the user asks "
        "to schedule a meeting or an event. Write start and end as local date-times in the user's time zone, unless "
        "the user names another zone. If the title, the day, the start time, or the length is missing, ask for it "
        "instead of guessing. The user approves each event in the chat before it is created, so say an event was "
        "created only after the tool result says so."
    ),
    missing_note=(
        "You cannot add events to a calendar, because the user has not connected Google Calendar. When the user "
        "asks to schedule something, tell them to connect Google Calendar on the Integrations screen first."
    ),
    unavailable_error="Google Calendar is no longer connected. Connect it on the Integrations screen, then ask again.",
    prepare=_prepare_event,
    execute=_create_event,
)

TOOLS = {definition.spec.name: definition for definition in [CREATE_CALENDAR_EVENT]}
