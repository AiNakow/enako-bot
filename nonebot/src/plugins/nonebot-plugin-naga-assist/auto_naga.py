import os
import httpx
import json
import time
import hashlib
import re
from .common import *
from .config import config

kanji = ["一", "二", "三", "四"]

class Auto_naga():
    __server = config.naga_assist_server
    __auto_naga_secret = config.naga_assist_secret
    __tenhou_title = "https://tenhou.net/6/#json="
    __report_domain = "https://naga.dmv.nico/htmls/"
    
    def __init__(self) -> None:
        pass

    def __get_haihu_last(self) -> int:
        haihu_list = os.listdir(haihu_dir)
        if haihu_list == []:
            return 0
        else:
            haihu_id_list = []
            for haihu in haihu_list:
                haihu_id_list.append(int(haihu.split(".")[0]))
            haihu_id_list.sort(reverse=True)
        return haihu_id_list[0]
    
    def __get_order(self, body: dict) -> dict:
        api_interface = self.__server + "/order"
        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = httpx.post(url=api_interface, headers=headers, data=json.dumps(body), timeout=100)
        except:
            return {"status": 400}
        response_json = response.json()
        print(response_json)
        if response_json["status"] != 200:
            return {"status": 400}
        
        timestamp = int(time.mktime(time.strptime(response_json["current"], "%Y-%m-%dT%H:%M:%S")))

        # 等待生成报告并获取报告
        if body["custom"]:
            order_list = self.get_order_list()
            if order_list == [] or order_list is None:
                return {"status": 400}
            time_list = []
            for order in order_list:
                if "custom_haihu" in order[0]:
                    time_list.append(order[0].split("_")[2])
                else:
                    time_list.append("2000-01-01T00:00:00")
            index = 0
            delta_s = 1000
            for i in range(len(time_list)):
                time_check = int(time.mktime(time.strptime(time_list[i], "%Y-%m-%dT%H:%M:%S")))
                if time_check >=  timestamp:
                    if delta_s > time_check - timestamp:
                        delta_s = time_check - timestamp
                        index = i
            report_id = order_list[index][0]
        else:
            report_id = re.match(r"log=([0-9a-z-]*)&", body["tenhou_url"]).group(1)
        
        flag = False
        time_counter = 0
        report_url = ""
        print(report_id)
        while time_counter < 301:
            report_list = self.get_report_list()
            for report in report_list:
                if report[0] == report_id:
                    flag = True
                    report_url = self.__report_domain + report[2] + ".html"
                    break
                
            if flag:
                break
            time_counter += 10
            time.sleep(10)

        if time_counter > 300:
            return {"status": 400}
                
        return {
            "status": 200, 
            "report": report_url
            }
    
    def get_report_list(self) -> list:
        api_interface = self.__server + "/order_report_list"
        try:
            response = httpx.get(url=api_interface, timeout=100)
        except:
            return None
        response_json = response.json()
        if response_json["status"] != 200:
            return None
        
        report_list = response_json["report"]

        return report_list
    
    def get_order_list(self) -> list:
        api_interface = self.__server + "/order_report_list"
        try:
            response = httpx.get(url=api_interface, timeout=100)
        except:
            return None
        response_json = response.json()
        if response_json["status"] != 200:
            return None
        
        order_list = response_json["order"]

        return order_list

    def convert_majsoul(self, majsoul_url: str) -> dict:
        api_interface = self.__server + "/convert_majsoul"
        headers = {
            "Content-Type": "application/json"
        }
        body = {
            "secret": self.__auto_naga_secret,
            "majsoul_url": majsoul_url
        }
        
        try:
            response = httpx.post(url=api_interface, headers=headers, data=json.dumps(body), timeout=100)
        except httpx.HTTPError as exc:
            print(exc)
            return {"status": 400}
        response_json = response.json()
        if response_json["status"] != 200:
            print(response_json)
            return {"status": 400}

        haihu_data = response_json["message"]

        title = " ".join(haihu_data[0]["title"])
        player = " ".join(haihu_data[0]["name"])
        preview = []
        for game in haihu_data:
            game_meta = game["log"][0][0]
            game_title = (
                kanji[game_meta[0]%4],
                game_meta[1],
                game_meta[2]
                )
            if game_meta[0] < 4:
                preview.append("东{0}局 {1}本场 场供{2}".format(*game_title))
            else:
                preview.append("南{0}局 {1}本场 场供{2}".format(*game_title))

        # 将牌谱数据存储到本地
        haihu_id = self.__get_haihu_last() + 1
        haihu_path = os.path.join(haihu_dir, "{0}.txt".format(haihu_id))
        with open(file=haihu_path, mode="w", encoding="utf-8") as f:
            for game in haihu_data:
                f.write(self.__tenhou_title + json.dumps(game) + "\n")
        
        result = {
            "status": 200,
            "haihu_id": haihu_id,
            "title": title,
            "player": player,
            "preview": preview
        }

        return result
    
    def analyse_tenhou(self, tenhou_url: str) -> str:
        body = {
            "secret": self.__auto_naga_secret,
            "custom": False,
            "tenhou_url": tenhou_url,
        }

        return self.__get_order(body=body)
    
    def analyse_custom(self, haihu_id: int, game_list: list, analyse_type: list = ['2', '4']) -> str:
        haihu_file = os.path.join(haihu_dir, "{0}.txt".format(haihu_id))
        with open(file=haihu_file, mode="r", encoding="utf-8") as f:
            haihus_origin = f.readlines()
        haihus = []
        for game in game_list:
            haihus.append(json.loads(haihus_origin[game].split('=')[1]))

        body = {
            "secret": self.__auto_naga_secret,
            "custom": True,
            "haihus": haihus,
            "player_types": ", ".join(analyse_type)
        }

        return self.__get_order(body=body)
    
