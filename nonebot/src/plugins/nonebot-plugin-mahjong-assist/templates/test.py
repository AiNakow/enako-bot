from jinja2 import Environment, FileSystemLoader

import os

template_dir = os.path.dirname(__file__)

def create_jinja2_env():
    """创建 Jinja2 环境"""
    env = Environment(loader=FileSystemLoader(template_dir))
    return env


jinja_env = create_jinja2_env()

def tenhou_paili_analyse(analyse_type, tehai_input):
    t = jinja_env.get_template("tenhou_paili.html")
    content = t.render(static_path=os.path.join(template_dir, "static/"), typeStr=analyse_type, tehaiInputStr=tehai_input)
    return content.encode('utf-8')

if __name__ == "__main__":
    # 测试模板渲染
    result = tenhou_paili_analyse("q", "123566678999s11z")
    with open("output.html", "wb") as f:
        f.write(result)
    print("模板渲染成功，结果已保存到 output.html")