#!/usr/bin/env python3
import re
import json
import os
import shutil
import pickle
from threading import Timer

import google_auth_oauthlib.flow
import googleapiclient.discovery

__TEXT_TYPE = "text"
__UPLOAD_TYPE = "upload"
__CODE_TYPE = "code"
__PAGE = "activation/page.html"

__TYPE = "type"
__PIC = "pic"
__TEXT = "text"
__TITLE = "title"

__CRED_FILE = "credentials.json"
__TOKEN_FILE = "token.pickle"

IP = "0.0.0.0"
PORT = "80"

__PAGES = {
    1: {
        __TYPE: __TEXT_TYPE,
        __PIC: None,
        __TITLE: "Welcome",
        __TEXT: "This tool will guide You through token and credentials activation of Google Photos API support for "
        "<b>ePiframe</b>. <br><br>You can always start it by running <br><code>./install.sh --activate</code> "
        "<br>command in the main path",
    },
    2: {
        __TYPE: __TEXT_TYPE,
        __PIC: "1.png",
        __TITLE: "Google Cloud Console",
        __TEXT: "<ul><li>Create new or use an existing Google account for <b>ePiframe</b> and log in. </li><li>Go to "
        '<a href="https://console.cloud.google.com/" target="_blank">Google Cloud Console. </a></li><li>Click '
        "on <i>Select a project</i>.</li></ul>",
    },
    3: {
        __TYPE: __TEXT_TYPE,
        __PIC: "2.png",
        __TITLE: "New project",
        __TEXT: "Click on <i>NEW PROJECT</i>",
    },
    4: {
        __TYPE: __TEXT_TYPE,
        __PIC: "3.png",
        __TITLE: "Configure new project",
        __TEXT: "Put <i>ePiframe</i> in the <i>Project name</i> field and click <i>[CREATE]</i>. <br>You have created "
        "<b>ePiframe</b> project!",
    },
    5: {
        __TYPE: __TEXT_TYPE,
        __PIC: "4.png",
        __TITLE: "Select project",
        __TEXT: "Now select <i>ePiframe</i> project by clicking on it",
    },
    6: {
        __TYPE: __TEXT_TYPE,
        __PIC: "5.png",
        __TITLE: "Libraries",
        __TEXT: "Click <i>APIs & Services</i> in the panel on the left hand side and pick <i>Library</i>",
    },
    7: {
        __TYPE: __TEXT_TYPE,
        __PIC: "6.png",
        __TITLE: "Search for API",
        __TEXT: "Search for <i>Photos</i> and then click <i>Photos Library API</i>",
    },
    8: {
        __TYPE: __TEXT_TYPE,
        __PIC: "7.png",
        __TITLE: "Enable API",
        __TEXT: "Click on <i>[ENABLE]</i>. <br>Now You have given Your <b>ePiframe</b> project support to Google "
        "Photos API",
    },
    9: {
        __TYPE: __TEXT_TYPE,
        __PIC: "8.png",
        __TITLE: "Consent screen",
        __TEXT: "Go to <i>Credentials</i> in the panel on the left hand side under <i>APIs & Services</i> and click "
        "<i>[CONFIGURE CONSENT SCREEN]</i>",
    },
    10: {
        __TYPE: __TEXT_TYPE,
        __PIC: "9.png",
        __TITLE: "Create consent screen",
        __TEXT: "Choose <i>External</i> and click <i>[CREATE]</i>",
    },
    11: {
        __TYPE: __TEXT_TYPE,
        __PIC: "10.png",
        __TITLE: "Configure consent screen",
        __TEXT: "Put <i>ePiframe</i> in the <i>App name</i> field, type Google email used for Your <b>ePiframe</b> "
        "where necessary, scroll down and click on <i>[SAVE AND CONTINUE]</i> three times until You get to "
        "<b>Summary</b>. <br>Click <i>[BACK TO DASHBOARD]</i>. <br>Your application consent screen is ready!",
    },
    12: {
        __TYPE: __TEXT_TYPE,
        __PIC: "11.png",
        __TITLE: "Publish App",
        __TEXT: "Click on <i>[PUBLISH APP]</i> in <i>Oauth consent screen</i> section under <i>APIs & Services</i> to "
        "publish Your application",
    },
    13: {
        __TYPE: __TEXT_TYPE,
        __PIC: "12.png",
        __TITLE: "Create credentials",
        __TEXT: "Click on <i>+CREATE CREDENTIALS</i> and choose <i>OAuth client ID</i>",
    },
    14: {
        __TYPE: __TEXT_TYPE,
        __PIC: "13.png",
        __TITLE: "Configure credentials",
        __TEXT: "Pick <i>Desktop app</i> as <i>Application type</i> and put <i>ePiframe</i>	in the <i>Name</i> field. "
        "<br>Click <i>[CREATE]</i>",
    },
    15: {
        __TYPE: __TEXT_TYPE,
        __PIC: "14.png",
        __TITLE: "Download credentials",
        __TEXT: "You have created OAuth client for Your <b>ePiframe</b>! <br>Click on <i>DOWNLOAD JSON</i> to "
        "download JSON formatted credentials file",
    },
    16: {
        __TYPE: __TEXT_TYPE,
        __PIC: "15.png",
        __TITLE: "Find credentials",
        __TEXT: "You can always get it from the <i>Credentials</i> dashboard by clicking download icon in "
        "<i>Actions</i> column of Your desired Client ID",
    },
    17: {
        __TYPE: __UPLOAD_TYPE,
        __PIC: None,
        __TITLE: "Upload credentials",
        __TEXT: "Now upload the JSON credentials file by dropping it or choosing <i>[Upload File]</i> option. <br>Any "
        "existing credentials file will be backed up",
    },
    18: {
        __TYPE: __CODE_TYPE,
        __PIC: None,
        __TITLE: "Generate token",
        __TEXT: 'Almost done! Go to <br><a href="{}" class="text-wrap text-break" target="_blank">{}</a> <br>and '
        "authenticate with Your <b>ePiframe</b> Google account You have created project and credentials for. "
        "<br>After successful authentication <u>You will get an error (but that is ok)</u>, copy the whole "
        "address that is not reachable and paste it below. <br>Click on <i>[Generate Token]</i>. Any existing "
        "token file will be backed up",
    },
    19: {
        __TYPE: __TEXT_TYPE,
        __PIC: None,
        __TITLE: "Success",
        __TEXT: "<h4>All done!</h4> You have successfully activated Google Photos credentials and token for Your "
        "<b>ePiframe</b>! <br>Test Your frame and have fun!",
    },
}

