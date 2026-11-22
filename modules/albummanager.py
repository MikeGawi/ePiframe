import pandas as pd


class AlbumManager:

    __album_data = pd.DataFrame()
    __album_names = pd.DataFrame()

    def __init__(self, albums, names: str, header: str):
        dataframe_albums = pd.DataFrame(albums)

        # search for albums
        if names:
            album_names = names.split(",")

            for name in set(album_names):
                if name.strip():
                    album = dataframe_albums[dataframe_albums[header] == name.strip()]
                    if not album.empty:
                        self.__album_names = self.__album_names.append(album)
        else:
            self.__album_names = dataframe_albums

    def get_albums(self):
        return self.__album_names

    def append_data(self, data):
        pandas_data = pd.DataFrame(data)

        if not pandas_data.empty:
            self.__album_data = self.__album_data.append(pandas_data)

    def get_data(self):
        return self.__album_data
