from flask import Flask, render_template, request, jsonify, session
from functools import wraps
import json
import os
from datetime import datetime
import uuid
import qrcode
from io import BytesIO
import base64
from flask import request

app = Flask(__name__)
app.secret_key = 'gizli-anahtar-buraya-yaz'

# JSON dosya yolları
DATA_DIR = 'data'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
MENU_FILE = os.path.join(DATA_DIR, 'menu.json')
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')
TABLES_FILE = os.path.join(DATA_DIR, 'tables.json')
CATEGORIES_FILE = os.path.join(DATA_DIR, 'categories.json')

# Data klasörünü oluştur
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# JSON dosyalarını yükle/oluştur
def load_json(filepath, default_data):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        save_json(filepath, default_data)
        return default_data

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Varsayılan veriler
def init_data():
    # Kullanıcılar
    users = load_json(USERS_FILE, {
        "admin": {"password": "admin123", "role": "admin"},
        "mutfak": {"password": "mutfak123", "role": "kitchen"},
        "garson": {"password": "garson123", "role": "waiter"}
    })
    
    # Kategoriler
    categories = load_json(CATEGORIES_FILE, [
        {"id": "1", "name": "Ana Yemekler"},
        {"id": "2", "name": "İçecekler"},
        {"id": "3", "name": "Tatlılar"},
        {"id": "4", "name": "Başlangıçlar"}
    ])
    
    # Menü
    menu = load_json(MENU_FILE, [
        {"id": "1", "name": "Izgara Köfte", "price": 120, "category": "1"},
        {"id": "2", "name": "Tavuk Şiş", "price": 110, "category": "1"},
        {"id": "3", "name": "Karışık Izgara", "price": 180, "category": "1"},
        {"id": "4", "name": "Ayran", "price": 15, "category": "2"},
        {"id": "5", "name": "Kola", "price": 20, "category": "2"},
        {"id": "6", "name": "Künefe", "price": 80, "category": "3"},
        {"id": "7", "name": "Baklava", "price": 70, "category": "3"},
        {"id": "8", "name": "Mercimek Çorbası", "price": 35, "category": "4"}
        
    ])
    
    # Masalar (30 masa)
    tables = load_json(TABLES_FILE, [
        {"number": i, "status": "empty"} for i in range(1, 31)
    ])
    
    # Siparişler
    orders = load_json(ORDERS_FILE, [])

init_data()

