"""Replacement for builtins.input returning queued answers."""


class MockedInput:
    __inputs = []

    def __init__(self, inputs: list):
        self.__inputs = inputs

    def mock_inputs(self, *args, **kwargs):
        return self.__inputs.pop(0) if self.__inputs else "-"
