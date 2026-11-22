"""System checks for every model in apps/. `manage.py check`, `manage.py test`, and scripts/check.sh run them.

Every table, column, index, and constraint name is snake_case. Django's default table name runs the words of a class
name together, such as agents_chatsession for ChatSession, so a model whose class name has more than one word sets
db_table.
"""

import re

from django.apps import apps
from django.core import checks

SNAKE_CASE = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")
# Where a new word starts in a class name: ChatSession is Chat|Session, OAuthToken is O|Auth|Token.
WORD_START = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@checks.register(checks.Tags.models)
def check_snake_case_names(app_configs=None, **kwargs):
    configs = apps.get_app_configs() if app_configs is None else app_configs
    return [
        error
        for config in configs
        if config.name.startswith("apps.")
        for model in config.get_models(include_auto_created=True)
        for error in model_errors(model)
    ]


def model_errors(model):
    opts = model._meta
    names = [(f"table {opts.db_table!r}", opts.db_table)]
    names += [(f"column {f.column!r} of field {f.name}", f.column) for f in opts.local_concrete_fields]
    names += [(f"index {index.name!r}", index.name) for index in opts.indexes]
    names += [(f"constraint {constraint.name!r}", constraint.name) for constraint in opts.constraints]
    errors = [
        checks.Error(
            f"The {what} is not snake_case.",
            hint="Use lowercase words joined by underscores, such as agents_chat_session or created_at.",
            obj=model,
            id="config.E001",
        )
        for what, name in names
        if not SNAKE_CASE.fullmatch(name)
    ]
    words = WORD_START.split(model.__name__)
    if len(words) > 1 and opts.db_table == f"{opts.app_label}_{opts.model_name}":
        errors.append(
            checks.Error(
                f"The table name {opts.db_table!r} is Django's default, which runs the words of {model.__name__} together.",
                hint=f'Set db_table = "{opts.app_label}_{"_".join(words).lower()}" in its Meta.',
                obj=model,
                id="config.E002",
            )
        )
    return errors
