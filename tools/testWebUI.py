#!/usr/bin/env python3

from flask import Flask
import sys
import re

IP = "0.0.0.0"
PORT = "80"
app = Flask(__name__)
app.config["SECRET_KEY"] = "This is secret"


@app.route("/")
def hello_world():
    return "ePiframe says 'Hello from the Web'!"


print("ePiframe - e-Paper Raspberry Pi Photo Frame - WebUI test tool.")
print("This tool will help test WebUI port and IP run for ePiframe.")

if "--help" not in [argument.lower() for argument in sys.argv]:
    while True:
        ip = (
            input(f"Enter IP address [Leave empty for {IP} (under public IP address)]:")
            or IP
        )

        if re.match(
            r"^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$",
            ip,
        ):
            print("IP = " + ip)
            break
        else:
            sys.stdout.write("Please provide a correct IP address\n")

    while True:
        print(
            "Any port below 5000 will need root privilleges - start script with 'sudo'"
        )
        port = input(f"Enter port number (1-65535) [Leave empty for {PORT}]:") or PORT

        try:
            int(port)
            if 65535 >= int(port) >= 1:
                print("Port = " + port)
                break
            else:
                sys.stdout.write("Please provide a value in 1-65535 range\n")
        except Exception:
            sys.stdout.write("Please provide a value in 1-65535 range\n")
            pass

    print("Setting up web...")
    print("Press Ctrl+C to stop")
    print("Now check under provided IP address and port for the response")
    app.run(host=ip, port=int(port))
