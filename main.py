import os
import time
import json
import logging

import requests

logging.basicConfig(
    style="{",
    level=logging.INFO,
    format="[{levelname}] {asctime} {module} {message}",
    datefmt='%H:%M:%S'
)

try:
    with open("info.json") as fp:
        info = json.load(fp)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    with open("info.json", "w") as fp:
        info = {"client_id": ""}
        json.dump(info, fp, indent=4)

if not info["client_id"]:
    raise ValueError("Client ID required in info.json file")

session = requests.Session()
session.headers["Client-ID"] = info["client_id"]

def is_live(name):
    url = "https://api.twitch.tv/helix/streams"
    return bool(session.get(url, params={"user_login":name}).json()["data"])

def parse_format(text):
    max_resolution, max_framerate = text.split("p")
    
    return float(max_resolution), float(max_framerate or 30)

def download(name, parts_url):
    current_section = None
    fp = None
    last_downloaded = -1

    while True:
        response = session.get(parts_url)
        logging.info(f"Lines {response.status_code}")
        response = response.text.splitlines()

        sequence_start = int(response[3].split(":")[1])

        for sequence, url in enumerate(response[10::3], sequence_start):
            if sequence > last_downloaded:
                if sequence % 5 == 0:
                    if fp:
                        fp.close()
                    fp = open(f"{name}/{sequence//5:.0f}.ts", "wb")
                    current_section = sequence // 5

                    logging.info(f"New {sequence}")
                    fp.write(session.get(url).content)
                elif sequence // 5 == current_section:
                    logging.info(f"Add {sequence}")
                    fp.write(session.get(url).content)
                last_downloaded = sequence

        time.sleep(10)

def download_parts(name, max_format):
    token_url = f"https://api.twitch.tv/api/channels/{name}/access_token"
    url = f"https://usher.ttvnw.net/api/channel/hls/{name}.m3u8"

    line = None

    while True:
        response = session.get(token_url)
        logging.info(f"Token {response.status_code}")
        response = response.json()

        parameters = {
            "token": response["token"],
            "sig": response["sig"],
            "allow_source": "true"
        }

        while True:
            response = session.get(url, params=parameters)
            logging.info(f"Formats {response.status_code}")

            if response.status_code == 403: # Token expired
                break
            elif response.status_code == 404: # Streamer offline
                return
            
            lines = response.text.splitlines()

            if line is not None:
                logging.info(f"Format found {_format} {line}")
                download(name, lines[line])
            else:
                for n, (f, url) in enumerate(zip(lines[2::3], lines[4::3])):
                    _format = f.split(",")[2].strip('NAME= (source)"')
                    if parse_format(_format) <= max_format:
                        line = n * 3 + 4
                        logging.info(f"Format found {_format}")
                        download(name, url)

def main(name, max_format="infp"):
    os.makedirs(name, exist_ok=True)
    max_format = parse_format(max_format)

    logging.info(f"Start {name}")

    while True:
        try:
            if not is_live(name):
                time.sleep(5)
                continue

            logging.info(f"Live {name}")
            download_parts(name, max_format)
        except requests.exceptions.ConnectionError:
            logging.error("Connection Error")
            time.sleep(10)

if __name__ == "__main__":
    main("cryaotic")
