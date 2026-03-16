import os
import sqlite3
import secrets
import string
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps

app = Flask(__name__)

# 数据库配置
DATABASE = '/data/keys.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
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

def generate_keys(count=2000, length=16):
    """生成密钥"""
    keys = []
    for _ in range(count):
        key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))
        keys.append(key)
    return keys

def init_keys(count=2000):
    """初始化密钥到数据库"""
    conn = get_db()
    c = conn.cursor()
    
    # 检查是否已有密钥
    c.execute("SELECT COUNT(*) FROM keys")
    if c.fetchone()[0] > 0:
        conn.close()
        print(f"数据库已有密钥，跳过生成")
        return
    
    keys = generate_keys(count)
    c.executemany("INSERT INTO keys (key) VALUES (?)", [(k,) for k in keys])
    conn.commit()
    conn.close()
    
    # 保存到文件备份
    with open('/data/keys_backup.txt', 'w') as f:
        f.write('\n'.join(keys))
    
    print(f"已生成 {count} 个密钥")
    print(f"密钥已保存到 /data/keys_backup.txt")
    print("=" * 50)
    print("前10个密钥示例：")
    for k in keys[:10]:
        print(k)
    print("=" * 50)
    print("管理页面地址: /admin")
    print("=" * 50)

# API验证密钥
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

# 验证装饰器
def require_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('key')
        if not key:
            return jsonify({'error': '请输入密钥'}), 401
        if not verify_key(key):
            return jsonify({'error': '密钥无效或已使用'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.get_json()
    key = data.get('key', '').strip()
    
    if not key:
        return jsonify({'valid': False, 'error': '请输入密钥'})
    
    if verify_key(key):
        return jsonify({'valid': True, 'message': '验证成功'})
    else:
        return jsonify({'valid': False, 'error': '密钥无效或已使用'})

@app.route('/api/stats', methods=['GET'])
def stats():
    """查看密钥统计（管理用）"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM keys")
    total = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as used FROM keys WHERE used = 1")
    used = c.fetchone()['used']
    conn.close()
    return jsonify({'total': total, 'used': used, 'available': total - used})

@app.route('/admin')
def admin():
    """管理页面"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, used, used_at FROM keys ORDER BY used DESC, key")
    keys = c.fetchall()
    conn.close()
    
    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>密钥管理</title>
    <style>
        body { font-family: Arial; padding: 20px; max-width: 1200px; margin: 0 auto; }
        h1 { color: #C9A86C; }
        .stats { background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .stats span { margin-right: 30px; font-size: 18px; }
        .btn { padding: 10px 20px; background: #C9A86C; color: white; border: none; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f5f5f5; }
        .used { color: green; }
        .unused { color: #C9A86C; }
    </style>
</head>
<body>
    <h1>🎭 甄嬛传测试 - 密钥管理</h1>
    <div class="stats">
        <span>总数: ''' + str(len(keys)) + '''</span>
        <span>已使用: ''' + str(len([k for k in keys if k['used']])) + '''</span>
        <span>未使用: ''' + str(len([k for k in keys if not k['used']])) + '''</span>
    </div>
    <button class="btn" onclick="exportKeys()">导出未使用密钥</button>
    <table>
        <tr><th>密钥</th><th>状态</th><th>使用时间</th></tr>'''
    
    for k in keys:
        status = '<span class="used">已使用</span>' if k['used'] else '<span class="unused">未使用</span>'
        used_at = k['used_at'] if k['used_at'] else '-'
        html += f'<tr><td>{k["key"]}</td><td>{status}</td><td>{used_at}</td></tr>'
    
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
            const blob = new Blob([text], {type: "text/plain"});
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "keys.txt";
            a.click();
        }
    </script>
</body>
</html>'''
    return html

@app.route('/api/export')
def export_all_keys():
    """导出所有密钥（带密码保护）"""
    password = request.args.get('password', '')
    # 简单密码保护，生产环境请用更安全的方式
    if password != os.environ.get('ADMIN_PASSWORD', 'admin123'):
        return jsonify({'error': '密码错误'}), 403
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, used, used_at FROM keys ORDER BY used, key")
    keys = c.fetchall()
    conn.close()
    
    return jsonify([{
        'key': k['key'],
        'used': bool(k['used']),
        'used_at': k['used_at']
    } for k in keys])

# 前端静态文件
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # Railway环境
    port = int(os.environ.get('PORT', 5000))
    
    # 初始化数据库
    init_db()
    init_keys(2000)
    
    app.run(host='0.0.0.0', port=port)
