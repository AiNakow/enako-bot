#!/bin/bash

prefix_url="https://cdn.tenhou.net/2/t/"
save_dir="./static"  

mkdir -p "$save_dir"

for i in {0..9}; do
    filename="${i}s.gif"
    curl -L "${prefix_url}${filename}" -o "${save_dir}/${filename}"
done

for i in {0..9}; do
    filename="${i}m.gif"
    curl -L "${prefix_url}${filename}" -o "${save_dir}/${filename}"
done

for i in {0..9}; do
    filename="${i}p.gif"
    curl -L "${prefix_url}${filename}" -o "${save_dir}/${filename}"
done

for i in {1..7}; do
    filename="${i}z.gif"
    curl -L "${prefix_url}${filename}" -o "${save_dir}/${filename}"
done

echo "所有GIF已下载到：$save_dir"

