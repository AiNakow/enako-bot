import os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
database_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")
gsz_userdata_file = os.path.join(database_dir, "gsz_userdata.db")
