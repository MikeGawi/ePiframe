from typing import List
from misc.constants import Constants
import sqlite3


class DatabaseManager:
    __SELECT_DB = (
        "SELECT "
        + Constants.DB_NAME_COL
        + " FROM "
        + Constants.DB_SQLITE_MASTER_TAB
        + " WHERE type='table' AND "
        + Constants.DB_NAME_COL
        + "='{}'"
    )
    __BACK_TAG = "_back"

    def __init__(self):
        self.__dbconnection = sqlite3.connect(
            Constants.USERS_DB_FILE, check_same_thread=False
        )
        cur = self.__dbconnection.cursor()

        dbs = {
            Constants.USERS_TABLE_NAME: "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, username text, hash text, "
            "api text)".format(Constants.USERS_TABLE_NAME),
            Constants.SALTS_TABLE_NAME: "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, userid INTEGER, salt text, "
            "FOREIGN KEY(userid) REFERENCES {}(id))".format(
                Constants.SALTS_TABLE_NAME, Constants.USERS_TABLE_NAME
            ),
        }

        for db in dbs.keys():
            cur.execute(self.__SELECT_DB.format(db))
            if not cur.fetchone():
                cur.execute(dbs[db])
                self.__dbconnection.commit()
            else:
                # simple backward compatibility
                if self.get_create(db)[0][0] != dbs[db]:
                    fields = ",".join([x[1] for x in self.get_schema(db)])
                    cur = self.__dbconnection.cursor()
                    cur.execute(
                        "ALTER TABLE {} RENAME TO {}".format(db, db + self.__BACK_TAG)
                    )
                    cur.execute(dbs[db])
                    cur.execute(
                        "INSERT INTO {} ({}) SELECT {} FROM {}".format(
                            db, fields, fields, db + self.__BACK_TAG
                        )
                    )
                    cur.execute("DROP TABLE {}".format(db + self.__BACK_TAG))
                    self.__dbconnection.commit()

    def __commit(self, query: str, fields: str = ""):
        cursor = self.__dbconnection.cursor()
        if fields:
            cursor.executemany(query, fields)
        else:
            cursor.execute(query, "")
        self.__dbconnection.commit()

    def __get(self, query: str, fields: str = "") -> list:
        cursor = self.__dbconnection.cursor()
        cursor.execute(query, fields)
        self.__dbconnection.commit()
        return cursor.fetchall()

    @staticmethod
    def __change_many(fields):
        return ",".join(fields) if isinstance(fields, list) else fields

    @staticmethod
    def __to_strings(fields) -> List[str]:
        values = []
        for iterator, enumerator in enumerate(fields):
            values.append(
                "'{}'".format(enumerator)
                if isinstance(enumerator, str) and enumerator != Constants.DB_NULL
                else enumerator
            )
        return values

    def select(self, fields, _from, where: str = None) -> list:
        return self.__get(
            "SELECT {} FROM {}".format(
                self.__change_many(fields), self.__change_many(_from)
            )
            + (" WHERE {}".format(where) if where else "")
        )

    def update(self, table: str, field: str, value: str, where: str):
        self.__commit(
            "UPDATE {} SET {} = {} WHERE {}".format(table, field, value, where)
        )

    def delete(self, table: str, where: str):
        self.__commit("DELETE FROM {} WHERE {}".format(table, where))

    def insert(self, to, values):
        self.__commit(
            "INSERT INTO {} VALUES ({})".format(
                self.__change_many(to), self.__change_many(self.__to_strings(values))
            )
        )

    def get_schema(self, _for: str) -> list:
        return self.__get('PRAGMA table_info("{}")'.format(_for))

    def get_create(self, _for: str) -> list:
        return self.select(
            Constants.DB_SQL_COL,
            Constants.DB_SQLITE_MASTER_TAB,
            '{} IS "{}"'.format(Constants.DB_NAME_COL, _for),
        )