auth_url = ""
flow: google_auth_oauthlib.flow.Flow
page = 0


def strip_html(data):
    p = re.compile(r"<.*?>")
    return p.sub("", data)


def get_auth_url():
    global flow
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        __CRED_FILE, scopes=["https://www.googleapis.com/auth/photoslibrary.readonly"]
    )
    flow.redirect_uri = "http://localhost:1/"
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    return str(authorization_url)


def gen_token(code_token):
    code_token = (
        re.search(r"code=(.*)&", code_token)
        .group(0)
        .replace("code=", "")
        .replace("&", "")
    )
    if not code_token or not flow:
        raise Exception()
    flow.fetch_token(code=code_token)
    credentials = flow.credentials
    googleapiclient.discovery.build(
        "photoslibrary", "v1", credentials=credentials, static_discovery=False
    )
    if os.path.exists(__TOKEN_FILE):
        shutil.copy(__TOKEN_FILE, __TOKEN_FILE + ".back")
    with open(__TOKEN_FILE, "wb") as token:
        pickle.dump(credentials, token)
    os.chmod(__TOKEN_FILE, 0o0666)


def generate():
    from flask import request, redirect, flash

    if request.method == "POST":
        try:
            gen_token(request.form.get("code"))
            return redirect(str(len(__PAGES.keys())))
        except Exception as exception_data:
            flash_error(exception_data)
            flash(
                "Error: The URL should be an exact copy of the generated URL and should not be empty!"
            )
            flash(
                "If something is still wrong then try to re-upload the credentials and try again"
            )
            return redirect(str(page))


def flash_error(exception_data):
    from flask import flash

    if (
        str(exception_data)
        or hasattr(exception_data, "message")
        and getattr(exception_data, "message", str(exception_data))
    ):
        flash(f"Error: {exception_data}")


def save_creds(content):
    if not content:
        raise Exception("Empty value")
    struct = json.loads(content)
    if check_credentials_json(struct):
        raise Exception("Wrong file content")
    if os.path.exists(__CRED_FILE):
        shutil.copy(__CRED_FILE, __CRED_FILE + ".back")
    with open(__CRED_FILE, "w") as file:
        file.write(content)
    os.chmod(__CRED_FILE, 0o0666)
    global auth_url
    auth_url = get_auth_url()


def check_credentials_json(struct):
    return (
        "installed" not in struct
        or "client_id" not in struct["installed"]
        or "client_secret" not in struct["installed"]
    )


def upload():
    from flask import request, redirect, flash

    if request.method == "POST":
        try:
            content = request.files.get("file").read().decode("utf-8")
            save_creds(content)
            return redirect(str(page + 1))
        except Exception:
            flash(
                "Error: wrong file uploaded! Make sure You are uploading JSON credentials file"
            )
            return redirect(str(page))


