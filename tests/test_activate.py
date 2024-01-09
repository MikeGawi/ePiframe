import json
import os
import time
import urllib.parse
from threading import Timer
from unittest.mock import patch

import flask
import pytest
from flask import Flask, render_template
from google_auth_oauthlib import flow
from googleapiclient import discovery
import activate
from tests.helpers.capturing import Capturing
from tests.helpers.credentials import Flow
from tests.helpers.helpers import remove_file, not_raises
from tests.helpers.oauth_service import OauthService
from tests.helpers.request import MockedRequest, MockedStream

mocked_code = (
    "http://localhost:1/?state=VOT2v2x5aq1chctSbL1qhjDGq66WHz&code=ABCDEFGHIJKLMNOPQRSTVXYZ0123456789&scope"
    "=https://www.googleapis.com/auth/photoslibrary.readonly"
)

cred_file = "test_creds.json"
token_file = "test_token.pickle"


def test_text_pages():
    pages = []
    for i in [
        key
        for key in [key_value for key_value in activate.__PAGES.keys()][:-1]
        if activate.__PAGES[key][activate.__TYPE] == activate.__TEXT_TYPE
    ]:
        pages.append("* " + activate.strip_html(activate.__PAGES[i]["text"]))

    assert pages == [
        "* This tool will guide You through token and credentials activation of Google Photos API support for "
        "ePiframe. You can always start it by running ./install.sh --activate command in the main path",
        "* Create new or use an existing Google account for ePiframe and log in. Go to Google Cloud Console. Click on "
        "Select a project.",
        "* Click on NEW PROJECT",
        "* Put ePiframe in the Project name field and click [CREATE]. You have created ePiframe project!",
        "* Now select ePiframe project by clicking on it",
        "* Click APIs & Services in the panel on the left hand side and pick Library",
        "* Search for Photos and then click Photos Library API",
        "* Click on [ENABLE]. Now You have given Your ePiframe project support to Google Photos API",
        "* Go to Credentials in the panel on the left hand side under APIs & Services and click [CONFIGURE CONSENT "
        "SCREEN]",
        "* Choose External and click [CREATE]",
        "* Put ePiframe in the App name field, type Google email used for Your ePiframe where necessary, scroll down "
        "and click on [SAVE AND CONTINUE] three times until You get to Summary. Click [BACK TO DASHBOARD]. Your "
        "application consent screen is ready!",
        "* Click on [PUBLISH APP] in Oauth consent screen section under APIs & Services to publish Your application",
        "* Click on +CREATE CREDENTIALS and choose OAuth client ID",
        "* Pick Desktop app as Application type and put ePiframe\tin the Name field. Click [CREATE]",
        "* You have created OAuth client for Your ePiframe! Click on DOWNLOAD JSON to download JSON formatted "
        "credentials file",
        "* You can always get it from the Credentials dashboard by clicking download icon in Actions column of Your "
        "desired Client ID",
    ]


def test_end_pages():
    assert (
        activate.strip_html(activate.__PAGES[len(activate.__PAGES)]["text"])
        == "All done! You have successfully activated Google Photos credentials and token for Your ePiframe! Test "
        "Your frame and have fun!"
    )


def test_get_page():
    app = get_app()
    with app.app_context(), app.test_request_context():
        response = activate.steps()
    assert activate.__PAGES[1]["text"] in response


def test_get_page_min():
    app = get_app()
    with app.app_context(), app.test_request_context():
        response = activate.steps("-10")
    assert activate.__PAGES[1]["text"] in response


def test_get_page_max():
    app = get_app()
    app.add_url_rule("/stop", view_func=stop, methods=["POST"])
    with app.app_context(), app.test_request_context():
        response = activate.steps("10000")
    assert activate.__PAGES[len(activate.__PAGES.keys())]["text"] in response


def test_stop():
    os._exit = mocked_exit
    with Capturing() as output:
        returned_value = activate.stop()
        assert not output
        time.sleep(3)

    assert output == ["Exit command with key=0"]
    assert returned_value == "Tool shutting down...<br>You can close this page."


