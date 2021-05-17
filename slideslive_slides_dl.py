import argparse
import re
import os
import requests
import pandas as pd
import xml.etree.ElementTree as et
import json
import time
from typing import List, Optional, Tuple, Callable


def parse_json(slides, df_cols):
    rows = []
    for slide in slides["slides"]:
        res = []
        if slide is not None:
            res.append(slide["time"])
            res.append(slide["image"]["name"])
        rows.append({df_cols[i]: res[i] for i, _ in enumerate(df_cols)})

    out_df = pd.DataFrame(rows, columns=df_cols)

    return out_df


def parse_xml(xml_file, df_cols: List[str]) -> pd.DataFrame:
    """Parse the input XML file and store the result in a pandas
    DataFrame with the given columns.

    Features will be parsed from the text content
    of each sub-element.

    based on:
    https://medium.com/@robertopreste/from-xml-to-pandas-dataframes-9292980b1c1c
    """
    xtree = et.parse(xml_file)
    xroot = xtree.getroot()
    rows = []

    for node in xroot:
        res = []
        for el in df_cols[0:]:
            if node is not None and node.find(el) is not None:
                res.append(node.find(el).text)
            else:
                res.append(None)
        rows.append({df_cols[i]: res[i] for i, _ in enumerate(df_cols)})

    out_df = pd.DataFrame(rows, columns=df_cols)

    return out_df


def get_video_id(video_url):
    ids = re.findall("https://slideslive\\.(com|de)/([0-9]*)/([^/]*)(.*)", video_url)
    if len(ids) < 1:
        print("Error: {0} is not a correct url.".format(video_url))
        exit()
    return ids[0][1], ids[0][2]


def download_save_file(url, save_path, headers, wait_time=0.2):
    print(f"Downloading {url}")
    r = requests.get(url, headers=headers)
    with open(save_path, "wb") as f:
        f.write(r.content)
    time.sleep(wait_time)


def json_path(video_id, video_name):
    file_path = f"slides_json/{video_id}.json".format(video_id)
    return file_path


def download_slides_json(
    folder_name: str, base_json_url, video_id, video_name, headers, wait_time
):
    slides_folder = f"{folder_name}/slides"
    if not os.path.exists(slides_folder):
        os.makedirs(slides_folder)

    if os.path.isfile(slides_folder):
        print(
            "Error: {0} is a file, can't create a folder with that name".format(
                folder_name
            )
        )
        exit()

    file_path = "{0}/{1}.json".format(folder_name, video_id)
    if not os.path.exists(file_path):
        json_url = f"{base_json_url}{video_id}/v1/slides.json"
        print("downloading {}".format(file_path))
        download_save_file(json_url, file_path, headers, wait_time)

    return json.load(open(file_path, "r"))


def download_slides_xml(base_xml_url, video_id, video_name, headers, wait_time):
    folder_name = "{0}-{1}".format(video_id, video_name)
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)

    if os.path.isfile(folder_name):
        print(
            "Error: {0} is a file, can't create a folder with that name".format(
                folder_name
            )
        )
        exit()

    file_path = "{0}/{1}.xml".format(folder_name, video_id)
    if not os.path.exists(file_path):
        xml_url = "{0}{1}/{1}.xml".format(base_xml_url, video_id)
        print("downloading {}".format(file_path))
        download_save_file(xml_url, file_path, headers, wait_time)

    return open(file_path, "r")


def download_slides(
    folder_name,
    video_id,
    video_name,
    df,
    base_img_url,
    size,
    headers,
    wait_time,
    neg_idx: int = 0,
):
    folder_name = f"{folder_name}/slides"

    for index, row in df.iloc[neg_idx:].iterrows():
        img_url = base_img_url.format(video_id, row["slide-name"], size)
        file_path = "{0}/{3}-{1}-{2}.jpg".format(
            folder_name, row["slide-name"], size, row["time"]
        )
        print("downloading {}".format(file_path))
        download_save_file(img_url, file_path, headers, wait_time)


def time_convert(t1: int) -> int:
    """
    Need to manually convert to seconds
    """
    return int(t1 // 1000)


def create_ffmpeg_concat_file(folder_name, video_id, video_name, df, size):
    ffmpeg_file_path = f"{folder_name}/ffmpeg_concat.txt"
    if os.path.exists(ffmpeg_file_path):
        return
    with open(ffmpeg_file_path, "a") as f:
        last_time = 0
        last_file_path = ""
        for index, row in df.iterrows():
            # if not first, write duration
            t = time_convert(row["time"])
            duration = t - last_time
            # duration = int(row["timeSec"]) - last_time
            if index != 0:
                f.write("duration {0}\n".format(duration))
            file_path = "{3}-{1}-{2}.jpg".format(
                folder_name, row["slide-name"], size, row["time"]
            )
            f.write("file '{0}'\n".format(file_path))
            last_time = t
            # last_time = int(row["timeSec"])
            last_file_path = file_path
        # add some time for the last slide, we have no information how long it should be shown.
        f.write("duration 30\n")
        # Due to a quirk, the last image has to be specified twice - the 2nd time without any duration directive
        # see: https://trac.ffmpeg.org/wiki/Slideshow
        # still not bug free
        f.write("file '{0}'\n".format(last_file_path))


def get_folder_name(format, video_id, video_name):
    OUTPUT_FOLDER = "slideshares"
    folder = f"{OUTPUT_FOLDER}/{format}/{video_name}-{video_id}"
    return folder


def get_ss():
    parser = argparse.ArgumentParser()
    parser.add_argument("id")
    parser.add_argument("name")
    parser.add_argument("format", default="workshop")
    parser.add_argument("--slide_neg_index", "-s", default=0, type=int)
    parser.fromfile_prefix_chars
    parser.add_argument("--size", default="big", help="medium or big")
    parser.add_argument(
        "--useragent",
        default="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/76.0.3809.100 Chrome/76.0.3809.100 Safari/537.36",
    )
    parser.add_argument(
        "--basedataurl",
        default="https://d2ygwrecguqg66.cloudfront.net/data/presentations/",
        # https://d2ygwrecguqg66.cloudfront.net/data/presentations/38956520/v1/slides.json
    )
    parser.add_argument(
        "--waittime",
        default="0.2",
        type=float,
        help="seconds to wait after each download",
    )
    args = parser.parse_args()

    headers = {"User-Agent": args.useragent}
    base_img_url = "{0}{1}".format(args.basedataurl, "{0}/slides/{2}/{1}.jpg")

    # video_id, video_name = get_video_id(args.url)
    format, video_id, video_name = args.format, args.id, args.name

    output_folder = get_folder_name(format, video_id, video_name)
    js = download_slides_json(
        output_folder, args.basedataurl, video_id, video_name, headers, args.waittime
    )
    # df_cols = ["orderId", "timeSec", "time", "slideName"]
    df_cols = ["time", "slide-name"]
    df = parse_json(js, df_cols)
    download_slides(
        output_folder,
        video_id,
        video_name,
        df,
        base_img_url,
        args.size,
        headers,
        args.waittime,
        args.slide_neg_index,
    )
    create_ffmpeg_concat_file(output_folder, video_id, video_name, df, args.size)


if __name__ == "__main__":
    get_ss()
