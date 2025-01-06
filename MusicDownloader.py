import os
import requests
import re
from yt_dlp import YoutubeDL
import time
import sys
import subprocess
import threading
import base64
import json
import argparse

class MusicDownloader:
    def __init__(self, save_path="Music"):
        self.save_path = save_path
        os.makedirs(self.save_path, exist_ok=True)
        self.client_id = 'ca9b11813eee45aea23fcc5b40be7d7e'
        self.client_secret = 'da54ee2b87d14bf3a19aa92cc8b0bcd7'
        self.spotify_token = None
        self.spinner = Spinner()

    def get_spotify_access_token(self):
        try:
            token_manager = SpotifyTokenManager(self.client_id, self.client_secret)
            self.spotify_token = token_manager.getToken();  
            return self.spotify_token
        except Exception as e:
            print("Failed to get Spotify access token:", e)
            return None

    def fetch_song_metadata(self, song_name):
        if not self.spotify_token:
            self.get_spotify_access_token()
        if not self.spotify_token:
            return None 
        print("\rFetching track list from Spotify...")
        self.spinner.start()
        url = "https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {self.spotify_token}"}
        params = {"q": song_name, "type": "track", "limit": 10}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            tracks = response.json()["tracks"]["items"]

            if not tracks:
                self.spinner.stop()
                print("\rNo tracks found...")
                return None

            self.spinner.stop()
            print("\rTop 10 tracks:")
            for idx, track in enumerate(tracks, start=1):
                track_artists = ", ".join(artist["name"] for artist in track["artists"])
                print(f"{idx}. {track['name']} by {track_artists}")

            while True:
                try:
                    choice = int(input("Select a track (1-10): "))
                    if 1 <= choice <= len(tracks):
                        selected_track = tracks[choice - 1]
                        break
                    else:
                        print("Please choose a valid option between 1 and 10.")
                except ValueError:
                    print("Invalid input. Please enter a number between 1 and 10.")
            print("Fetching metadata for the selected track...")
            self.spinner.start()
            artist_id = selected_track["artists"][0]["id"]
            artist_url = f"https://api.spotify.com/v1/artists/{artist_id}"
            artist_response = requests.get(artist_url, headers=headers)
            artist_response.raise_for_status()
            artist_data = artist_response.json()
            genres = ", ".join(artist_data.get("genres", []))
            album = selected_track["album"]
            album_artists = ", ".join(artist["name"] for artist in album["artists"])
            album_images = selected_track["album"]["images"]
            cover_image_url = album_images[0]["url"] if album_images else None

            metadata = {
                "title": selected_track["name"].replace('?',''),
                "artist": ", ".join(artist["name"] for artist in selected_track["artists"]),
                "album": album["name"],
                "album_artist": album_artists,
                "year": album["release_date"].split("-")[0],
                "genre": genres,
                "track_id": selected_track["id"],
                "popularity": selected_track.get("popularity", "N/A"),
                "track_number": selected_track["track_number"],
                "duration_ms": selected_track["duration_ms"],
                "cover_image_url": cover_image_url
            }

            for key, value in metadata.items():
                if isinstance(value, str):
                    metadata[key] = re.sub(r'["?]', '', value)
            self.spinner.stop()
            print("\rMetadata fetched successfully...")
            return metadata
        except Exception as e:
            self.spinner.stop()
            print("\rFailed to fetch song metadata:", e)
            return None

    def downloadAudio(self, url):
        modified_title = None
        print("Fetching Audio Title from YouTube...")
        self.spinner.start()
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)  # Get metadata only
            raw_title = info['title']
            modified_title = self.modifyTitle(raw_title)
        self.spinner.stop()
        print("\rTitle : " + modified_title)
        choice = input("\rDo u want to edit the title (y/n): ")
        if choice == 'y':
            modified_title = input("\rEdit the title : ")
        
        metadata = self.fetch_song_metadata(modified_title) if modified_title else {}
        if not metadata:
            proceed = input("\rProceed without metadata (y/n) : ")
            if proceed == 'n':
                sys.exit()
        if len(metadata["title"]) > 50:
            print("\rMetadata's Title : "+metadata["title"])
            inp = input("\rmetadata's title is too long(>50) will u edit (y/n): ")
            if inp == 'y':
                metadata["title"] = input("Edit the title : ")
        cover_image_data = None
        if metadata and 'cover_image_url' in metadata:
            cover_image_data = self.fetch_cover_image(metadata["cover_image_url"])
        if not cover_image_data:
            proceed = input("\rProceed without metadata (y/n) : ")
            if proceed == 'n':
                sys.exit()
        
        options = {
            'format': 'bestaudio/best',  
            'extractaudio': True,        
            'audioquality': '0',         
            'outtmpl': os.path.join(self.save_path, f'{metadata["title"]}.%(ext)s'),
            'noplaylist': True,
            'logger': QuietLogger(),
            'progress_hooks': [self._progress_hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',  
                'preferredquality': '320', 
            }],
        }

        try:
            print("Downloading and converting audio to M4A...")
            self.spinner.start()
            with YoutubeDL(options) as ydl:
                result = ydl.extract_info(url, download=True)
                downloaded_file = os.path.join(self.save_path, f"{metadata["title"]}.m4a")
                self.spinner.stop()
            print("\rDownload completed! File saved in:", downloaded_file)
            return downloaded_file, metadata, cover_image_data
        except Exception as e:
            print("An error occurred during downloading:", e)
            return None, None, None

    def modifyTitle(self,title):
        return re.sub(r'[<>:"/\\|?*.]', '_', title)

    def _progress_hook(self, d):
        # Update spinner or show progress
        if d['status'] == 'downloading':
            self.spinner.stop()
            print(f"\rDownloading: {d['_percent_str']} | Speed: {d['_speed_str']}", end="")
        elif d['status'] == 'finished':
            print("\nDownload finished, converting file...")
            self.spinner.start()

    def add_metadata_and_coverimage(self, input_file, cover_image_data, metadata=None):
        print("Adding metadata and cover image to the file...")
        spinner = Spinner()
        spinner.start()
        if not input_file.endswith(".m4a"):
            spinner.stop()
            print(f"\rInput file {input_file} is not in M4A format.")
            return

        temp_output_file = input_file.replace(".m4a", "_temp.m4a")  

        metadata_args = []
        if metadata:
            if 'title' in metadata:
                metadata_args.append(f'-metadata title="{metadata["title"]}"')
            if 'artist' in metadata:
                metadata_args.append(f'-metadata artist="{metadata["artist"]}"')
            if 'album' in metadata:
                metadata_args.append(f'-metadata album="{metadata["album"]}"')
            if 'genre' in metadata:
                metadata_args.append(f'-metadata genre="{metadata["genre"]}"')
            if 'year' in metadata:
                metadata_args.append(f'-metadata date="{metadata["year"]}"')
            if 'track_number' in metadata:
                metadata_args.append(f'-metadata track="{metadata["track_number"]}"')
            if 'album_artist' in metadata:
                metadata_args.append(f'-metadata album_artist="{metadata["album_artist"]}"')

        try: 
            ffmpeg_cmd = (
                f'ffmpeg -y -i "{input_file}" -i pipe:0 '
                f'-map 0:a -map 1:v -c:v mjpeg -c:a copy '
                f'{" ".join(metadata_args)} '
                f'-disposition:v attached_pic "{temp_output_file}"'
            )
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True 
            )
            stdout, stderr = process.communicate(input=cover_image_data)

            if process.returncode != 0:
                spinner.stop()
                print("\rFFmpeg error:", stderr.decode())
                if os.path.exists(temp_output_file): 
                    os.remove(temp_output_file)
            else:
                os.replace(temp_output_file, input_file)
                self.check_audio_properties(input_file)
                spinner.stop()
                print(f"\rAudio file is succeccfully updated with metadata and cover image : {input_file}")
        except Exception as e:
            spinner.stop()
            print("\rError updating the audio file with metadata and cover image :", e)

    def fetch_cover_image(self, url):
        try:
            print("Fetching cover Image from the selected track...")
            self.spinner.start()
            response = requests.get(url, stream=True)
            response.raise_for_status()
            self.spinner.stop()
            print("\rCover image fetched successfully...")
            return response.content 
        except Exception as e:
            self.spinner.stop()
            print(f"\rFailed to fetch cover image: {e}")
            return None

    def check_audio_properties(self,file_path):
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', file_path],
                stderr=subprocess.PIPE,  # FFmpeg writes details to stderr
                stdout=subprocess.PIPE,
            )
            # Decode output safely with 'replace' to handle unknown characters
            output = result.stderr.decode('utf-8', errors='replace')
            audio_properties = {}

            for line in output.splitlines():
                if "Audio:" in line:
                    print("\rAudio Details:", line)  

                    codec_match = re.search(r'Audio:\s(\w+)', line)
                    sample_rate_match = re.search(r'(\d+)\s*Hz', line)
                    channel_match = re.search(r'(mono|stereo)', line, re.IGNORECASE)
                    bitrate_match = re.search(r'(\d+)\s*kb/s', line)

                    audio_properties['codec'] = codec_match.group(1) if codec_match else "Unknown"
                    audio_properties['sampling_rate'] = sample_rate_match.group(1) if sample_rate_match else "Unknown"
                    audio_properties['channels'] = channel_match.group(1).lower() if channel_match else "Unknown"
                    audio_properties['bitrate'] = bitrate_match.group(1) if bitrate_match else "Unknown"
                    break  

            print("\rcodec         :",audio_properties["codec"])
            print("\rbitrate       :",audio_properties["bitrate"],"kb/s")
            print("\rchannels      :",audio_properties["channels"])
            print("\rsampling_rate :",audio_properties["sampling_rate"],"Hz")

        except Exception as e:
            print("\rError checking audio properties:", e)
            return None

    def process(self, video_url):
        downloaded_file, metadata, cover_image_data = self.downloadAudio(video_url)
        if downloaded_file:
            self.add_metadata_and_coverimage(downloaded_file, cover_image_data, metadata=metadata)

