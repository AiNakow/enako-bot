import os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(plugin_dir, "templates")

data_dir = "/app/plugin_data/gsz_assist"
database_dir = os.path.join(data_dir, "database")
gsz_userdata_file = os.path.join(database_dir, "gsz_userdata.db")
