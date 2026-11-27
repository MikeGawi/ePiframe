"""Console setup of the Google Drive source (``epiframe setup-drive``).

Works over SSH: shows the steps with links, takes the service account key (a
file path or the pasted JSON), the photo folders, checks the access until it
works and saves the settings.
"""

import json
from collections.abc import Callable

from epiframe.config.base import ConfigBase
from epiframe.config.paths import caller_path
from epiframe.core.console import Ask, Say, ask_yes
from epiframe.sources.drive import Drive, DriveClient, folder_ids
from epiframe.sources.drive_setup import (
    SHARE_STEP,
    STEPS,
    KeyFileError,
    ServiceAccountKey,
    SetupReport,
    Step,
    check,
    explain,
    read_key,
    save_config,
    save_key,
)

Connect = Callable[[str], Drive]

# lines read when the JSON key is pasted (a key file has about 15)
MAX_PASTED_LINES = 200


class ConsoleSetup:
    """The setup dialogue; ``ask``/``say`` are ``input``/``print`` by default."""

    def __init__(
        self,
        config: ConfigBase,
        ask: Ask = input,
        say: Say = print,
        connect: Connect = DriveClient.from_key_file,
    ) -> None:
        self.config = config
        self.ask = ask
        self.say = say
        self.connect = connect
        self.key_file = config.get("drive_key_file")

    def run(self) -> int:
        """Run the setup; return the exit code (0 = settings saved)."""
        try:
            self.say("ePiframe - Google Drive source setup (Ctrl+C to stop)")
            self._guide()
            key = self._key()
            folders = self._folders(key)
            if not self._verify(key, folders):
                self.say("Settings not saved.")
                return 1
        except (EOFError, KeyboardInterrupt):
            self.say("\nSetup stopped, settings not saved.")
            return 1
        save_config(self.config, self.key_file, folders)
        self.say(
            f"Saved to {self.config.path}: Google Drive source enabled. Test it with"
            " ./ePiframe.py test"
        )
        return 0

    # ---------------------------------------------------------------- dialogue

    def _yes(self, question: str, default: bool) -> bool:
        return ask_yes(self.ask, question, default)

    def _show(self, number: int, step: Step, **values: str) -> None:
        self.say(f"\n{number}. {step.title}\n   {step.text.format(**values)}")
        if step.link:
            self.say(f"   {step.link}")

    def _guide(self) -> None:
        if not self._yes("Show the steps to create a service account key?", True):
            return
        for number, step in enumerate(STEPS, 1):
            self._show(number, step)
            self.ask("   Press Enter when done...")

    # --------------------------------------------------------------------- key

    def _key(self) -> ServiceAccountKey:
        existing = self._existing_key()
        if existing and self._yes(
            f"Use the key in {self.key_file} ({existing.account})?", True
        ):
            return existing
        while True:
            answer = self.ask(
                "\nPath of the downloaded JSON key file (or paste its content): "
            )
            try:
                key = save_key(self._key_content(answer), self.key_file)
            except (OSError, KeyFileError) as error:
                self.say(f"Error: {error}")
                continue
            self.say(f"Key of {key.account} saved to {self.key_file}")
            return key

    def _existing_key(self) -> ServiceAccountKey | None:
        try:
            return read_key(self.key_file)
        except (OSError, KeyFileError):
            return None

    def _key_content(self, answer: str) -> str:
        answer = answer.strip()
        if not answer.startswith("{"):
            return caller_path(answer).read_text()
        lines = [answer]
        while not self._complete(lines) and len(lines) < MAX_PASTED_LINES:
            lines.append(self.ask(""))
        return "\n".join(lines)

    @staticmethod
    def _complete(lines: list[str]) -> bool:
        try:
            json.loads("\n".join(lines))
        except ValueError:
            return False
        return True

    # ----------------------------------------------------------------- folders

    def _folders(self, key: ServiceAccountKey) -> list[str]:
        self._show(len(STEPS) + 1, SHARE_STEP, account=key.account)
        current = self.config.get("drive_folders")
        suffix = f" [{current}]" if current else ""
        while True:
            answer = self.ask(f"\nFolder links or IDs, comma separated{suffix}: ")
            try:
                return folder_ids(answer.strip() or current)
            except ValueError as error:
                self.say(f"Error: {error}")

    # ------------------------------------------------------------------- check

    def _verify(self, key: ServiceAccountKey, folders: list[str]) -> bool:
        while True:
            self.say("\nChecking the access...")
            report = self._check(key, folders)
            self._print(report)
            if report.ok:
                return True
            if not self._yes("Check again (e.g. after sharing a folder)?", True):
                return self._yes("Save the settings anyway?", False)

    def _check(self, key: ServiceAccountKey, folders: list[str]) -> SetupReport:
        try:
            drive = self.connect(self.key_file)
        except Exception as error:  # e.g. a broken private key
            return SetupReport(key.account, problem=explain(error, key))
        return check(drive, folders, key)

    def _print(self, report: SetupReport) -> None:
        self.say(f"Service account: {report.account}")
        for item in report.folders:
            name = f"{item.name} ({item.folder})" if item.name else item.folder
            if item.problem:
                self.say(f"  [!!] {name}: {item.problem}")
            else:
                self.say(
                    f"  [OK] {name}: {item.photos} photos and {item.subfolders}"
                    " subfolders directly in it"
                )
        if report.problem:
            self.say(f"  [!!] {report.problem}")
