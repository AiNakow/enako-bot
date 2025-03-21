import os

RAND_RESPONSE = ["喵呜", "nya~", "ニャーコ！", "Meow~", "等死吧你"]

plugin_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = "/app/plugin_data/management"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

database_dir = os.path.join(data_dir, "database")
if not os.path.exists(database_dir):
    os.makedirs(database_dir)

plugin_data_file = os.path.join(database_dir, "plugin_data.db")