class SpotifyTokenManager:
    def __init__(self, client_id, client_secret, token_file="D:/Projects/Python/MyMusic//TokenStore/spotify_token.json"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file

    def loadToken(self):
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as file:
                return json.load(file)
        return None

    def saveToken(self, token_data):
        with open(self.token_file, 'w') as file:
            json.dump(token_data, file)

    def isTokenExpired(self, token_data):
        expiry_time = token_data.get("expiry_time", 0)
        return time.time() >= expiry_time

    def requestNewToken(self):
        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": "Basic " + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        }
        data = {"grant_type": "client_credentials"}

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_info = response.json()
            # Calculate expiry time: current time + expires_in seconds
            expiry_time = time.time() + token_info['expires_in']
            token_info['expiry_time'] = expiry_time
            print("Token acquired...")
            return token_info
        except Exception as e:
            print("Failed to get Spotify access token:", e)
            return None
        
    def getToken(self):
        token_data = self.loadToken()
        if token_data is None or self.isTokenExpired(token_data):
            print("\rFetching new Spotify Token...")
            token_data = self.requestNewToken()
            self.saveToken(token_data)
            return token_data['access_token']
        else:
            print("\rUsing previous Spotify Token...")
            return token_data['access_token']

class Spinner:
    def __init__(self):
        self.spinner_chars = ['|', '/', '-', '\\']
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._animate)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()  # Wait for the thread to finish

    def _animate(self):
        while self.running:
            for char in self.spinner_chars:
                print(f"\r{char}", end="", flush=True)
                time.sleep(0.1)
                if not self.running:
                    break

class QuietLogger:
    def debug(self, msg):
        pass  # Suppress debug messages
    def warning(self, msg):
        pass  # Suppress warning messages
    def error(self, msg):
        print(msg)

def main():
    parser = argparse.ArgumentParser(description="Music Downloader CLI Tool")
    parser.add_argument("urls", nargs='+', help="One or more YouTube video URLs to process")
    parser.add_argument("--save-path", default="Music", help="Path to save the downloaded files")
    args = parser.parse_args()

    downloader = MusicDownloader(save_path=args.save_path)
    for url in args.urls:
        downloader.process(url)

if __name__ == "__main__":
    main()
