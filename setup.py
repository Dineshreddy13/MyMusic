from setuptools import setup

setup(
    name="MusicDownloader",
    version="1.3",
    py_modules=["MusicDownloader"],  # Replace with the actual name of your script file without the `.py` extension
    install_requires=[
        "ffmpeg-python",
        "yt-dlp",
        "requests"
    ],
    entry_points={
        "console_scripts": [
            "MusicDownloader=MusicDownloader:main",  # Replace `music_downloader` with your script name
        ],
    },
)
