from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import spacy
import fitz
import numpy as np
from sentence_transformers import SentenceTransformer, util
import shutil
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

load_dotenv()
app = FastAPI()
nlp = spacy.load("en_core_web_sm")
model = SentenceTransformer('all-MiniLM-L6-v2')
UPLOAD_DIR = "uploaded_resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, unique=True)
    text = Column(Text, nullable=False)
    match_percentage = Column(Float)
    job_matches = relationship("JobMatch", back_populates="resume", cascade="all, delete-orphan")

class JobMatch(Base):
    __tablename__ = "job_matches"
    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    job_description = Column(Text, nullable=False)
    match_percentage = Column(Float, nullable=False)
    resume = relationship("Resume", back_populates="job_matches")

Base.metadata.create_all(bind=engine)

def convert_numpy(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    return obj

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
    except Exception as e:
        raise RuntimeError(f"Failed to extract PDF text: {str(e)}")
    return text

@app.post("/upload_resume/")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    overwrite: bool = Form(False)
):
    db = SessionLocal()
    try:
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse(
                content={"error": "Only PDF files are allowed"},
                status_code=415
            )

        existing_resume = db.query(Resume).filter(Resume.filename == file.filename).first()
        if existing_resume and not overwrite:
            return JSONResponse(
                content={"error": f"Resume '{file.filename}' already exists. Set overwrite=True to replace it."},
                status_code=409
            )

        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        text = extract_text_from_pdf(file_path)

        resume_embedding = model.encode(text, convert_to_tensor=True)
        job_embedding = model.encode(job_description, convert_to_tensor=True)
        similarity_score = util.pytorch_cos_sim(resume_embedding, job_embedding).item()
        match_percentage = similarity_score * 100
        if existing_resume:
            existing_resume.text = text
            existing_resume.match_percentage = match_percentage
            db.add(existing_resume)
            db.commit()
            db.refresh(existing_resume)
            resume_record = existing_resume
        else:
            new_resume = Resume(
                filename=file.filename,
                text=text,
                match_percentage=match_percentage
            )
            db.add(new_resume)
            db.commit()
            db.refresh(new_resume)
            resume_record = new_resume
        job_match = JobMatch(
            resume_id=resume_record.id,
            job_description=job_description,
            match_percentage=match_percentage
        )
        db.add(job_match)
        db.commit()

        response_data = {
            "similarity_score": convert_numpy(similarity_score),
            "match_percentage": convert_numpy(match_percentage),
            "resume_text": text[:500] + "..."  # snippet of extracted text
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()

@app.get("/uploads/")
async def get_uploads(
    filename: str = "",
    job_description: str = "",
    min_match: float = 0.0,
    max_match: float = 100.0
):
    """
    Returns a list of uploads by joining the resumes and job_matches tables.
    Supports filtering by filename, job description, and match percentage range.
    """
    db = SessionLocal()
    try:
        query = db.query(Resume, JobMatch).join(JobMatch, Resume.id == JobMatch.resume_id)
        if filename:
            query = query.filter(Resume.filename.ilike(f"%{filename}%"))
        if job_description:
            query = query.filter(JobMatch.job_description.ilike(f"%{job_description}%"))
        query = query.filter(JobMatch.match_percentage >= min_match, JobMatch.match_percentage <= max_match)
        results = query.all()

        uploads = []
        for resume, job in results:
            uploads.append({
                "filename": resume.filename,
                "job_description": job.job_description,
                "match_percentage": job.match_percentage,
                "resume_snippet": resume.text[:300] + "..."
            })
        return {"uploads": uploads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
