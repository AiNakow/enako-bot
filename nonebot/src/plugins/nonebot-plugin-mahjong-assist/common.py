import os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
model_dir = os.path.join(plugin_dir, "model_ocr")
data_dir = "/app/plugin_data/mahjong-assist"
data_collection_file = os.path.join(data_dir, "images.txt")