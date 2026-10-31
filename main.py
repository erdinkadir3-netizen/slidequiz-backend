import io
import json
import re
import time
import traceback
from typing import List
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pypdf import PdfReader
from pptx import Presentation
from pydantic import BaseModel

import os

API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6ImNbT1sy81v0CLPsQXc_XJ-q8aNjnVkqIez_iUFrY8rA")
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(api_version="v1")
)

app = FastAPI(title="SlideQuiz API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str
    options: List[str]
    answer: str


class QuizResponse(BaseModel):
    total_questions: int
    questions: List[Question]


def extract_text_from_file(filename: str, content: bytes) -> str:
    text = ""
    file_stream = io.BytesIO(content)
    lower_name = (filename or "").lower()

    # 1. Metin Belgesi (.txt)
    if lower_name.endswith(".txt") or not lower_name:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception:
                text = ""

    # 2. Word Belgesi (.docx)
    if not text and (lower_name.endswith(".docx") or not lower_name):
        try:
            from docx import Document
            doc = Document(file_stream)
            extracted = "\n".join([p.text for p in doc.paragraphs if p.text])
            if extracted.strip():
                return extracted.strip()
            file_stream.seek(0)
        except Exception:
            file_stream.seek(0)

    # 3. PDF (.pdf)
    if not text and (lower_name.endswith(".pdf") or not lower_name):
        try:
            reader = PdfReader(file_stream)
            extracted = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted += t + "\n"
            if extracted.strip():
                return extracted.strip()
            file_stream.seek(0)
        except Exception:
            file_stream.seek(0)

    # 4. PowerPoint (.pptx, .ppt)
    if not text and (lower_name.endswith((".pptx", ".ppt")) or not lower_name):
        try:
            prs = Presentation(file_stream)
            extracted = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        extracted += shape.text + "\n"
            if extracted.strip():
                return extracted.strip()
        except Exception:
            pass

    return text.strip()


@app.get("/")
def home():
    return {"status": "online", "project": "SlideQuiz API"}


@app.post("/generate-quiz", response_model=QuizResponse)
async def generate_quiz(
    file: UploadFile = File(...),
    question_count: int = Form(default=5),
):
    try:
        content = await file.read()
        extracted_text = extract_text_from_file(file.filename or "", content)

        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Dosya boş veya içeriğindeki metinler okunamadı."
            )

        prompt = f"""
        Aşağıdaki ders materyali içeriğine dayanarak tam olarak {question_count} adet çoktan seçmeli sınav sorusu hazırla.
        Her sorunun 4 seçeneği ve 1 kesin doğru cevabı olmalıdır.

        ÇOK ÖNEMLİ: JSON anahtarlarını tam olarak şu İngilizce formatta döndür:
        [
          {{
            "question": "Soru metni",
            "options": ["A", "B", "C", "D"],
            "answer": "Doğru seçenek"
          }}
        ]

        İçerik:
        {extracted_text[:6000]}
        """

        response = None
        last_error = None

        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
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
                detail=f"Sunucu meşgul, lütfen birazdan tekrar deneyin: {str(last_error)}"
            )

        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        parsed_data = json.loads(raw_text)

        if isinstance(parsed_data, dict):
            if "questions" in parsed_data:
                raw_list = parsed_data["questions"]
            elif "sorular" in parsed_data:
                raw_list = parsed_data["sorular"]
            else:
                raw_list = [parsed_data]
        elif isinstance(parsed_data, list):
            raw_list = parsed_data
        else:
            raw_list = []

        normalized_questions: List[Question] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue

            q_text = item.get("question") or item.get("soru") or ""
            opts = item.get("options") or item.get("secenekler") or item.get("seçenekler") or []
            ans = item.get("answer") or item.get("cevap") or item.get("dogru_cevap") or ""

            if isinstance(opts, dict):
                opts = list(opts.values())

            normalized_questions.append(
                Question(
                    question=str(q_text),
                    options=[str(o) for o in opts],
                    answer=str(ans)
                )
            )

        return QuizResponse(
            total_questions=len(normalized_questions),
            questions=normalized_questions
        )

    except HTTPException:
        raise
    except Exception as e:
        print("\n--- HATA AYRINTISI BAŞLANGICI ---")
        traceback.print_exc()
        print("--- HATA AYRINTISI SONU ---\n")
        raise HTTPException(status_code=500, detail=str(e))