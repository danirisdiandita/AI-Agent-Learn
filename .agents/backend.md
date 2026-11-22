# Backend layout

The Django backend is split into one app per business domain under `backend/apps/`. Every app has the same internal layout, and dependencies point in one direction. These rules keep the backend easy to navigate as it grows from one app to a dozen. `scripts/check.sh` runs `lint-imports`, which enforces the numbered rules with the contracts in `backend/.importlinter`.

## Folders

```text
backend/
├── config/                 Project wiring only: settings, root URLs, ASGI and WSGI
│   ├── settings/           base.py (shared), dev.py (default), prod.py
│   ├── checks.py           System checks over every model in apps/, loaded by apps.py
│   └── urls.py             Mounts each app's api/urls.py under /api/v1/<app>/
├── apps/
│   └── <domain>/           One Django app per business domain
│       ├── models.py       Tables. Split into a models/ package when the file passes about 300 lines
│       ├── services.py     Writes: create, update, delete, and the business rules around them
│       ├── selectors.py    Reads: query functions that return querysets or plain values
│       ├── api/            The HTTP boundary
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       ├── admin.py
│       ├── apps.py         name = "apps.<domain>", label = "<domain>"
│       ├── <module>.py     Optional plain modules, such as a client for an outside API (integrations/google.py)
│       ├── migrations/
│       └── tests/          test_api.py, test_services.py, test_selectors.py
├── engine/                 The agent loop in plain Python, with no Django (see The agent runtime)
├── app_template/           Template that scripts/new-backend-app.sh renders
├── .importlinter           Import contracts
├── requirements.txt        Runtime dependencies (Docker installs only these)
└── requirements-dev.txt    Runtime dependencies plus development tools
```

## Create an app

Run the generator from the repository root. Do not run `startapp` by hand.

```bash
scripts/new-backend-app.sh agents
```

The generator creates `backend/apps/agents/` in the layout above. It adds the app to `INSTALLED_APPS` and mounts its URLs at `/api/v1/agents/`. It refuses to overwrite an existing app.

## Rules

1. **Dependencies inside an app point down.** `api` may import `services`, `selectors`, and `models`. `services` and `selectors` may import `models`. `models` imports none of them.
2. **Only `config` and other `api` packages import an app's `api`.** Models, services, selectors, and admin never import any app's `api`.
3. **Apps depend only on apps below them in the domain order.** See the domain map below. An app may import the models, services, and selectors of a lower app. It never imports from a higher app. When a lower app must react to a higher one, use a Django signal or pass a callback in.

These rules need judgment, so no script checks them:

- **Views stay thin.** A view parses the request, calls one service or selector, and serializes the result. Business rules live in `services.py`, so the admin, management commands, and other apps can call them too.
- **Services take keyword-only arguments** and return model instances. Wrap a multi-step write in `transaction.atomic()`.
- **Selectors own query shape.** Put `select_related`, `prefetch_related`, and filtering in a selector. Views never build querysets.
- **Validate at the boundary.** Serializers validate request data. Services trust their arguments and enforce business rules, not types.
- **Test through the public surface.** Test endpoints in `tests/test_api.py` with the DRF `APIClient`. Test business rules by calling services directly.
- **Create a shared app only when two apps need the same code.** Do not create `common/` or `utils/` in advance.

## Names in the database

Every table, column, index, and constraint of a model in `apps/` has a snake_case name: lowercase words joined by underscores, such as `agents_chat_session` or `created_at`. `config/checks.py` enforces this as a Django system check, so `manage.py check`, `manage.py test`, and `scripts/check.sh` fail on a bad name.

- **Set `db_table` when the class name has more than one word.** Django's default table name runs the words together, such as `agents_chatsession` for `ChatSession`. Write `db_table = "agents_chat_session"` in the model's `Meta`. The check fails with `config.E002` until you do, and its hint names the table to use.
- **Keep field names snake_case.** A column takes its name from the field, and a foreign key adds `_id`, such as `user_id`. Do not set `db_column` to anything else.
- **Name each index and constraint after its table.** Use `<table>_<what>`, such as `agents_chat_message_role_valid`. Django limits index names to 30 characters, so shorten the table part of an index name, such as `agents_chat_msg_session_idx`.

A name that is not snake_case fails with `config.E001`.

## Domain map

`accounts`, `integrations`, and `agents` exist today. The other apps are planned. Create each one with the generator when its first feature starts, not before. The list is in dependency order: each app may depend on the apps below it.

