import pandas as pd
from misc.constants import Constants


class PhotoManager:

    __album = pd.DataFrame()
    __photos = pd.DataFrame()

    def set_photos(
        self,
        album,
        media_metadata_header: str,
        photo_header: str,
        mime_header: str,
        mime_type: str,
        source_label: str,
        source: str,
    ):
        self.__album = album

        # get media items
        dataframe_meta = album.get_data()[media_metadata_header].apply(pd.Series)

        # build all items table
        all_elements = pd.concat(
            [
                album.get_data().drop(media_metadata_header, axis=1),
                dataframe_meta.drop(photo_header, axis=1),
                dataframe_meta[photo_header].apply(pd.Series),
            ],
            axis=1,
        )

        # get only photos
        isimage = all_elements[mime_header].str.startswith(mime_type)
        self.__photos = all_elements[isimage].reset_index(drop=True)

        # set source
        self.__photos[source_label] = source

        return self.__photos

    def get_album(self):
        return self.__album

    def get_photos(self):
        return self.__photos

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
        merged = target_dataframe.append([source_dataframe])
        return self.reset_index(merged)

    @staticmethod
    def get_refresh_rates():
        return [Constants.REFRESH_ALWAYS, Constants.REFRESH_ONCE]
