from jinja2 import Environment, FileSystemLoader
import httpx
import json
import base64

template_dir = 'src/plugins/nonebot-plugin-mahjong-assist/templates'
def create_jinja2_env():
    """创建 Jinja2 环境"""
    env = Environment(loader=FileSystemLoader(template_dir))
    return env

jinja_env = create_jinja2_env()

def test_template():
    API_ENDPOINTS = {
            "basic": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerByName',
            "tech": 'https://gsz.rmlinking.com/gszapi/score/tech',
            "rateList": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerRateList'
        }

    username = '铃木大介'
    basic_data = httpx.get(API_ENDPOINTS["basic"] + f'?name={username}').json()
    if basic_data['code'] != 200:
        return None
    custom_id= basic_data['data']['id']
    qq = basic_data['data']['qq']
    print(qq)
    tech_data = httpx.get(API_ENDPOINTS["tech"] + f'?customerId={custom_id}').json()
    if tech_data['code'] != 200:
        return None
    rateList_data = httpx.get(API_ENDPOINTS["rateList"] + f'?customerId={custom_id}').json()
    if rateList_data['code'] != 200:
        return None

    raw_pic = httpx.get(f'https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=jpg').content

    template = jinja_env.get_template('gsz_info.html')
    content = template.render(username=username, userpic=base64.b64encode(raw_pic).decode("utf-8"), basic_data=json.dumps(basic_data["data"]), tech_data=json.dumps(tech_data["data"]), rateList_data=json.dumps(rateList_data["data"]))
    
    with open('src/plugins/nonebot-plugin-mahjong-assist/test/result.html', 'w') as f:
        f.write(content)

if __name__ == '__main__':
    test_template()