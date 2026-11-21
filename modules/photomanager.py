import pandas as pd


# photo list (DataFrame) column labels, also passed to plugins
PHOTOS_ID_HEADER = "id"
PHOTOS_CREATIONTIME_HEADER = "creationTime"
PHOTOS_SOURCE_LABEL = "source"
LOCAL_SOURCE = "Local"


class PhotoManager:
    @staticmethod
    def get_num_of_photos(photos) -> int:
        return len(photos.axes[0])

    @staticmethod
    def reset_index(photos):
        return photos.reset_index(drop=True)

    @staticmethod
    def get_photos_attribute(photos, attribute: str):
        return photos[attribute]

    @staticmethod
    def get_photo_attribute(photo, attribute: str):
        return photo[attribute]

    @staticmethod
    def get_photo_by_index(photos, index: int):
        return photos.iloc[index]

    def append_photos(self, target_dataframe, source_dataframe):
        if target_dataframe is None:
            target_dataframe = pd.DataFrame()
        merged = pd.concat([target_dataframe, source_dataframe])
        return self.reset_index(merged)