def test_get_auth_url():
    flow.InstalledAppFlow.from_client_secrets_file = Flow.from_client_secrets_file
    activate.__CRED_FILE = cred_file

    with open(cred_file, "w") as credentials_file:
        json.dump(
            mocked_credentials,
            credentials_file,
        )

    url = activate.get_auth_url()
    assert url
    decoded = urllib.parse.parse_qs(url)
    assert "https://accounts.google.com/o/oauth2/auth?response_type" in decoded
    assert decoded["client_id"] == ["client_id.apps.googleusercontent.com"]
    assert decoded["redirect_uri"] == ["http://localhost:1/"]
    assert decoded["scope"] == [
        "https://www.googleapis.com/auth/photoslibrary.readonly"
    ]
    assert decoded["access_type"] == ["offline"]
    assert decoded["include_granted_scopes"] == ["true"]


def test_save_creds():
    activate.__CRED_FILE = cred_file
    activate.get_auth_url = stop
    activate.save_creds(json.dumps(mocked_credentials))

    assert os.path.exists(cred_file)
    assert os.path.exists(cred_file + ".back")
    assert os.stat(cred_file)
    assert oct(os.stat(cred_file).st_mode & 0o777) == "0o666"

    remove_file(cred_file)
    remove_file(cred_file + ".back")


def test_save_creds_empty():
    activate.get_auth_url = stop
    with pytest.raises(Exception) as exception:
        activate.save_creds("")
    assert exception
    assert str(exception.value) == "Empty value"


def test_save_creds_wrong_client_id():
    activate.get_auth_url = stop
    with pytest.raises(Exception) as exception:
        activate.save_creds(
            json.dumps(
                {
                    "installed": {
                        "project_id": "epiframe",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_secret": "secret",
                        "redirect_uris": [
                            "urn:ietf:wg:oauth:2.0:oob",
                            "http://localhost",
                        ],
                    }
                }
            )
        )
    assert exception
    assert str(exception.value) == "Wrong file content"


def test_save_creds_wrong_client_secret():
    activate.get_auth_url = stop
    with pytest.raises(Exception) as exception:
        activate.save_creds(
            json.dumps(
                {
                    "installed": {
                        "client_id": "client_id.apps.googleusercontent.com",
                        "project_id": "epiframe",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": [
                            "urn:ietf:wg:oauth:2.0:oob",
                            "http://localhost",
                        ],
                    }
                }
            )
        )
    assert exception
    assert str(exception.value) == "Wrong file content"


def test_save_creds_no_installed():
    activate.get_auth_url = stop
    with pytest.raises(Exception) as exception:
        activate.save_creds(
            json.dumps(
                {
                    "not_installed": {
                        "client_id": "client_id.apps.googleusercontent.com",
                        "project_id": "epiframe",
                        "client_secret": "secret",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": [
                            "urn:ietf:wg:oauth:2.0:oob",
                            "http://localhost",
                        ],
                    }
                }
            )
        )
    assert exception
    assert str(exception.value) == "Wrong file content"


def test_gen_token_wrong():
    with pytest.raises(Exception) as exception:
        activate.gen_token(
            "http://localhost:1/?state=VOT2v2x5aq1chctSbL1qhjDGq66WHz&no_code=code&scope=https://www.googleapis.com"
            "/auth/photoslibrary.readonly"
        )

    assert exception


def test_gen_token_empty_code():
    with pytest.raises(Exception) as exception:
        activate.gen_token(
            "http://localhost:1/?state=VOT2v2x5aq1chctSbL1qhjDGq66WHz&code=&scope=https://www.googleapis.com"
            "/auth/photoslibrary.readonly"
        )

    assert exception


def test_get_token():
    remove_file(token_file)
    remove_file(token_file + ".back")

    activate.__TOKEN_FILE = token_file
    discovery.build = OauthService.build
    activate.flow = Flow
    with not_raises(Exception), Capturing() as output:
        activate.gen_token(mocked_code)

    assert output == [
        "Flow_fetch_token",
        "Build: name='photoslibrary' version='v1' credentials='Flow_credentials' static_discovery=False",
    ]

    assert os.path.exists(token_file)
    assert os.stat(token_file)
    assert not os.path.exists(token_file + ".back")
    assert oct(os.stat(token_file).st_mode & 0o777) == "0o666"


