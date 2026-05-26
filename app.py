from flask import Flask, jsonify, request, render_template
from bs4 import BeautifulSoup
import requests
import smtplib
import sqlite3
import threading
import time
from datetime import datetime

app = Flask(__name__)

DB_FILE = "tracker.db"

HEADERS = {
    'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 OPR/128.0.0.0"
}


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT NOT NULL,
        limit_price REAL NOT NULL,
        last_price REAL,
        last_check TEXT,
        img_url TEXT,
        active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        product TEXT,
        price REAL,
        limit_price REAL,
        alert_sent INTEGER,
        error TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    conn.commit()
    conn.close()


def load_products():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["limit"] = d.pop("limit_price")
        d["active"] = bool(d["active"])
        result.append(d)
    return result

def get_product(pid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["limit"] = d.pop("limit_price")
    d["active"] = bool(d["active"])
    return d

def insert_product(data):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (name, url, limit_price, active) VALUES (?, ?, ?, 1)",
        (data.get("name", ""), data["url"], float(data["limit"]))
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

def update_product(pid, data):
    conn = get_conn()
    conn.execute(
        "UPDATE products SET name=?, url=?, limit_price=?, active=? WHERE id=?",
        (data.get("name", ""), data["url"], float(data["limit"]), int(data.get("active", 1)), pid)
    )
    conn.commit()
    conn.close()

def update_product_check(pid, price, img_url, name):
    conn = get_conn()
    conn.execute(
        "UPDATE products SET last_price=?, last_check=?, img_url=COALESCE(?, img_url), name=COALESCE(NULLIF(name,''), ?) WHERE id=?",
        (price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), img_url, name, pid)
    )
    conn.commit()
    conn.close()

def delete_product(pid):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def add_log(product_name, price, limit, sent_email, error=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (timestamp, product, price, limit_price, alert_sent, error) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), product_name, price, limit, int(sent_email), error)
    )
    conn.commit()
    conn.close()

def load_logs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["limit"] = d.pop("limit_price")
        d["alert_sent"] = bool(d["alert_sent"])
        result.append(d)
    return result


def load_settings():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def save_settings(data):
    conn = get_conn()
    for key, value in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
    conn.commit()
    conn.close()


def scrape_price(url):
    site = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(site.content, 'html.parser')
    title = soup.find('h1').getText().strip()
    price_div = soup.find('div', class_='product-price').getText().strip()
    raw = price_div.replace('R$', '').replace('\xa0', '').strip()
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    else:
        raw = raw.replace('.', '')
    num_price = float(raw)
    slide = soup.find('a', class_='swiper-slide-active')
    img_url = None
    if slide:
        img = slide.find('img')
        if img:
            img_url = img.get('src')
    return title, num_price, img_url


def send_email(product, price, email_from, email_to, password):
    import email.mime.text
    import email.mime.multipart

    content = f"""
    <h2>Alerta de preco!</h2>
    <p>O produto <strong>{product['name']}</strong> esta com preco abaixo do seu limite!</p>
    <ul>
        <li><strong>Preco atual:</strong> R$ {price:,.2f}</li>
        <li><strong>Seu limite:</strong> R$ {product['limit']:,.2f}</li>
    </ul>
    <p><a href="{product['url']}">Comprar agora</a></p>
    """

    msg = email.mime.multipart.MIMEMultipart('alternative')
    msg['Subject'] = f"[Price Tracker] {product['name']} baixou de preco!"
    msg['From'] = email_from
    msg['To'] = email_to

    parte = email.mime.text.MIMEText(content, 'html', 'utf-8')
    msg.attach(parte)

    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(email_from, password)
    s.sendmail(email_from, [email_to], msg.as_string())
    s.quit()


def check_product(product, settings):
    name = product.get("name") or "Produto"
    try:
        title, price, img_url = scrape_price(product["url"])
        if not product.get("name"):
            name = title
        sent = False
        if price < product["limit"]:
            try:
                send_email(
                    {**product, "name": name},
                    price,
                    settings["email_from"],
                    settings["email_to"],
                    settings["password"]
                )
                sent = True
            except Exception as e:
                add_log(name, price, product["limit"], False, f"Erro ao enviar e-mail: {e}")
                return
        add_log(name, price, product["limit"], sent)
        update_product_check(product["id"], price, img_url, name)
    except Exception as e:
        add_log(name, None, product.get("limit"), False, str(e))

def background_checker():
    while True:
        settings = load_settings()
        if settings:
            for p in load_products():
                if p.get("active"):
                    check_product(p, settings)
        interval_hours = int(settings.get("interval_hours", 6)) if settings else 6
        time.sleep(interval_hours * 3600)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/products", methods=["GET"])
def get_products():
    return jsonify(load_products())

@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.json
    new_id = insert_product(data)
    product = get_product(new_id)
    return jsonify(product), 201

@app.route("/api/products/<int:pid>", methods=["PUT"])
def edit_product(pid):
    data = request.json
    update_product(pid, data)
    return jsonify(get_product(pid))

@app.route("/api/products/<int:pid>", methods=["DELETE"])
def remove_product(pid):
    delete_product(pid)
    return jsonify({"ok": True})

@app.route("/api/products/<int:pid>/check", methods=["POST"])
def check_now(pid):
    product = get_product(pid)
    if not product:
        return jsonify({"error": "not found"}), 404
    settings = load_settings()
    if not settings:
        return jsonify({"error": "configure as settings primeiro"}), 400
    check_product(product, settings)
    return jsonify(get_product(pid))

@app.route("/api/settings", methods=["GET"])
def get_settings_route():
    s = load_settings()
    return jsonify({k: v for k, v in s.items() if k != "password"})

@app.route("/api/settings", methods=["POST"])
def save_settings_route():
    data = request.json
    existing = load_settings()
    if not data.get("password"):
        data["password"] = existing.get("password", "")
    save_settings(data)
    return jsonify({"ok": True})

@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify(load_logs()[:50])

if __name__ == "__main__":
    init_db()
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()
    app.run(debug=True, port=5000)
