# VAD service based on [py-webrtcvad](https://github.com/wiseman/py-webrtcvad)

Build the docker: `docker build -t vad:v1.0 .`

Run the docker: `./run.sh`

Sample client:
1. python client: `python client.py path/to/audio_video/file`
2. curl client: `curl -X POST "http://192.168.1.101:8000/uploadfile" -H  "accept: application/json" -H  "Content-Type: multipart/form-data" -F "file=@file_path"`

Output format:
```json
[
    {
        "start": 0.,
        "end": 10.,
        "duration": 7.920000000000021,
        "aggressiveness": 0,
        "data": "base64 encoded of raw pcm data"
    },
    ...
]
```