| Order | App | Owns |
| --- | --- | --- |
| 8 | `evals` | Eval datasets and cases, eval runs, graders, and scores |
| 7 | `runs` | Runs of an agent: each step and tool call in order, token use, cost, and errors |
| 6 | `agents` | Agent definitions: model, instructions, sampling settings, the tools and knowledge each agent may use, and their versions. Chat sessions and their messages |
| 5 | `knowledge` | Knowledge bases, uploaded documents, chunks, embeddings, and retrieval settings |
| 4 | `tools` | Tool definitions with their JSON schemas, HTTP tools, and connected MCP servers |
| 3 | `integrations` | Connected third-party accounts (OAuth tokens) such as Google Calendar |
| 2 | `providers` | Model providers, encrypted API keys, and the models each provider offers |
| 1 | `accounts` | Users, sign-in, and JWT tokens |

The `domain-order` contract in `backend/.importlinter` lists the same order. If a new feature needs a different order, change the table and the contract in the same commit.

## The agent runtime

The agent loop lives in `backend/engine/`, a plain Python package that never imports Django, Django REST framework, or the apps. The `engine-is-plain-python` contract in `backend/.importlinter` enforces that, so the loop stays fast to test with a fake model client, and a model provider can be swapped without touching the apps.

- `engine/types.py` holds the data. Messages are `SystemMessage`, `UserMessage`, `AssistantMessage` (with its `ToolCall`s), and `ToolMessage` (one tool call's result). A `Tool` is a `ToolSpec` (name, description, JSON schema), `requires_approval`, `prepare` (checks and cleans the model's arguments), and `run`. Both raise `ToolError`, whose message goes back to the model.
- `engine/loop.py` has `run()`. It calls the model through a `ModelClient`, settles the tool calls the model asks for, and calls the model again until it answers or `MAX_STEPS` stops it. Each step yields its `TextDelta` events, then one event per tool call, then `Finished`. A call to a tool that needs approval yields `ToolCallRequested` and never runs inside the engine: the run ends after that step, and the caller runs the loop again once the user decided, with the results in the conversation. Every other call is settled at once as `ToolCallCompleted`: the tool ran, or the call named no offered tool, or `prepare` rejected its arguments.
- `engine/openrouter.py` has `OpenRouterClient`, which streams OpenRouter's chat completions with `stream: true`, and assembles the text and the tool-call fragments. It raises `ModelError`, whose message is for the user, and logs the underlying cause.
- `engine/testing.py` has `FakeClient`, which plays model steps back in order and records what each step was sent.
- `engine/tests/` holds unit tests that need no database. `manage.py test` runs them with the app tests. `engine/tests/fixtures/` holds streams recorded from OpenRouter.

An app that runs the loop turns its models into these types, passes a model client and the tools the user may use, and saves every step that `run()` yields. Model provider SDKs and HTTP clients belong behind `ModelClient`, so tests never call a real model. Read API keys from the `providers` app or the environment, never from code.

## The Agents chat

The chat in `apps/agents/` is the first caller of the engine. It saves every step, so the conversation the model reads is rebuilt from the database on each request.

- **Data.** `agents_chat_message` holds each user message and each model step. `agents_chat_tool_call` holds each tool call a step asked for, under that step's message, with `status` (`pending`, `approved` while the tool runs, `declined`, `succeeded`, `failed`), the `result` the model reads, and `decided_at`. A reply that only calls tools has empty `content`. `services._history` turns the rows back into engine messages: each reply with its calls, then one `ToolMessage` per call.
- **Tools.** `apps/agents/tools.py` lists each tool once in `TOOLS`, as a `ToolDefinition`: the `ToolSpec`, `requires_approval`, `available(user)`, the system prompt's note for when the tool is offered and for when it is not, `prepare`, and `execute`. `tools.offer()` binds the available tools to the user, so the model only sees tools the user can use. To add a tool, add a `ToolDefinition` to `TOOLS`; no service changes.
- **Streams.** `services.send_message`, `services.reply`, and `services.decide_tool_call` check every precondition and save what the user did before they return, so a refusal is a plain exception that the view answers as JSON. They then return an iterator of events, which the view sends as server-sent events (`api/views.py` lists them). Each model step is saved in one transaction when it finishes.
- **Approval.** A pending call blocks new messages in its session (409). A decision locks the call's row with `select_for_update`, so a second decision gets 409. An approved call runs before the stream starts, after `tools.run_approved` checks again that the tool is available, so a client that leaves mid-stream cannot leave it unrun. The model's follow-up starts once every call of the step is decided.
- **No transaction across a network call.** The model and Google are called outside `transaction.atomic()`. A session row lock lasts only while a step or a message is written.
- **Tests.** `apps/agents/tests/streams.py` posts to the streaming endpoints with `engine.testing.FakeClient` in place of the model and reads the events back. `apps/integrations/tests/fake_google.py` stands in for Google.
