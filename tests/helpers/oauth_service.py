from misc.constants import Constants


class OauthService:
    data = None

    @classmethod
    def build(cls, name, version, credentials, static_discovery):
        print(f"Build: {name=} {version=} {credentials=} {static_discovery=}")
        return cls

    @classmethod
    def albums(cls):
        print("Albums")
        return cls

    @classmethod
    def mediaItems(cls):
        print("MediaItems")
        return cls

    @classmethod
    def set_data(cls, data):
        cls.data = data

    @classmethod
    def list(cls, pageSize, pageToken, excludeNonAppCreatedData):
        print(f"List: {pageSize=} {pageToken=} {excludeNonAppCreatedData=}")
        return cls

    @classmethod
    def search(cls, body):
        print(f"Search: {body=}")
        return cls

    @classmethod
    def get(cls, mediaItemId):
        print(f"Get: {mediaItemId=}")
        return cls

    @classmethod
    def execute(cls):
        if cls.data:
            data = cls.data
            cls.data = None
            return data
        else:
            return {
                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER: "",
            }
