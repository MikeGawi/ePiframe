class MockedChat:
    def __init__(self, chat_id):
        self.id = chat_id


class MockedPhotoPath:
    def __init__(self, photo_path):
        self.file_path = photo_path


class MockedPhotoId:
    def __init__(self, photo_info):
        self.file_id = photo_info


class MockedMessage:
    photo = []

    def __init__(self, content_type, text, chat, photo_id=None):
        self.content_type = content_type
        self.text = text
        self.chat = chat
        if photo_id:
            self.photo.append(photo_id)
