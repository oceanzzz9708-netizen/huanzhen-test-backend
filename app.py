import os
import sqlite3
import secrets
import string
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# Railway volume 挂载到 /data
VOLUME_DIR = os.environ.get('DATA_DIR', '/data')
DB_PATH = os.path.join(VOLUME_DIR, 'keys.db')

print(f"启动目录: {os.getcwd()}")
print(f"数据目录: {VOLUME_DIR}")
print(f"数据库路径: {DB_PATH}")

# 确保目录存在
os.makedirs(VOLUME_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        used INTEGER DEFAULT 0,
        used_at TIMESTAMP DEFAULT NULL
    )''')
    conn.commit()
    conn.close()
    print("数据库初始化成功")

def generate_keys(count=2000, length=16):
    keys = []
    for _ in range(count):
        key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))
        keys.append(key)
    return keys

def init_keys(count=2000):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM keys")
    if c.fetchone()[0] > 0:
        conn.close()
        print(f"数据库已有密钥")
        return
    
    keys = generate_keys(count)
    c.executemany("INSERT INTO keys (key) VALUES (?)", [(k,) for k in keys])
    conn.commit()
    conn.close()
    print(f"已生成 {count} 个密钥")

def verify_key(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM keys WHERE key = ? AND used = 0", (key,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE keys SET used = 1, used_at = CURRENT_TIMESTAMP WHERE key = ?", (key,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.get_json() or {}
    key = data.get('key', '').strip()
    if not key:
        return jsonify({'valid': False, 'error': '请输入密钥'})
    if verify_key(key):
        return jsonify({'valid': True, 'message': '验证成功'})
    return jsonify({'valid': False, 'error': '密钥无效或已使用'})

@app.route('/api/stats', methods=['GET'])
def stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM keys")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM keys WHERE used = 1")
    used = c.fetchone()[0]
    conn.close()
    return jsonify({'total': total, 'used': used, 'available': total - used})

@app.route('/admin')
def admin():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, used, used_at FROM keys ORDER BY used DESC, key")
    keys = c.fetchall()
    conn.close()
    
    keys_list = [(k['key'], k['used'], k['used_at']) for k in keys]
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>密钥管理</title>
    <style>
        body {{ font-family: Arial; padding: 20px; max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #C9A86C; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .stats span {{ margin-right: 30px; font-size: 18px; }}
        .btn {{ padding: 10px 20px; background: #C9A86C; color: white; border: none; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; }}
        .used {{ color: green; }}
        .unused {{ color: #C9A86C; }}
    </style>
</head>
<body>
    <h1>🎭 甄嬛传测试 - 密钥管理</h1>
    <div class="stats">
        <span>总数: {len(keys_list)}</span>
        <span>已使用: {len([k for k in keys_list if k[1]])}</span>
        <span>未使用: {len([k for k in keys_list if not k[1]])}</span>
    </div>
    <button class="btn" onclick="exportKeys()">导出未使用密钥</button>
    <table>
        <tr><th>密钥</th><th>状态</th><th>使用时间</th></tr>'''
    
    for k in keys_list:
        status = '<span class="used">已使用</span>' if k[1] else '<span class="unused">未使用</span>'
        used_at = k[2] if k[2] else '-'
        html += f'<tr><td>{k[0]}</td><td>{status}</td><td>{used_at}</td></tr>'
    
    html += '''
    </table>
    <script>
        function exportKeys() {
            const rows = document.querySelectorAll("table tr");
            let text = "";
            for(let i = 1; i < rows.length; i++) {
                const cells = rows[i].querySelectorAll("td");
                if(cells[1].textContent === "未使用") {
                    text += cells[0].textContent + "\\n";
                }
            }
            const blob = new Blob([text], {{type: "text/plain"}});
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "keys.txt";
            a.click();
        }
    </script>
</body>
</html>'''
    return html

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    init_db()
    init_keys(2000)
    app.run(host='0.0.0.0', port=port)
