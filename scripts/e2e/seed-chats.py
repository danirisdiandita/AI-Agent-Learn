# Saves the chats that the e2e drives, so it never calls a model or Google. Run it through scripts/e2e-dashboard.sh:
#   E2E_EMAIL=<email> E2E_CALENDAR_EMAIL=<email> .venv/bin/python manage.py shell < ../scripts/e2e/seed-chats.py
# E2E_EMAIL gets two chats that scripts/e2e/signin.mjs opens, reloads, and deletes. It expects these titles, the first
# user message of each session, with "Write a system prompt" newer.
# E2E_CALENDAR_EMAIL gets a Google Calendar connection with fake tokens, and one chat whose last reply asks to create
# a calendar event that waits for approval. scripts/e2e/calendar.mjs declines it.
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.agents.models import ChatSession
from apps.integrations.models import Connection

user = get_user_model().objects.get(email=os.environ["E2E_EMAIL"])
model = "e2e/seeded-model"
chats = [
    [
        ("user", "What is a tool call?"),
        (
            "assistant",
            "A tool call is a step where the model asks the agent to run a tool, such as a search or an HTTP "
            "request, and waits for the result before it answers.",
        ),
        ("user", "Who runs the tool, the model or the backend?"),
        (
            "assistant",
            "The backend runs it. The model only names the tool and its arguments. The backend calls the tool, "
            "then sends the result back to the model as the next message.",
        ),
    ],
    [
        ("user", "Write a system prompt for a support agent"),
        (
            "assistant",
            "You answer questions about our product. Be brief and exact. When you do not know, say so and offer to "
            "hand the question to a person.",
        ),
    ],
]
for chat in chats:
    session = ChatSession.objects.create(user=user)
    for role, content in chat:
        session.messages.create(role=role, content=content, model=model if role == "assistant" else None)

calendar_user = get_user_model().objects.get(email=os.environ["E2E_CALENDAR_EMAIL"])
Connection.objects.create(
    user=calendar_user,
    provider=Connection.Provider.GOOGLE_CALENDAR,
    account_email="e2e-calendar@example.com",
    refresh_token="e2e-fake-refresh-token",
    access_token="e2e-fake-access-token",
    access_token_expires_at=timezone.now() + timedelta(hours=1),
    scopes="openid email https://www.googleapis.com/auth/calendar",
)
session = ChatSession.objects.create(user=calendar_user)
session.messages.create(role="user", content="Put a design review with the team on Monday Dec 7 at 3pm Berlin time")
asked = session.messages.create(role="assistant", content="", model=model)
asked.tool_calls.create(
    call_id="e2e-call-1",
    name="create_calendar_event",
    arguments={
        "summary": "Design review",
        "start": "2026-12-07T15:00:00",
        "end": "2026-12-07T15:45:00",
        "time_zone": "Europe/Berlin",
        "description": "Walk through the new onboarding screens.",
    },
)
