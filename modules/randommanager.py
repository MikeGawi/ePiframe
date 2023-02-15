import os
import pandas as pd


class RandomManager:

    __COLUMN_NAME = "random"

    def __init__(self, path: str, photos, id_header: str):
        self.__path = path
        self.__data = photos.copy().get([id_header])
        self.__data[self.__COLUMN_NAME] = 0
        self.__id_header = id_header

        old_data = pd.DataFrame()

        try:
            if os.path.exists(path):
                old_data = pd.read_csv(self.__path)
        except Exception:
            pass

        if not old_data.empty:
            self.__data.loc[
                self.__data[id_header].isin(old_data[id_header]), [self.__COLUMN_NAME]
            ] = old_data[self.__COLUMN_NAME]

        self.__data[self.__COLUMN_NAME].fillna(0, inplace=True)

    def __save(self):
        self.__data.to_csv(self.__path)

    def get_random(self, last_id: str, no_save=False) -> int:
        randoms = self.__data.copy().loc[(self.__data[self.__COLUMN_NAME] != 1)]

        if randoms.empty:
            self.__data[self.__COLUMN_NAME] = 0
            randoms = self.__data

        # prevent last photo showing again after full cycle
        if last_id and len(randoms.axes[0]) > 1:
            index_names = randoms[(randoms[self.__id_header] == last_id)].index
            randoms.drop(index_names, inplace=True, errors="ignore")

        sample = randoms.sample()
        index = sample.index.values[0]
        if f"id_{index+1}" == last_id:
            print ("lolo")
        self.__data.at[index, self.__COLUMN_NAME] = 1


        if not no_save:
            self.__save()
        return index
