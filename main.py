import os
import json
import time
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(title="SlideQuiz API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    text = ""
    if ext == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += page.extract_text() or ""
        except Exception:
            text = file_bytes.decode("utf-8", errors="ignore")
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    return text

@app.get("/")
def read_root():
    return {"status": "ok", "message": "SlideQuiz API is running"}

@app.post("/generate-quiz")
async def generate_quiz(file: UploadFile = File(...)):
    try:
        content = await file.read()
        raw_text = extract_text_from_file(content, file.filename)
        
        if not raw_text.strip():
            raw_text = content.decode("utf-8", errors="ignore")
            
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Dosyadan metin okunamadi.")
            
        prompt = f"""
Sen bir egitim uzmanisin. Asagida sana verilen ders notlarindan veya slayt iceriginden TAM 5 adet coktan secmeli soru hazirla.
Sorular sadece verilen metindeki bilgilere dayansin.

Ciktiyi SADECE gecerli bir JSON formatinda ver. JSON semasi tam olarak su sekilde olmalidir:
[
  {{
    "question": "Soru metni buraya",
    "options": ["A sikki", "B sikki", "C sikki", "D sikki"],
    "correct_answer": 0,
    "explanation": "Dogru cevabin kisa aciklamasi"
  }}
]
(Not: correct_answer 0 ile 3 arasinda bir indeks olmalidir.)

Metin:
{raw_text[:12000]}
"""

        response = None
        last_error = None
        
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model="models/gemini-3.8-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                if response and response.text:
                    break
            except Exception as err:
                last_error = err
                time.sleep(3)

        if response is None or not response.text:
            raise HTTPException(
                status_code=503,
                detail=f"Gemini Hatasi: {last_error}",
            )

        quiz_data = json.loads(response.text)
        return {"questions": quiz_data}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))