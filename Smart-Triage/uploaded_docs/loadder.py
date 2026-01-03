from pypdf import PdfReader
from docx import Document

def load_pdf(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def load_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def load_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_document(path):
    if path.endswith(".pdf"):
        return load_pdf(path)
    if path.endswith(".docx"):
        return load_docx(path)
    if path.endswith(".txt"):
        return load_txt(path)
    raise ValueError("Unsupported file type")
