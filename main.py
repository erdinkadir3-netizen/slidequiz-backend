import os
import json
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import pypdf
from docx import Document
from pptx import Presentation
import io

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
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    elif ext == "docx":
        doc = Document(io.BytesIO(file_bytes))
        for p in doc.paragraphs:
            text += p.text + "\n"
    elif ext == "pptx":
        prs = Presentation(io.BytesIO(file_bytes))
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
    elif ext == "txt":
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
            raise HTTPException(status_code=400, detail="Dosyadan metin okunamadı.")
            
        prompt = f"""
Sen bir eğitim uzmanısın. Aşağıda sana verilen ders notlarından veya slayt içeriğinden TAM 5 adet çoktan seçmeli soru hazırla.
Sorular sadece verilen metindeki bilgilere dayansın.

Çıktıyı SADECE geçerli bir JSON formatında ver. JSON şeması tam olarak şu şekilde olmalıdır:
[
  {{
    "question": "Soru metni buraya",
    "options": ["A şıkkı", "B şıkkı", "C şıkkı", "D şıkkı"],
    "correct_answer": 0,
    "explanation": "Doğru cevabın kısa açıklaması"
  }}
]
(Not: correct_answer 0 ile 3 arasında bir indeks olmalıdır.)

Metin:
{raw_text[:12000]}
"""

        response = None
        last_error = None
        
        # 503 yogunluk hatasina karsi 4 kere tekrar deneme dongusu
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
                time.sleep(3)  # 3 saniye bekle ve tekrar dene

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
