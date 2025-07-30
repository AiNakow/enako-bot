#!/bin/bash

prefix_url="https://cdn.tenhou.net/2"
save_dir="./static"  

mkdir -p "$save_dir"
mkdir -p "$save_dir/t"
mkdir -p "$save_dir/a"

for i in {0..9}; do
    filename="${i}s.gif"
    curl -L "${prefix_url}/t/${filename}" -o "${save_dir}/t/${filename}"
done

for i in {0..9}; do
    filename="${i}m.gif"
    curl -L "${prefix_url}/t/${filename}" -o "${save_dir}/t/${filename}"
done

for i in {0..9}; do
    filename="${i}p.gif"
    curl -L "${prefix_url}/t/${filename}" -o "${save_dir}/t/${filename}"
done

for i in {1..7}; do
    filename="${i}z.gif"
    curl -L "${prefix_url}/t/${filename}" -o "${save_dir}/t/${filename}"
done

# a
for i in {0..9}; do
    filename="${i}s.gif"
    curl -L "${prefix_url}/a/${filename}" -o "${save_dir}/a/${filename}"
done

for i in {0..9}; do
    filename="${i}m.gif"
    curl -L "${prefix_url}/a/${filename}" -o "${save_dir}/a/${filename}"
done

for i in {0..9}; do
    filename="${i}p.gif"
    curl -L "${prefix_url}/a/${filename}" -o "${save_dir}/a/${filename}"
done

for i in {1..7}; do
    filename="${i}z.gif"
    curl -L "${prefix_url}/a/${filename}" -o "${save_dir}/a/${filename}"
done

echo "所有GIF已下载到：$save_dir"

