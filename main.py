from flask import Flask, render_template_string, request, redirect, url_for, session
import webbrowser
import threading
import os
from agents import run_prompt_engineer, run_developer, run_code_reviewer

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure key in production

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

HTML_CODE_REVIEW = '''
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Generated Code & Review</title><style>
body { font-family: Arial, sans-serif; background: #f4f4f4; }
.container { max-width: 900px; margin: 60px auto; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.12); }
.title { text-align:center; font-size:2.2rem; font-weight:bold; letter-spacing:2px; color:#2563eb; margin-bottom:18px; }
h2 { text-align: center; }
.scroll-box { background: #f8f8f8; padding: 18px; border-radius: 6px; max-width: 100%; max-height: 350px; overflow-x: auto; overflow-y: auto; font-size: 1rem; white-space: pre; margin-bottom: 20px; border: 1px solid #e0e0e0; }
.review { margin-top: 30px; background: #e9ecef; padding: 18px; border-radius: 6px; }
.actions { text-align: center; margin-top: 20px; }
button { padding: 10px 28px; border: none; border-radius: 4px; background: #007bff; color: #fff; cursor: pointer; font-size: 1rem; }
button:hover { background: #0056b3; }
</style></head>
<body>
    <div class="container">
        <div class="title">CODE-GENERATOR</div>
        <h2>Generated Code</h2>
        <div class="scroll-box">{{ code }}</div>
        <div class="review">
            <h3>Code Review</h3>
            <div class="scroll-box">{{ review }}</div>
        </div>
        <div class="actions">
            <a href="/" style="text-decoration:none;"><button>Start Over</button></a>
        </div>
    </div>
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
    return render_template_string(HTML_CODE_REVIEW, code=session['code'], review=session['review'])

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