def test_get_token_back():
    activate.__TOKEN_FILE = token_file
    discovery.build = OauthService.build
    activate.flow = Flow
    with not_raises(Exception), Capturing() as output:
        activate.gen_token(
            "http://localhost:1/?state=VOT2v2x5aq1chctSbL1qhjDGq66WHz&code=ABCDEFGHIJKLMNOPQRSTVXYZ0123456789&scope"
            "=https://www.googleapis.com/auth/photoslibrary.readonly"
        )

    assert output == [
        "Flow_fetch_token",
        "Build: name='photoslibrary' version='v1' credentials='Flow_credentials' static_discovery=False",
    ]

    assert os.path.exists(token_file)
    assert os.path.exists(token_file + ".back")
    assert os.stat(token_file)
    assert oct(os.stat(token_file).st_mode & 0o777) == "0o666"

    remove_file(token_file)
    remove_file(token_file + ".back")


def test_get_generate_fail():
    app = get_app()
    activate.__TOKEN_FILE = token_file
    discovery.build = OauthService.build
    activate.flow = Flow
    MockedRequest.form = {"no_code": "not a code"}

    with app.app_context(), app.test_request_context(), not_raises(
        Exception
    ), Capturing() as output, patch.object(flask, "flash", mocked_flash), patch.object(
        flask, "redirect", mocked_redirect
    ), patch.object(
        flask, "request", MockedRequest
    ):
        response = activate.generate()

    assert output == [
        "Flash msg='Error: expected string or bytes-like object'",
        "Flash msg='Error: The URL should be an exact copy of the generated URL and should not be empty!'",
        "Flash msg='If something is still wrong then try to re-upload the credentials and try again'",
    ]

    assert not os.path.exists(token_file)
    assert not os.path.exists(token_file + ".back")
    assert response == "Redirect page='19'"


def test_get_generate_ok():
    app = get_app()
    activate.__TOKEN_FILE = token_file
    discovery.build = OauthService.build
    activate.flow = Flow
    MockedRequest.form = {"code": mocked_code}

    with app.app_context(), app.test_request_context(), not_raises(
        Exception
    ), Capturing() as output, patch.object(flask, "flash", mocked_flash), patch.object(
        flask, "redirect", mocked_redirect
    ), patch.object(
        flask, "request", MockedRequest
    ):
        response = activate.generate()

    assert output == [
        "Flow_fetch_token",
        "Build: name='photoslibrary' version='v1' credentials='Flow_credentials' static_discovery=False",
    ]

    assert os.path.exists(token_file)
    assert not os.path.exists(token_file + ".back")
    assert os.stat(token_file)
    assert oct(os.stat(token_file).st_mode & 0o777) == "0o666"

    remove_file(token_file)
    assert response == "Redirect page='19'"


def test_upload_fail():
    app = get_app()
    MockedRequest.form = {"no_file": "not a file"}

    with app.app_context(), app.test_request_context(), not_raises(
        Exception
    ), Capturing() as output, patch.object(flask, "flash", mocked_flash), patch.object(
        flask, "redirect", mocked_redirect
    ), patch.object(
        flask, "request", MockedRequest
    ):
        response = activate.upload()

    assert output == [
        "Flash msg='Error: wrong file uploaded! Make sure You are uploading JSON credentials file'"
    ]
    assert response == "Redirect page='19'"


def test_upload_ok():
    app = get_app()
    MockedRequest.files = {"file": MockedStream()}
    activate.save_creds = mocked_save

    with app.app_context(), app.test_request_context(), not_raises(
        Exception
    ), Capturing() as output, patch.object(flask, "flash", mocked_flash), patch.object(
        flask, "redirect", mocked_redirect
    ), patch.object(
        flask, "request", MockedRequest
    ):
        response = activate.upload()

    assert output == ["Save msg='1234567890'"]
    assert response == "Redirect page='20'"


def stop():
    return "Tool shutting down...<br>You can close this page."


def mocked_flash(msg: str):
    print(f"Flash {msg=}")


def mocked_save(msg: str):
    print(f"Save {msg=}")


def mocked_exit(key: int):
    print(f"Exit command with {key=}")


def mocked_redirect(page: str):
    return f"Redirect {page=}"


def get_app():
    activate.render_template = render_template
    activate.Timer = Timer
    template_dir = "../templates"
    app = Flask(__name__, template_folder=template_dir)
    return app


mocked_credentials = {
    "installed": {
        "client_id": "client_id.apps.googleusercontent.com",
        "project_id": "epiframe",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "secret",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}
