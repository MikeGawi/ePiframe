class Credentials:
    valid = False
    expired = True
    refresh_token = True

    @staticmethod
    def refresh(request):
        print("Credentials_refresh")


class Flow:
    credentials = "Flow_credentials"

    @classmethod
    def from_client_secrets_file(cls, client_secrets_file, scopes, **kwargs):
        print(f"Flow_from_client_secrets_file {client_secrets_file=} {scopes=}")
        return cls

    @classmethod
    def run_local_server(cls, port=0):
        print("Flow_run_local_server")
        return Credentials()

    @classmethod
    def fetch_token(cls, **kwargs):
        print("Flow_fetch_token")
        return cls
