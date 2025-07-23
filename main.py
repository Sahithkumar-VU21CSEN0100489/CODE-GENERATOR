from flask import Flask, render_template_string, request, redirect, url_for, session, send_file, jsonify
import webbrowser
import threading
import os
from agents import run_prompt_engineer, run_developer, run_code_reviewer
import re
from flask_session import Session
import tempfile
import subprocess
import base64
from PIL import Image
from pyvirtualdisplay import Display
import io
import zipfile

app = Flask(__name__)
app.secret_key = '9f8c2e4b1a2d3c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Add a styled title to all main HTML templates
# Remove global HTML_TITLE injection

HTML_TASK = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Input</title>
    <style>body { font-family: Arial, sans-serif; background: #f4f4f4; } .container { max-width: 400px; margin: 100px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); } .title { text-align:center; font-size:2.2rem; font-weight:bold; letter-spacing:2px; color:#2563eb; margin-bottom:18px; } h2 { text-align: center; } input[type="text"] { width: 100%; padding: 10px; margin: 10px 0; border-radius: 4px; border: 1px solid #ccc; } button { width: 100%; padding: 10px; background: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; } button:hover { background: #0056b3; }</style>
</head>
<body>
    <div class="container">
        <div class="title">CODE-GENERATOR</div>
        <h2>Enter Your Task</h2>
        <form method="post">
            <input type="text" name="task" placeholder="Describe your task..." required />
            <button type="submit">Submit</button>
        </form>
    </div>
</body>
</html>
'''

HTML_PROMPT = '''
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Prompt Approval</title><style>
body { font-family: Arial, sans-serif; background: #f4f4f4; }
.container { max-width: 700px; margin: 60px auto; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.12); }
.title { text-align:center; font-size:2.2rem; font-weight:bold; letter-spacing:2px; color:#2563eb; margin-bottom:18px; }
h2 { text-align: center; }
.scroll-box { background: #f8f8f8; padding: 18px; border-radius: 6px; max-width: 100%; max-height: 350px; overflow-x: auto; overflow-y: auto; font-size: 1rem; white-space: pre; margin-bottom: 20px; border: 1px solid #e0e0e0; }
.actions { display: flex; gap: 10px; justify-content: center; margin-top: 20px; }
button { padding: 10px 28px; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
.approve { background: #28a745; color: #fff; }
.reject { background: #dc3545; color: #fff; }
a { color: #007bff; text-decoration: none; }
a:hover { text-decoration: underline; }
</style></head>
<body>
    <div class="container">
        <div class="title">CODE-GENERATOR</div>
        <h2>Generated Prompt</h2>
        <div class="scroll-box">{{ prompt }}</div>
        <form method="post" class="actions">
            <button name="action" value="approve" class="approve">Approve</button>
            <button name="action" value="reject" class="reject">Reject</button>
        </form>
        <p style="text-align:center; margin-top:20px;"><a href="/">Start Over</a></p>
    </div>
</body>
</html>
'''

def parse_files(output):
    # Parse output like ---file:<filename>---<content>
    pattern = r"---file:(.*?)---\n([\s\S]*?)(?=(---file:|$))"
    matches = re.findall(pattern, output)
    files = []
    for match in matches:
        filename = match[0].strip()
        content = match[1].strip()
        files.append({'filename': filename, 'content': content})
    return files

def get_language_from_filename(filename):
    ext = filename.lower().split('.')[-1]
    if ext == 'py':
        return 'python'
    elif ext == 'js':
        return 'javascript'
    elif ext == 'html':
        return 'markup'
    elif ext == 'css':
        return 'css'
    elif ext == 'json':
        return 'json'
    elif ext == 'md':
        return 'markdown'
    elif ext == 'sh':
        return 'bash'
    elif ext == 'env' or ext == 'txt':
        return 'none'
    else:
        return 'none'

def is_tkinter_code(code):
    return 'import tkinter' in code or 'from tkinter' in code

@app.route('/preview/<int:file_index>', methods=['POST'])
def preview_tkinter(file_index):
    print(f"[DEBUG] Preview requested for file index: {file_index}")
    files = parse_files(session['code'])
    print(f"[DEBUG] Parsed {len(files)} files from session.")
    if file_index < 0 or file_index >= len(files):
        print("[DEBUG] Invalid file index.")
        return jsonify({'error': 'Invalid file index'}), 400
    file = files[file_index]
    code = file['content']
    print(f"[DEBUG] Filename: {file['filename']}")
    if not (file['filename'].endswith('.py') and is_tkinter_code(code)):
        print("[DEBUG] Not a Tkinter .py file.")
        return jsonify({'error': 'Preview only supported for Tkinter .py files.'}), 400
    try:
        print("[DEBUG] Calling run_preview_agent...")
        img_bytes = run_preview_agent(code)
        if img_bytes is None:
            print("[DEBUG] run_preview_agent returned None.")
            return jsonify({'error': 'Preview failed.'}), 500
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        print("[DEBUG] Preview image generated successfully.")
        return jsonify({'image': img_b64})
    except Exception as e:
        print(f"[DEBUG] Exception in preview_tkinter: {e}")
        return jsonify({'error': f'Preview failed: {e}'}), 500

HTML_CODE_REVIEW = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Generated Code & Review</title>
<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism.min.css" rel="stylesheet" />
<style>
body { font-family: Arial, sans-serif; background: #f4f4f4; }
.container { max-width: 900px; margin: 60px auto; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.12); }
.title { text-align:center; font-size:2.2rem; font-weight:bold; letter-spacing:2px; color:#2563eb; margin-bottom:18px; }
h2 { text-align: center; }
.file-block { margin-bottom: 32px; }
.file-label { font-weight: bold; margin-bottom: 6px; display: block; }
.filename-input { font-size: 1rem; padding: 4px 8px; border-radius: 4px; border: 1px solid #ccc; width: 220px; margin-bottom: 8px; }
.scroll-box { background: #f8f8f8; padding: 0; border-radius: 6px; max-width: 100%; max-height: 350px; overflow-x: auto; overflow-y: auto; font-size: 1rem; margin-bottom: 10px; border: 1px solid #e0e0e0; }
pre { margin: 0; padding: 18px; background: none; border-radius: 6px; }
.btn-row { display: flex; gap: 10px; margin-bottom: 10px; }
button { padding: 8px 18px; border: none; border-radius: 4px; background: #007bff; color: #fff; cursor: pointer; font-size: 1rem; }
button:hover { background: #0056b3; }
.review { margin-top: 30px; background: #e9ecef; padding: 18px; border-radius: 6px; }
.preview-img { display: block; margin: 18px auto 0 auto; max-width: 100%; border: 1px solid #ccc; border-radius: 8px; }
</style>
</head>
<body>
    <div class="container">
        <div class="title">CODE-GENERATOR</div>
        <div style="text-align:center; margin-bottom:24px;"><a href="/download_zip"><button>Download All as ZIP</button></a></div>
        <div style="text-align:center; margin-bottom:24px;"><button id="preview-project-btn">Preview Project</button></div>
        <h2>Generated Files</h2>
        {% for file in files %}
        <div class="file-block">
            <label class="file-label">Filename:</label>
            <input class="filename-input" type="text" value="{{ file.filename }}" id="filename-{{ loop.index0 }}" />
            <div class="btn-row">
                <button onclick="copyToClipboard('content-{{ loop.index0 }}')">Copy</button>
                <button onclick="downloadFile('filename-{{ loop.index0 }}', 'content-{{ loop.index0 }}')">Download</button>
                {% if file.filename.endswith('.py') and file.is_tkinter %}
                <button onclick="previewTkinter({{ loop.index0 }})">Preview</button>
                {% endif %}
                {% if file.filename.endswith(".html") %}
                <button onclick="previewHTML({{ loop.index0 }})">Preview</button>
                {% endif %}
            </div>
            <div class="scroll-box" id="content-{{ loop.index0 }}">
                <pre><code class="language-{{ file.language }}">{{ file.content|e }}</code></pre>
            </div>
            <div id="preview-img-{{ loop.index0 }}"></div>
            <div id="preview-html-{{ loop.index0 }}"></div>
        </div>
        {% endfor %}
        <div class="review">
            <h3>Code Review</h3>
            <div class="scroll-box">{{ review }}</div>
        </div>
    </div>
    <div id="project-preview-modal" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.4); z-index:9999; align-items:center; justify-content:center;">
  <div style="background:#fff; padding:30px; border-radius:10px; max-width:900px; max-height:90vh; overflow:auto; position:relative;">
    <button onclick="document.getElementById('project-preview-modal').style.display='none'" style="position:absolute; top:10px; right:10px;">Close</button>
    <div id="project-preview-content"></div>
  </div>
</div>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-markup.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-css.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-json.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-bash.min.js"></script>
    <script>
    function copyToClipboard(contentId) {
        var text = document.getElementById(contentId).innerText;
        navigator.clipboard.writeText(text);
    }
    function downloadFile(filenameId, contentId) {
        var filename = document.getElementById(filenameId).value;
        var content = document.getElementById(contentId).innerText;
        var blob = new Blob([content], {type: 'text/plain'});
        var link = document.createElement('a');
        link.href = window.URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    }
    function previewTkinter(fileIndex) {
        var imgDiv = document.getElementById('preview-img-' + fileIndex);
        imgDiv.innerHTML = 'Generating preview...';
        fetch('/preview/' + fileIndex, {method: 'POST'})
            .then(resp => resp.json())
            .then(data => {
                if (data.image) {
                    imgDiv.innerHTML = '<img class="preview-img" src="data:image/png;base64,' + data.image + '" />';
                } else if (data.error) {
                    imgDiv.innerHTML = '<span style="color:red;">' + data.error + '</span>';
                }
            })
            .catch(err => {
                imgDiv.innerHTML = '<span style="color:red;">Preview failed.</span>';
            });
    }
    function previewHTML(fileIndex) {
        var code = document.querySelector('#content-' + fileIndex + ' pre code').innerText;
        var htmlDiv = document.getElementById('preview-html-' + fileIndex);
        htmlDiv.innerHTML = '<iframe style="width:100%;min-height:350px;border:1px solid #ccc;border-radius:8px;margin-top:12px;" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>';
        var iframe = htmlDiv.querySelector('iframe');
        iframe.srcdoc = code;
    }
    document.getElementById('preview-project-btn').onclick = function() {
  var modal = document.getElementById('project-preview-modal');
  var contentDiv = document.getElementById('project-preview-content');
  contentDiv.innerHTML = 'Generating preview...';
  modal.style.display = 'flex';
  fetch('/preview_project', {method: 'POST'})
    .then(resp => resp.json())
    .then(data => {
      if (data.type === 'html') {
        contentDiv.innerHTML = '<iframe style="width:100%;min-height:500px;border:1px solid #ccc;border-radius:8px;" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>';
        var iframe = contentDiv.querySelector('iframe');
        iframe.srcdoc = data.content;
      } else if (data.type === 'image') {
        contentDiv.innerHTML = '<img style="max-width:100%;border:1px solid #ccc;border-radius:8px;" src="data:image/png;base64,' + data.content + '" />';
      } else {
        contentDiv.innerHTML = '<span style="color:red;">' + data.content + '</span>';
      }
    })
    .catch(err => {
      contentDiv.innerHTML = '<span style="color:red;">Preview failed.</span>';
    });
};
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def task_input():
    if request.method == 'POST':
        session.clear()
        session['task'] = request.form['task']
        # Generate prompt
        prompt = run_prompt_engineer(session['task'])
        session['prompt'] = prompt
        return redirect(url_for('prompt_approval'))
    return render_template_string(HTML_TASK)

@app.route('/prompt', methods=['GET', 'POST'])
def prompt_approval():
    if 'prompt' not in session or 'task' not in session:
        return redirect(url_for('task_input'))
    if request.method == 'POST':
        action = request.form['action']
        if action == 'approve':
            # Generate code and review
            code = run_developer(session['prompt'])
            session['code'] = code
            review = run_code_reviewer(code)
            session['review'] = review
            return redirect(url_for('code_review'))
        elif action == 'reject':
            # Generate a new prompt
            prompt = run_prompt_engineer(session['task'])
            session['prompt'] = prompt
            return redirect(url_for('prompt_approval'))
    return render_template_string(HTML_PROMPT, prompt=session['prompt'])

@app.route('/code', methods=['GET'])
def code_review():
    if 'code' not in session or 'review' not in session:
        return redirect(url_for('task_input'))
    files = parse_files(session['code'])
    # Add language for syntax highlighting and Tkinter detection
    for file in files:
        file['language'] = get_language_from_filename(file['filename'])
        file['is_tkinter'] = file['filename'].endswith('.py') and is_tkinter_code(file['content'])
    return render_template_string(HTML_CODE_REVIEW, files=files, review=session['review'])

@app.route('/download_zip')
def download_zip():
    files = parse_files(session['code'])
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.writestr(file['filename'], file['content'])
    mem_zip.seek(0)
    return send_file(mem_zip, mimetype='application/zip', as_attachment=True, download_name='code-generator-files.zip')

# --- Add new preview_project endpoint ---
@app.route('/preview_project', methods=['POST'])
def preview_project():
    files = parse_files(session['code'])
    from agents import run_project_preview
    result = run_project_preview(files)
    if result['type'] == 'html':
        return jsonify({'type': 'html', 'content': result['content']})
    elif result['type'] == 'image':
        img_b64 = base64.b64encode(result['content']).decode('utf-8')
        return jsonify({'type': 'image', 'content': img_b64})
    else:
        return jsonify({'type': 'error', 'content': result['content']}), 400

def open_browser():
    chrome_paths = [
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
    ]
    chrome_found = False
    for path in chrome_paths:
        if os.path.exists(path):
            webbrowser.get(f'"{path}" %s').open_new('http://127.0.0.1:5000/')
            chrome_found = True
            break
    if not chrome_found:
        print("Google Chrome not found. Opening in default browser instead.")
        try:
            webbrowser.open_new('http://127.0.0.1:5000/')
        except Exception as e:
            print(f"Could not open browser automatically: {e}")

def run_app():
    app.run(debug=False, use_reloader=False)

if __name__ == '__main__':
    threading.Timer(1.0, open_browser).start()
    run_app()
