"""
Single-file Flask webapp: Bionic Reading + Soft Text for uploaded PDFs

Features:
- Upload a PDF (server extracts text using PyMuPDF / fitz)
- Displays text in-browser
- Client-side toggles for: Bionic Reading (intensity slider), Soft Text (contrast/opacity), Font size, Line height
- All bionic processing is done client-side in JavaScript for instant toggles

How to run:
1. python -m venv venv
2. source venv/bin/activate   # or venv\Scripts\activate on Windows
3. pip install Flask PyMuPDF
4. python Untitled-1.py
5. Open http://127.0.0.1:5000
 s
Notes:
- PyMuPDF (pip install pymupdf) extracts text robustly. For complex PDFs with heavy layout, extraction may be imperfect.
- This is a minimal proof-of-concept single-file app. For production, add file size limits, authentication, HTTPS, and storage cleanup.
"""
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, flash
import fitz  # PyMuPDF
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'replace_this_with_a_secure_random_key'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Bionic Reader — PDF to Fast Text</title>
  <style>
    :root{
      --base-font: Arial, system-ui, -apple-system, "Segoe UI", Roboto;
      --soft-color: #6b7280; /* gray-500 */
      --bg: #fff;
      --text: #111827;
    }
    body{font-family:var(--base-font);background:var(--bg);color:var(--text);margin:0;padding:0}
    header{padding:1rem;border-bottom:1px solid #eee;display:flex;align-items:center;gap:1rem}
    main{display:flex;gap:1rem;padding:1rem}
    .controls{width:320px;flex:0 0 320px}
    .viewer{flex:1;max-width:900px}
    .text-area{padding:1rem;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.03);min-height:60vh;overflow:auto}
    .word {white-space:pre-wrap}
    .bionic-strong{font-weight:700}
    label{display:block;margin-top:0.75rem}
    input[type=range]{width:100%}
    .muted{color:#6b7280;font-size:0.9rem}
    .file-list{font-size:0.9rem}
    footer{padding:1rem;border-top:1px solid #eee;text-align:center;color:#6b7280}
  </style>
</head>
<body>
  <header>
    <h2>Bionic Reader — PDF to Fast Text</h2>
    <div class="muted">Upload a PDF, then toggle Bionic Reading & Soft Text</div>
  </header>
  <main>
    <aside class="controls">
      <form id="uploadForm" method="post" enctype="multipart/form-data" action="/upload">
        <label>Choose PDF to upload</label>
        <input type="file" name="file" accept="application/pdf" required>
        <div style="margin-top:.75rem">
          <button type="submit">Upload & Extract</button>
        </div>
      </form>

      <div style="margin-top:1rem">
        <label>Font size <span id="fontSizeLabel">16</span>px</label>
        <input id="fontSize" type="range" min="12" max="28" value="16">

        <label>Line height <span id="lineHeightLabel">1.5</span></label>
        <input id="lineHeight" type="range" min="12" max="28" value="24" oninput="updateLineHeightLabel()">

        <label>Bionic intensity <span id="bionicLabel">35%</span></label>
        <input id="bionicIntensity" type="range" min="10" max="60" value="35">

        <label><input id="softToggle" type="checkbox"> Enable Soft Text (lower contrast)</label>

        <div class="muted" style="margin-top:.5rem">Tip: Use the sliders while reading — all rendering is client-side for instant response.</div>
      </div>

      <div style="margin-top:1rem">
        <div class="file-list">Uploaded file: <strong id="uploadedName">None</strong></div>
      </div>

    </aside>

    <section class="viewer">
      <div id="textContainer" class="text-area">Upload a PDF to extract text here.</div>
    </section>
  </main>
  <footer>Made with PyMuPDF + Flask — minimal demo</footer>

<script>
// Utilities
function escapeHtml(s){
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
           .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// Bionic algorithm: bold the first ceil(len * ratio) characters of each word
function bionicWrapText(text, ratioPercent){
  const ratio = Math.min(Math.max(ratioPercent/100, 0.05), 0.9);
  // Split keeping whitespace
  return text.split(/(\s+)/).map(token => {
    if (/^\s+$/.test(token)) return token;
    // For punctuation-heavy tokens, separate letters
    const m = token.match(/^([\p{L}\p{N}']+)(.*)$/u);
    if (!m) return escapeHtml(token);
    const core = m[1];
    const rest = m[2] || '';
    const n = core.length;
    const k = Math.max(1, Math.ceil(n * ratio));
    const first = escapeHtml(core.slice(0,k));
    const last = escapeHtml(core.slice(k));
    return `<span class="word"><span class="bionic-strong">${first}</span>${last}${escapeHtml(rest)}</span>`;
  }).join('');
}

function applyStyles(){
  const textContainer = document.getElementById('textContainer');
  const fontSize = document.getElementById('fontSize').value;
  const lineHeightPx = document.getElementById('lineHeight').value;
  textContainer.style.fontSize = fontSize + 'px';
  textContainer.style.lineHeight = (lineHeightPx / fontSize).toFixed(2);

  const soft = document.getElementById('softToggle').checked;
  if(soft){
    textContainer.style.color = 'var(--soft-color)';
    textContainer.style.opacity = '0.95';
    textContainer.style.letterSpacing = '0.2px';
  } else {
    textContainer.style.color = 'var(--text)';
    textContainer.style.opacity = '1';
    textContainer.style.letterSpacing = '0';
  }

  document.getElementById('fontSizeLabel').innerText = fontSize;
  // derived line-height label
  document.getElementById('lineHeightLabel').innerText = (lineHeightPx / 16).toFixed(2);
}

function updateLineHeightLabel(){
  const lineHeightPx = document.getElementById('lineHeight').value;
  document.getElementById('lineHeightLabel').innerText = (lineHeightPx / 16).toFixed(2);
}

// Take raw text in data-raw attribute and render bionic-wrapped HTML
function renderText(){
  const raw = window._pdfRawText || '';
  const intensity = parseInt(document.getElementById('bionicIntensity').value,10);
  document.getElementById('bionicLabel').innerText = intensity + '%';
  const html = bionicWrapText(escapeHtml(raw), intensity);
  document.getElementById('textContainer').innerHTML = html;
  applyStyles();
}

// Controls
['fontSize','lineHeight','bionicIntensity','softToggle'].forEach(id=>{
  const el = document.getElementById(id);
  if(!el) return;
  el.addEventListener('input', ()=>{
    renderText();
  });
});

// When page loads, if server embedded text is present, wire it
window.addEventListener('DOMContentLoaded', ()=>{
  const embedded = document.getElementById('embeddedRaw');
  if(embedded){
    window._pdfRawText = embedded.textContent || '';
    const fname = embedded.getAttribute('data-fname') || 'Uploaded PDF';
    document.getElementById('uploadedName').innerText = fname;
    renderText();
  }
});
</script>

<!-- Server may render raw text into this element (hidden) to avoid extra fetch -->
{% if raw_text %}
<pre id="embeddedRaw" data-fname="{{ filename }}" style="display:none">{{ raw_text }}</pre>
{% endif %}

</body>
</html>
"""


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return render_template_string(TEMPLATE, raw_text=None, filename='')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        fname = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(path)
        # Extract text with PyMuPDF
        try:
            doc = fitz.open(path)
            all_text = []
            for page in doc:
                txt = page.get_text("text")
                if txt:
                    all_text.append(txt)
            raw = "\n\n".join(all_text)
        except Exception as e:
            raw = f"[Error extracting text: {e}]"
        return render_template_string(TEMPLATE, raw_text=raw, filename=fname)
    else:
        flash('Invalid file type')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
