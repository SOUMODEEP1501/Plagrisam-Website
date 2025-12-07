from flask import Flask, render_template, request, flash, redirect, url_for, session
import os
import PyPDF2
import re
import html
import chardet
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from database import create_connection, add_keyword, get_all_keywords, search_keywords
from scipy.sparse import diags

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = "uploaded_documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return None
    return text.strip()

def extract_text_from_docx(docx_path):
    # First try using python-docx if available (preferred)
    try:
        import docx
        try:
            doc = docx.Document(docx_path)
            return "\n".join([para.text for para in doc.paragraphs]).strip()
        except Exception as e:
            # if python-docx fails to read the file, fall back to zip parsing
            print(f"Error reading DOCX with python-docx: {e}")
            pass
    except Exception as e:
        # python-docx not installed — we'll try a pure-Python fallback
        print(f"python-docx not available: {e}")
        pass

    # Fallback: extract text by reading the DOCX (ZIP) and parsing word/document.xml
    try:
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(docx_path) as z:
            with z.open('word/document.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                # WordprocessingML namespace
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                paragraphs = []
                for para in root.findall('.//w:p', ns):
                    texts = [t.text for t in para.findall('.//w:t', ns) if t.text]
                    if texts:
                        paragraphs.append(''.join(texts))
                return "\n".join(paragraphs).strip()
    except Exception as e:
        print(f"Error extracting DOCX from ZIP: {e}")
        return None

def extract_text_from_txt(file_path):
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read()
            detected_encoding = chardet.detect(raw_data)['encoding']
        with open(file_path, "r", encoding=detected_encoding or "utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error extracting TXT: {e}")
        return None

def preprocess_text(text):
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def highlight_text(text, matched_phrases):
    text = html.escape(text)
    for phrase, _ in sorted(matched_phrases, key=lambda x: len(x[0]), reverse=True):
        text = re.sub(r'\b' + re.escape(phrase.lower()) + r'\b', 
                      f'<mark style="background-color: yellow; font-weight: bold;">{phrase}</mark>', 
                      text, flags=re.IGNORECASE)
    return text

def check_plagiarism(texts, use_keywords=False):
    cleaned_texts = [preprocess_text(text) for text in texts]
    
    if use_keywords:
        conn = create_connection()
        keyword_weights = {}
        found_keywords = []
        
        # Search for keywords in the single text
        found_keywords = search_keywords(conn, texts[0])
        
        if not found_keywords:
            flash("⚠ No keywords from database found in the text.", "warning")
            return [], texts
        
        keyword_weights = {kw.lower(): weight for kw, weight in found_keywords}
        
        # Create a custom vocabulary with weights
        try:
            vectorizer = TfidfVectorizer(analyzer='word', ngram_range=(1, 3), 
                                      stop_words=None, norm='l2',
                                      vocabulary=keyword_weights.keys())
            tfidf_matrix = vectorizer.fit_transform(cleaned_texts)

            # Apply keyword weights to the TF-IDF matrix by multiplying columns
            # using a sparse diagonal matrix (avoids slice-assignment on sparse matrices)
            feature_names = vectorizer.get_feature_names_out()
            weights = [keyword_weights.get(f.lower(), 1.0) for f in feature_names]
            weight_diag = diags(weights)
            tfidf_matrix = tfidf_matrix.dot(weight_diag)

            # For single file, we'll compare against itself to show keyword matches
            similarity = 100  # Since we're just showing keyword matches in the file
            matched_phrases = found_keywords
            highlighted_text = highlight_text(texts[0], matched_phrases)
            
            return [{
                "doc1": 1,
                "doc2": 1,
                "similarity": 100,
                "alert": '<span style="color: blue; font-weight: bold;">🔍 Keyword Matches Found</span>',
                "highlighted_doc1": highlighted_text,
                "highlighted_doc2": highlighted_text
            }], [highlighted_text]
            
        except ValueError as e:
            flash(f"⚠ Error in keyword-based detection: {str(e)}", "warning")
            return [], texts
    
    # Standard detection without keywords
    vectorizer = TfidfVectorizer(analyzer='word', ngram_range=(1, 3), 
                               stop_words=None, norm='l2')
    tfidf_matrix = vectorizer.fit_transform(cleaned_texts)
    
    similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
    results = []
    highlighted_texts = texts.copy()

    for i in range(len(cleaned_texts)):
        for j in range(i + 1, len(cleaned_texts)):
            similarity = round(similarity_matrix[i][j] * 100, 2)
            if similarity > 50:
                alert = '<span style="color: red; font-weight: bold;">⚠ High Plagiarism Alert!</span>'
            elif similarity >= 20:
                alert = '<span style="color: orange; font-weight: bold;">⚠ Moderate Plagiarism Alert!</span>'
            else:
                alert = '<span style="color: green; font-weight: bold;">✅ No Plagiarism Detected.</span>'

            feature_names = vectorizer.get_feature_names_out()
            matched_phrases = [(phrase, 1.0) for phrase in feature_names 
                             if phrase.lower() in texts[i].lower() 
                             and phrase.lower() in texts[j].lower()]
            highlighted_texts[i] = highlight_text(texts[i], matched_phrases)
            highlighted_texts[j] = highlight_text(texts[j], matched_phrases)

            results.append({
                "doc1": i + 1,
                "doc2": j + 1,
                "similarity": similarity,
                "alert": alert,
                "highlighted_doc1": highlighted_texts[i],
                "highlighted_doc2": highlighted_texts[j]
            })
    return results, highlighted_texts

@app.route("/", methods=["GET", "POST"])
def index():
    uploaded_files = []
    extracted_texts = []
    file_names = []
    input_mode = "files"  # Default to file upload mode

    # If results were stored in session via PRG, restore them and clear session.
    stored_results = session.pop('results', None)
    if stored_results is not None:
        uploaded_files = session.pop('uploaded_files', []) or []
        input_mode = session.pop('input_mode', 'files') or 'files'
        text1 = session.pop('text1', '')
        text2 = session.pop('text2', '')
        return render_template("index.html", uploaded_files=uploaded_files, results=stored_results, input_mode=input_mode, text1=text1, text2=text2)

    # If this is a fresh GET (no stored results), clear any leftover uploaded files
    if request.method == 'GET':
        try:
            for fname in os.listdir(UPLOAD_FOLDER):
                path = os.path.join(UPLOAD_FOLDER, fname)
                if os.path.isfile(path):
                    os.remove(path)
        except Exception as e:
            print(f"Error cleaning uploaded files: {e}")

    if request.method == "POST":
        input_mode = request.form.get("input_mode", "files")
        use_keywords = request.form.get("use_keywords") == "on"
        
        if input_mode == "files":
            files = request.files.getlist("files")
            
            if use_keywords:
                # Keyword mode - only need one file
                if len(files) != 1 or not files[0].filename:
                    flash("⚠ Please upload exactly one file for keyword-based checking.", "danger")
                    return render_template("index.html", uploaded_files=[], results=[])
            else:
                # Standard mode - need at least two files
                if len(files) < 2:
                    flash("⚠ Please upload at least two files for standard plagiarism checking.", "danger")
                    return render_template("index.html", uploaded_files=[], results=[])
            
            for file in files:
                if file.filename:
                    if not allowed_file(file.filename):
                        flash(f"⚠ Unsupported file format: '{file.filename}'. Allowed types are PDF, DOCX, TXT.", "danger")
                        continue

                    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                    file.save(file_path)
                    file_names.append(file.filename)

                    if file.filename.endswith(".pdf"):
                        extracted_text = extract_text_from_pdf(file_path)
                    elif file.filename.endswith(".docx"):
                        extracted_text = extract_text_from_docx(file_path)
                    elif file.filename.endswith(".txt"):
                        extracted_text = extract_text_from_txt(file_path)
                    else:
                        extracted_text = None

                    if extracted_text is None:
                        flash(f"⚠ The file '{file.filename}' is corrupt or unreadable!", "danger")
                    elif not extracted_text.strip():
                        flash(f"⚠ The file '{file.filename}' is empty!", "danger")
                    else:
                        extracted_texts.append(extracted_text)
            
            if use_keywords:
                if len(extracted_texts) != 1:
                    flash("⚠ Unable to process the uploaded file for keyword checking.", "danger")
                    return render_template("index.html", uploaded_files=file_names, results=[])
            else:
                if len(extracted_texts) < 2:
                    flash("⚠ Not enough valid files to perform plagiarism checking.", "danger")
                    return render_template("index.html", uploaded_files=file_names, results=[])
            
        elif input_mode == "text":
            text1 = request.form.get("text1", "").strip()
            text2 = request.form.get("text2", "").strip()
            
            if not text1 or not text2:
                flash("⚠ Please provide text in both input boxes.", "danger")
                return render_template("index.html", uploaded_files=[], results=[])
            
            extracted_texts = [text1, text2]
            file_names = ["Text Input 1", "Text Input 2"]
        
        results, _ = check_plagiarism(extracted_texts, use_keywords)

        # Clean up saved uploaded files so the site appears fresh on reload
        for fname in file_names:
            try:
                path = os.path.join(UPLOAD_FOLDER, fname)
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"Error removing file {fname}: {e}")

        # Store results in session and redirect (Post/Redirect/Get) so reload doesn't re-post
        session['results'] = results
        session['uploaded_files'] = file_names
        session['input_mode'] = input_mode
        session['text1'] = request.form.get("text1", "")
        session['text2'] = request.form.get("text2", "")
        flash("Analysis completed successfully!", "success")
        return redirect(url_for('index'))
    
    return render_template("index.html", 
                         uploaded_files=[], 
                         results=[],
                         input_mode=input_mode)

@app.route("/keywords", methods=["GET", "POST"])
def manage_keywords():
    conn = create_connection()
    try:
        if request.method == "POST":
            keyword = request.form.get("keyword", "").strip()
            weight = float(request.form.get("weight", 1.0))
            if keyword:
                add_keyword(conn, keyword, weight)
                flash(f"Keyword '{keyword}' added successfully!", "success")
        
        keywords = get_all_keywords(conn)
        return render_template("keywords.html", keywords=keywords)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(debug=True)