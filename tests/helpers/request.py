class MockedRequest:
    method = "POST"
    form = {}
    files = {}


class MockedStream:

    file = b"1234567890"

    def read(self):
        return self.file
