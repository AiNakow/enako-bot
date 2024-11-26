import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
userdata_dir = os.path.join(data_dir, "userdata")
haihu_dir = os.path.join(data_dir, "haihus")
userdata_file = os.path.join(userdata_dir, "user.db")


template_game_preview = """
牌谱编号: {0}
{1}
{2}
{3}
"""

template_analyse_hint = """
可以发送以下命令对某小局进行分析(以东一局0本场为例):
/牌谱分析 自定义 {0} {1}
或使用以下命令对多个小局进行分析(以全部小局为例):
/牌谱分析 自定义 {0} {2}-{3}
"""