# Oturum kontrolü
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return jsonify({"error": "Giriş yapmalısınız"}), 401
            if role and session.get('role') != role:
                return jsonify({"error": "Yetkiniz yok"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Ana sayfa - Login
@app.route('/')
def index():
    return render_template('login.html')

# Müşteri ekranı
@app.route('/customer')
def customer():
    return render_template('customer.html')

# Mutfak ekranı
@app.route('/kitchen')
@login_required(role='kitchen')
def kitchen():
    return render_template('kitchen.html')

# Garson ekranı
@app.route('/waiter')
@login_required(role='waiter')
def waiter():
    return render_template('waiter.html')

# Admin ekranı
@app.route('/admin')
@login_required(role='admin')
def admin():
    return render_template('admin.html')

# API: Login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    users = load_json(USERS_FILE, {})
    
    username = data.get('username')
    password = data.get('password')
    
    if username in users and users[username]['password'] == password:
        session['user'] = username
        session['role'] = users[username]['role']
        return jsonify({
            "success": True,
            "role": users[username]['role']
        })
    
    return jsonify({"success": False, "error": "Kullanıcı adı veya şifre hatalı"}), 401

# API: Logout
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# API: Menüyü getir
@app.route('/api/menu', methods=['GET'])
def get_menu():
    menu = load_json(MENU_FILE, [])
    categories = load_json(CATEGORIES_FILE, [])
    return jsonify({"menu": menu, "categories": categories})

# API: Sipariş oluştur (Müşteri)
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    orders = load_json(ORDERS_FILE, [])
    
    order = {
        "id": str(uuid.uuid4()),
        "table_number": data['table_number'],
        "items": data['items'],
        "total": data['total'],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    orders.append(order)
    save_json(ORDERS_FILE, orders)
    
    return jsonify({"success": True, "order": order})

# API: Siparişleri getir
@app.route('/api/orders', methods=['GET'])
@login_required()
def get_orders():
    orders = load_json(ORDERS_FILE, [])
    status = request.args.get('status')
    
    if status:
        orders = [o for o in orders if o['status'] == status]
    
    return jsonify({"orders": orders})

# API: Sipariş durumunu güncelle (Mutfak)
@app.route('/api/orders/<order_id>', methods=['PUT'])
@login_required(role='kitchen')
def update_order(order_id):
    data = request.json
    orders = load_json(ORDERS_FILE, [])
    
    for order in orders:
        if order['id'] == order_id:
            order['status'] = data['status']
            order['updated_at'] = datetime.now().isoformat()
            save_json(ORDERS_FILE, orders)
            return jsonify({"success": True, "order": order})
    
    return jsonify({"error": "Sipariş bulunamadı"}), 404

# API: Masaları getir
@app.route('/api/tables', methods=['GET'])
def get_tables():
    tables = load_json(TABLES_FILE, [])
    return jsonify({"tables": tables})

# API: Masa durumunu güncelle (Garson)
@app.route('/api/tables/<int:table_number>', methods=['PUT'])
@login_required(role='waiter')
def update_table(table_number):
    data = request.json
    tables = load_json(TABLES_FILE, [])
    
    for table in tables:
        if table['number'] == table_number:
            table['status'] = data['status']
            save_json(TABLES_FILE, tables)
            return jsonify({"success": True, "table": table})
    
    return jsonify({"error": "Masa bulunamadı"}), 404

# API: Menü ekle/güncelle (Admin)
@app.route('/api/menu', methods=['POST'])
@login_required(role='admin')
def add_menu_item():
    data = request.json
    menu = load_json(MENU_FILE, [])
    
    if 'id' in data and data['id']:
        # Güncelleme
        for item in menu:
            if item['id'] == data['id']:
                item.update(data)
                save_json(MENU_FILE, menu)
                return jsonify({"success": True, "item": item})
    else:
        # Yeni ekleme
        new_item = {
            "id": str(len(menu) + 1),
            "name": data['name'],
            "price": data['price'],
            "category": data['category']
        }
        menu.append(new_item)
        save_json(MENU_FILE, menu)
        return jsonify({"success": True, "item": new_item})

# API: Menü öğesi sil (Admin)
@app.route('/api/menu/<item_id>', methods=['DELETE'])
@login_required(role='admin')
def delete_menu_item(item_id):
    menu = load_json(MENU_FILE, [])
    menu = [item for item in menu if item['id'] != item_id]
    save_json(MENU_FILE, menu)
    return jsonify({"success": True})

# API: Raporlar (Admin)
@app.route('/api/reports', methods=['GET'])
@login_required(role='admin')
def get_reports():
    orders = load_json(ORDERS_FILE, [])
    period = request.args.get('period', 'daily')
    
    # Basit rapor hesaplama
    total_orders = len(orders)
    total_revenue = sum(o['total'] for o in orders if o['status'] == 'delivered')
    
    return jsonify({
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "period": period
    })
CALLS_FILE = os.path.join(DATA_DIR, 'calls.json')

# Çağrıları yükle
def get_calls():
    return load_json(CALLS_FILE, [])

# API: Garson çağır (Müşteri)
@app.route('/api/calls', methods=['POST'])
def create_call():
    data = request.json
    calls = get_calls()
    
    call = {
        "id": str(uuid.uuid4()),
        "table_number": data['table_number'],
        "message": data.get('message', 'Garson çağrısı'),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    calls.append(call)
    save_json(CALLS_FILE, calls)
    
    return jsonify({"success": True, "call": call})

# API: Çağrıları getir (Garson)
@app.route('/api/calls', methods=['GET'])
@login_required(role='waiter')
def get_all_calls():
    calls = get_calls()
    # Sadece bekleyen çağrıları göster
    pending_calls = [c for c in calls if c['status'] == 'pending']
    return jsonify({"calls": pending_calls})

# API: Çağrıyı kapat (Garson)
@app.route('/api/calls/<call_id>', methods=['DELETE'])
@login_required(role='waiter')
def close_call(call_id):
    calls = get_calls()
    calls = [c for c in calls if c['id'] != call_id]
    save_json(CALLS_FILE, calls)
    return jsonify({"success": True})

# Müşteri sayfası - Masa numarası ile
@app.route('/customer/<int:table_number>')
def customer_with_table(table_number):
    return render_template('customer.html', table_number=table_number)

# API: QR Kod oluştur
@app.route('/api/qr/<int:table_number>')
@login_required(role='admin')
def generate_qr(table_number):
    # QR kod için URL
    base_url = request.host_url
    qr_url = f"{base_url}customer/{table_number}"

    
    
    # QR kod oluştur
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # QR kodu resme çevir
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Base64'e çevir
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        "success": True,
        "qr_code": f"data:image/png;base64,{img_str}",
        "url": qr_url,
        "table_number": table_number
    })
if __name__ == '__main__':
    app.run()
