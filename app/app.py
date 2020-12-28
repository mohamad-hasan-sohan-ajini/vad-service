from fastapi import FastAPI, File, UploadFile

from .vad import vad, vad_file

app = FastAPI()


@app.post("/uploadfile")
async def create_upload_file(file: UploadFile = File(...)):
    data = await file.read()
    result = vad(data)
    return result
