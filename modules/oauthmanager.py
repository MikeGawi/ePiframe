import os
import pickle
from typing import Optional, Any
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class OAuthManager:
    __service: Optional[Any]
    __credentials: Any = None
    __items = []

    def manage_pickle(self, pickle_file: str, credentials_file: str, scopes: str):
        self.__credentials = None

        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(pickle_file):
            with open(pickle_file, "rb") as token:
                self.__credentials = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not self.__credentials or not self.__credentials.valid:
            self.__refresh_credentials(credentials_file, pickle_file, scopes)
        os.chmod(pickle_file, 0o0666)

    def __refresh_credentials(
        self, credentials_file: str, pickle_file: str, scopes: str
    ):
        if (
            self.__credentials
            and self.__credentials.expired
            and self.__credentials.refresh_token
        ):
            self.__credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            self.__credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        self.__dump_pickle(pickle_file)

    def __dump_pickle(self, pickle_file: str):
        with open(pickle_file, "wb") as token:
            pickle.dump(self.__credentials, token)

    def build_service(self, name: str, version: str):
        self.__service = build(
            name, version, credentials=self.__credentials, static_discovery=False
        )

    def get(
        self,
        page_size: int,
        exclude: bool,
        next_page_token_header: str,
        response_for: str,
    ):
        items = []
        next_page_token = None

        while next_page_token != "":
            results = (
                self.__service.albums()
                .list(
                    pageSize=page_size,
                    pageToken=next_page_token,
                    excludeNonAppCreatedData=exclude,
                )
                .execute()
            )
            items += results.get(response_for, [])
            next_page_token = results.get(next_page_token_header, "")

        self.__items = items

    @staticmethod
    def remove_token(pickle_file: str):
        if os.path.exists(pickle_file):
            os.remove(pickle_file)

    def get_items(
        self,
        header: str,
        identifier: str,
        item_header: str,
        pagesize: int,
        page_size_header: str,
        page_token_header: str,
        next_page_token_response_header: str,
    ) -> list:
        items = []
        next_page_token = None

        while next_page_token != "":
            results = (
                self.__service.mediaItems()
                .search(
                    body={
                        page_size_header: pagesize,
                        page_token_header: next_page_token,
                        header: identifier,
                    }
                )
                .execute()
            )
            items += results.get(item_header, [])
            next_page_token = results.get(next_page_token_response_header, "")

        return items

    def get_service(self):
        return self.__service

    def get_response(self) -> list:
        return self.__items

    def get_creds(self):
        return self.__credentials
