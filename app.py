import os
import re
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def upload_to_gemini(path, mime_type=None):
    """Uploads the file to Gemini and returns the file object."""
    file = genai.upload_file(path, mime_type=mime_type)
    return file

def get_html(text: str) -> str:
    """Convert plain text to formatted HTML."""
    def handle_links(line):
        link_pattern = re.compile(r'\[(.*?)\]\((.*?)\)')
        line = link_pattern.sub(r'<a href="\2">\1</a>', line)
        url_pattern = re.compile(r'(http[s]?://[^\s]+)')
        line = url_pattern.sub(r'<a href="\1">\1</a>', line)
        email_pattern = re.compile(r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)')
        line = email_pattern.sub(r'<a href="mailto:\1">\1</a>', line)
        return line

    def escape_html(text):
        return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#039;"))

    lines = text.split('\n')
    html_output = """<div style="max-width: 1000px; padding: 15px; margin: 0 auto; display: flex; flex-direction: column;">"""
    list_open = False

    for line in lines:
        line = line.strip()
        if not line:
            html_output += '<p></p>'
            continue

        if line.startswith("# "):
            html_output += f'<h2>{escape_html(line[2:])}</h2>'
        elif line.startswith("## "):
            html_output += f'<h3>{escape_html(line[3:])}</h3>'
        elif line.startswith("### "):
            html_output += f'<h4>{escape_html(line[4:])}</h4>'
        elif line.startswith("* "):
            if not list_open:
                html_output += '<ul>'
                list_open = True
            html_output += f'<li>{escape_html(line[2:])}</li>'
        else:
            if list_open:
                html_output += '</ul>'
                list_open = False
            line = handle_links(escape_html(line))
            html_output += f'<p>{line}</p>'

    if list_open:
        html_output += '</ul>'
    html_output += '</div>'
    return html_output

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    
    num_people = request.form.get("num_people", "4")
    
    try:
        uploaded_file = upload_to_gemini(filepath, mime_type=file.mimetype)
        
        # Generate Gemini Response
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            [
                uploaded_file,  # Image File
                f"Identify this food item and provide a detailed recipe for {num_people} people, including ingredients, preparation steps, cost estimation, calorie count, and an overall summary.",  # Prompt
            ]
        )

        # Convert response text to formatted HTML
        formatted_html = get_html(response.text)

        return jsonify({
            "message": "File uploaded and analyzed successfully",
            "file_uri": uploaded_file.uri,
            "bot_response_html": formatted_html  # ✅ HTML Response
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)