def stop():
    Timer(2.0, lambda: os._exit(0)).start()
    return "Tool shutting down...<br>You can close this page."


def steps(url=str()):
    global page
    if url and str.isdigit(url):
        page = max(min(len(__PAGES.keys()), int(url)), 1)
    else:
        page = 1
    toc = {__PAGES[key][__TITLE]: key for key in __PAGES}
    text = get_text()
    return get_steps_page(text, toc)


def get_steps_page(text, toc):
    from flask import render_template

    return render_template(
        __PAGE,
        type=__PAGES[page][__TYPE],
        page=page,
        text=text,
        pic=__PAGES[page][__PIC],
        title=__PAGES[page][__TITLE],
        previous=(str(page - 1) if page > 1 else str()),
        next=(str(page + 1) if page < len(__PAGES.keys()) - 1 else str()),
        toc=toc,
        last=len(__PAGES.keys()),
    )


def get_text():
    return (
        __PAGES[page][__TEXT]
        if not __PAGES[page][__TYPE] == __CODE_TYPE
        else f"<a href='{str(page - 1)}'>Link not generated yet! Upload credentials first!</a>"
        if not auth_url
        else str(__PAGES[page][__TEXT]).format(auth_url, auth_url)
    )


def start():
    try:
        from flask import Flask, render_template, request, redirect, flash
        import crypt

        check_templates()

        print(
            "Do You want to start a web version of Activation Tool (with visual guide) or just activate here in the "
            "console? "
        )
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}

        while True:
            choice = input("[Y/n]? [Default: Yes] ").lower() or "yes"

            if choice in valid:
                return valid[choice]
            else:
                print("Please respond with 'yes' or 'no' (or 'y' or 'n').")
    except Exception:
        print(
            "----- Probably this is not an ePiframe device or ePiframe is not yet installed so starting console mode "
            "----- "
        )
        return False


def check_templates():
    if not os.path.exists("templates/" + __PAGE):
        raise Exception()


def prepare_app():
    from flask import Flask
    import crypt

    global app
    app = Flask(__name__)
    app.config["SECRET_KEY"] = crypt.mksalt(crypt.METHOD_SHA512)
    app.add_url_rule("/upload", view_func=upload, methods=["POST"])
    app.add_url_rule("/generate", view_func=generate, methods=["POST"])
    app.add_url_rule("/stop", view_func=stop, methods=["POST"])
    app.add_url_rule("/<url>", methods=["GET"], view_func=steps)
    app.add_url_rule("/", defaults={"url": ""}, methods=["GET"], view_func=steps)


def get_ip():
    while True:
        ip_value = (
            input(f"Enter IP address [Leave empty for {IP} (under public IP address)]:")
            or IP
        )

        if re.match(
            r"^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$",
            ip_value,
        ):
            print("IP = " + ip_value)
            return ip_value
        else:
            print("Please provide a correct IP address")


def get_port():
    while True:
        print(
            "Any port below 5000 will need root privileges - start script with 'sudo'"
        )
        port_value = (
            input(f"Enter port number (1-65535) [Leave empty for {PORT}]:") or PORT
        )

        try:
            if 65535 >= int(port_value) >= 1:
                print("Port = " + port_value)
                return port_value
            else:
                raise Exception()
        except Exception:
            print("Please provide a value in 1-65535 range")


def print_text_pages():
    for item in [
        key
        for key in [key_value for key_value in __PAGES.keys()][:-1]
        if __PAGES[key][__TYPE] == __TEXT_TYPE
    ]:
        print("* " + strip_html(__PAGES[item]["text"]))


def get_json():
    while True:
        try:
            print(
                "* Now paste here the content (as it is) of downloaded JSON credentials file. Any existing "
                "credentials file will be backed up. "
            )
            creds = input("JSON credentials content: ")
            save_creds(creds)
            break
        except Exception as exception_object:
            print(f"Error: {exception_object}")


def get_code():
    while True:
        try:
            print("* Visit page:")
            print(auth_url)
            print(
                "and authenticate with Your ePiframe Google account You have created project and credentials for. "
                "After successful authentication You will get an error (but that is ok), copy the whole address "
                "that is not reachable and paste it below. "
            )
            code = input("URL: ")
            gen_token(code)
            break
        except Exception:
            print(
                "Error: The URL should be an exact copy of the generated URL and should not be empty!"
            )


def activate():
    res = start()
    if res:
        prepare_app()
        ip = get_ip()
        port = get_port()
        app.run(host=ip, port=int(port))
    else:
        print_text_pages()
        get_json()
        get_code()
        print("*** " + strip_html(__PAGES[len(__PAGES)]["text"]))


if __name__ == "__main__":
    activate()
