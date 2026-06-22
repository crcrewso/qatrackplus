from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Export selected app data into fixture folders for preloading defaults."

    excluded_apps = {"admin", "auth", "contenttypes", "sessions"}
    included_apps = {"qa", "units", "service_log"}

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=Path(settings.PROJECT_ROOT).parent / "fixtures" / "dev",
            type=Path,
            help="Directory to write fixture folders into.",
        )
        parser.add_argument(
            "--all-apps",
            action="store_true",
            default=False,
            help="Export all apps except those in excluded_apps.",
        )
        parser.add_argument(
            "--add-date",
            action="store_true",
            default=False,
            help="Append execution date/time to the output directory.",
        )
        parser.add_argument(
            "--apps",
            nargs="*",
            default=None,
            help="Optional list of app labels to export. If omitted, uses included_apps unless --all-apps is set.",
        )

    def handle(self, *args, **options):
        base_dir = options["output_dir"]
        if options["add_date"]:
            base_dir = base_dir / timezone.now().strftime("%Y-%m-%d-%H-%M-%S")
        all_apps = options["all_apps"]
        selected_apps = None if all_apps else set(options["apps"] or self.included_apps)
        base_dir.mkdir(parents=True, exist_ok=True)

        for model in apps.get_models():
            app_label = model._meta.app_label
            model_name = model.__name__.lower()

            if app_label in self.excluded_apps:
                continue
            if selected_apps is not None and app_label not in selected_apps:
                continue
            if model._meta.proxy:
                continue
            if "django" in model.__module__.lower():
                continue

            app_folder = base_dir / app_label
            app_folder.mkdir(parents=True, exist_ok=True)
            file_path = app_folder / f"{model_name}.json"

            self.stdout.write(f"Exporting {app_label}.{model_name}...")

            with file_path.open("w", encoding="utf-8") as fixture_file:
                call_command(
                    "dumpdata",
                    f"{app_label}.{model_name}",
                    indent=4,
                    stdout=fixture_file,
                    use_natural_foreign_keys=True,
                    use_natural_primary_keys=True,
                )

        self.stdout.write(self.style.SUCCESS("Successfully exported all models!"))
