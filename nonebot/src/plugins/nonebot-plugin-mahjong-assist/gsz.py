import httpx
import json

class Gsz:
    api_server = "https://gsz.rmlinking.com/gszapi"

    @staticmethod
    def get_userinfo_by_name(username: str) -> dict:
        api_interface = Gsz.api_server + "/customer/getCustomerByName?name=" + username
        try:
            response = httpx.get(url=api_interface, timeout=100)
        except:
            return None
        response_json = response.json()
        if response_json["code"] != 200:
            return None