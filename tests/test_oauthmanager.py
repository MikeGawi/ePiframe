import os.path
from unittest.mock import patch
from google_auth_oauthlib import flow
from googleapiclient import discovery
from misc.constants import Constants
from tests.helpers.capturing import Capturing
from tests.helpers.credentials import Flow
from tests.helpers.helpers import not_raises, remove_file
from tests.helpers.oauth_service import OauthService

pickle_file = "pickle.test"


def test_build_service():
    with Capturing() as output:
        manager = get_manager()
    assert output == [
        "Build: name='service_name' version='version_name' credentials=None static_discovery=False"
    ]
    assert (
        str(manager.get_service())
        == "<class 'tests.helpers.oauth_service.OauthService'>"
    )


def test_get_albums():
    manager = get_manager()
    OauthService.set_data(
        {
            Constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE: {"albums_data": "data"},
            Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER: "token",
        }
    )
    with Capturing() as output:
        with not_raises(Exception):
            manager.get(
                Constants.GOOGLE_PHOTOS_PAGESIZE,
                bool(Constants.GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA),
                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
                Constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE,
            )
    assert output == [
        "Albums",
        "List: pageSize=50 pageToken=None excludeNonAppCreatedData=False",
        "Albums",
        "List: pageSize=50 pageToken='token' excludeNonAppCreatedData=False",
    ]

    assert manager.get_response() == ["albums_data"]


def test_get_items():
    manager = get_manager()
    OauthService.set_data(
        {
            Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER: {
                "media_items_data": "data"
            },
            Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER: "token",
        }
    )
    with Capturing() as output:
        with not_raises(Exception):
            items = manager.get_items(
                Constants.GOOGLE_PHOTOS_ALBUMS_ALBUMID_HEADER,
                "album_id",
                Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER,
                Constants.GOOGLE_PHOTOS_PAGESIZE,
                Constants.GOOGLE_PHOTOS_PAGESIZE_HEADER,
                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_HEADER,
                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
            )
    assert output == [
        "MediaItems",
        "Search: body={'pageSize': 50, 'pageToken': None, 'albumId': 'album_id'}",
        "MediaItems",
        "Search: body={'pageSize': 50, 'pageToken': 'token', 'albumId': 'album_id'}",
    ]

    assert items == ["media_items_data"]


def test_create_credentials():
    remove_file(pickle_file)
    manager = get_manager_flow()
    with Capturing() as output:
        manager.manage_pickle(pickle_file, "credentials_file", Constants.SCOPES)
        assert (
            str(type(manager.get_creds()))
            == "<class 'tests.helpers.credentials.Credentials'>"
        )
        assert os.path.exists(pickle_file)
    assert output == [
        "Flow_from_client_secrets_file client_secrets_file='credentials_file' scopes=["
        "'https://www.googleapis.com/auth/photoslibrary.readonly']",
        "Flow_run_local_server",
    ]


def test_create_credentials_load():
    manager = get_manager_flow()
    with Capturing() as output:
        manager.manage_pickle(pickle_file, "credentials_file", Constants.SCOPES)
        assert (
            str(type(manager.get_creds()))
            == "<class 'tests.helpers.credentials.Credentials'>"
        )
    assert output == ["Credentials_refresh"]


def test_remove_pickle():
    manager = get_manager_flow()
    manager.remove_token(pickle_file)

    assert not os.path.exists(pickle_file)


def get_manager_flow():
    flow.InstalledAppFlow.from_client_secrets_file = Flow.from_client_secrets_file
    flow.InstalledAppFlow.run_local_server = Flow.run_local_server
    from modules.oauthmanager import OAuthManager

    return OAuthManager()


def get_manager():
    discovery.build = OauthService.build
    from modules.oauthmanager import OAuthManager

    manager = OAuthManager()
    manager.build_service("service_name", "version_name")
    return manager
