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
| 7 | `runs` | Runs of an agent: conversations, messages, each step and tool call in order, token use, cost, and errors |
| 6 | `agents` | Agent definitions: model, instructions, sampling settings, the tools and knowledge each agent may use, and their versions |
| 5 | `knowledge` | Knowledge bases, uploaded documents, chunks, embeddings, and retrieval settings |
| 4 | `tools` | Tool definitions with their JSON schemas, HTTP tools, and connected MCP servers |
| 3 | `integrations` | Connected third-party accounts (OAuth tokens) such as Google Calendar |
| 2 | `providers` | Model providers, encrypted API keys, and the models each provider offers |
| 1 | `accounts` | Users, sign-in, and JWT tokens |

The `domain-order` contract in `backend/.importlinter` lists the same order. If a new feature needs a different order, change the table and the contract in the same commit.

## The agent runtime

Keep the agent loop in a plain Python package, `backend/engine/`, that never imports Django. It takes an agent definition, the conversation so far, a model client, and the tools as plain Python types. It calls the model, runs the tool calls the model asks for, and yields each step until the model gives a final answer or a step limit stops it. The `runs` app turns models into the engine's input types, calls the engine, and saves every step it yields. This keeps the loop fast to test with a fake model client, and makes it possible to swap model providers. When you create `backend/engine/`, add it to `root_packages` in `backend/.importlinter`, and add a `forbidden` contract that stops it from importing `django`, `rest_framework`, and `apps`.

Model provider SDKs, such as `anthropic`, belong behind a small client interface in `engine/`, so tests never call a real model. Read API keys from the `providers` app or the environment, never from code.
