"""A scripted console for the interactive console tests."""

from collections.abc import Callable

Answer = str | BaseException | Callable[[], str]


class Console:
    """Scripted answers (an exception is raised, a callable is called) and output."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.lines: list[str] = []

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer() if callable(answer) else answer

    def say(self, text: str) -> None:
        self.lines.append(text)

    @property
    def output(self) -> str:
        return "\n".join(self.lines)
