from django.core import checks
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


def naming_errors(app_configs=None):
    """The (id, model name) of each naming error that `manage.py check` reports for these app configs."""
    return [
        (error.id, error.obj.__name__)
        for error in checks.run_checks(app_configs=app_configs)
        if error.id.startswith("config.")
    ]


class SnakeCaseNamesTests(SimpleTestCase):
    def test_every_model_in_apps_passes(self):
        self.assertEqual(naming_errors(), [])

    @isolate_apps("apps.agents", kwarg_name="registry")
    def test_snake_case_names_pass(self, registry):
        class ToolCall(models.Model):
            step_number = models.IntegerField()

            class Meta:
                app_label = "agents"
                db_table = "agents_tool_call"
                indexes = [models.Index(fields=["step_number"], name="agents_tool_call_step_idx")]

        self.assertEqual(naming_errors([registry.get_app_config("agents")]), [])

    @isolate_apps("apps.agents", kwarg_name="registry")
    def test_default_table_of_a_multi_word_model_fails(self, registry):
        class ToolCall(models.Model):
            class Meta:
                app_label = "agents"

        self.assertEqual(naming_errors([registry.get_app_config("agents")]), [("config.E002", "ToolCall")])

    @isolate_apps("apps.agents", kwarg_name="registry")
    def test_camel_case_table_fails(self, registry):
        class Step(models.Model):
            class Meta:
                app_label = "agents"
                db_table = "agents_runStep"

        self.assertEqual(naming_errors([registry.get_app_config("agents")]), [("config.E001", "Step")])

    @isolate_apps("apps.agents", kwarg_name="registry")
    def test_camel_case_column_fails(self, registry):
        class Step(models.Model):
            stepNumber = models.IntegerField()

            class Meta:
                app_label = "agents"

        self.assertEqual(naming_errors([registry.get_app_config("agents")]), [("config.E001", "Step")])

    @isolate_apps("apps.agents", kwarg_name="registry")
    def test_camel_case_constraint_and_index_names_fail(self, registry):
        class Step(models.Model):
            number = models.IntegerField()

            class Meta:
                app_label = "agents"
                indexes = [models.Index(fields=["number"], name="agents_Step_number")]
                constraints = [models.CheckConstraint(condition=models.Q(number__gte=0), name="agents_step_Positive")]

        self.assertEqual(
            naming_errors([registry.get_app_config("agents")]), [("config.E001", "Step"), ("config.E001", "Step")]
        )
