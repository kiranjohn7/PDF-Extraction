import re
from io import BytesIO

import pytesseract
from flask import Flask, jsonify, request, send_from_directory
from pdf2image import convert_from_bytes
from pypdf import PdfReader


def extract_name(text):
    ignored_words = [
        "resume",
        "email",
        "phone",
        "mobile",
        "contact",
        "profile",
        "summary",
        "experience",
        "education",
        "skills",
        "linkedin",
        "address"
    ]

    for line in text.splitlines()[:20]:
        cleaned_line = re.sub(r"[^A-Za-z\s'-]", " ", line)
        cleaned_line = re.sub(r"\s+", " ", cleaned_line).strip()

        if not cleaned_line:
            continue

        if any(word in cleaned_line.lower() for word in ignored_words):
            continue

        words = cleaned_line.split()

        if 2 <= len(words) <= 4 and all(
            word[0].isupper() or word.isupper()
            for word in words
            if word
        ):
            return " ".join(words)

    return None


def process_pdf(pdf_file):
    pdf_bytes = pdf_file.read()

    pdf_reader = PdfReader(BytesIO(pdf_bytes))
    full_text = ""

    for page in pdf_reader.pages:
        page_text = page.extract_text()

        if page_text:
            full_text += page_text + "\n"

    extraction_method = "PDF text extraction"

    if not full_text.strip():
        images = convert_from_bytes(pdf_bytes, dpi=200)
        full_text = ""

        for image in images:
            full_text += pytesseract.image_to_string(image) + "\n"

        extraction_method = "OCR"

    name = extract_name(full_text)

    email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    emails = re.findall(email_pattern, full_text)
    email = emails[0] if emails else None

    phone_patterns = [
    r"\+\d{1,3}[\s.-]?\d{6,14}",
    r"\b[6-9]\d{9}\b",
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,5}[\s.-]\d{3,5}"
    ]

    phone = None

    for pattern in phone_patterns:
        phones = re.findall(pattern, full_text)

        if phones:
            phone = phones[0]
            break

    return {
        "file_name": pdf_file.filename,
        "extraction_method": extraction_method,
        "text": full_text,
        "name": name,
        "email": email,
        "phone": phone
    }


app = Flask(__name__)


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    pdf_files = request.files.getlist("pdfFiles")

    if not pdf_files or pdf_files[0].filename == "":
        return jsonify({"error": "Please upload at least one PDF file"}), 400

    results = []

    for pdf_file in pdf_files:
        if not pdf_file.filename.lower().endswith(".pdf"):
            results.append({
                "file_name": pdf_file.filename,
                "error": "Only PDF files are allowed"
            })
            continue

        try:
            result = process_pdf(pdf_file)
            results.append(result)

        except Exception as error:  # noqa: BLE001
            results.append({
                "file_name": pdf_file.filename,
                "error": "Could not process this PDF: " + str(error)
            })

    return jsonify({
        "message": "PDF batch processed successfully",
        "results": results
    })

@app.route("/style.css")
def styles():
    return send_from_directory(".", "style.css")


if __name__ == "__main__":
    app.run(debug=True)