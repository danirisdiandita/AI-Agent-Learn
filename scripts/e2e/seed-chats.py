# Saves two chat sessions for the e2e user, so scripts/e2e/signin.mjs can open, reload, and delete them without
# calling a model. Run it through scripts/e2e-dashboard.sh:
#   E2E_EMAIL=<email> .venv/bin/python manage.py shell < ../scripts/e2e/seed-chats.py
# signin.mjs expects these titles, the first user message of each session, with "Write a system prompt" newer.
import os

from django.contrib.auth import get_user_model

from apps.agents.models import ChatSession

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
