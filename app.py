from flask import Flask, render_template_string, request, jsonify, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import wraps
from sqlalchemy import func, Index, or_
import pandas as pd
import io
import os
import base64
import json
import gzip
import urllib.parse

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart-system-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== حقوق الملكية ====================
FOOTER_TEXT = "جميع الحقوق محفوظة © علي حسين المسلم - 0546446382"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'غير مصرح'}), 403
        return f(*args, **kwargs)
    return decorated_function

def log_activity(user, action, details=""):
    try:
        log = ActivityLog(
            user_id=user.id if user else None,
            user_name=user.name if user else "نظام",
            action=action,
            details=details,
            ip_address=request.remote_addr if hasattr(request, 'remote_addr') else "0.0.0.0"
        )
        db.session.add(log)
        db.session.commit()
    except:
        db.session.rollback()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='cashier')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_name = db.Column(db.String(100))
    action = db.Column(db.String(200))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    cost = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False, default=0.0)
    expiry_months = db.Column(db.Integer, default=0)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Branch(db.Model):
    __tablename__ = 'branches'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    debt = db.Column(db.Float, default=0.0)

class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    pending_commission = db.Column(db.Float, default=0.0)

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime, nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_id_number = db.Column(db.String(20))
    product_name = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False, default=0.0)
    employee_name = db.Column(db.String(100), nullable=False)
    branch_name = db.Column(db.String(100), nullable=False)
    channel_name = db.Column(db.String(100), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    net_profit = db.Column(db.Float, nullable=False)
    commission_status = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text, default='')
    
    __table_args__ = (
        Index('idx_sale_date', 'date'),
        Index('idx_sale_branch', 'branch_name'),
        Index('idx_sale_order_id', 'order_id'),
        Index('idx_sale_phone', 'customer_phone'),
        Index('idx_sale_product', 'product_name'),
    )

class PaymentLog(db.Model):
    __tablename__ = 'payment_logs'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    branch_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

class Wallet(db.Model):
    __tablename__ = 'wallets'
    id = db.Column(db.Integer, primary_key=True)
    main_balance = db.Column(db.Float, default=0.0)
    pending_commission = db.Column(db.Float, default=0.0)
    profits = db.Column(db.Float, default=0.0)
    capital_base = db.Column(db.Float, default=0.0)

class CompanyInfo(db.Model):
    __tablename__ = 'company_info'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default='البرنامج الذكي')
    address = db.Column(db.String(500), default='')
    tax_number = db.Column(db.String(100), default='')
    phone = db.Column(db.String(50), default='')
    commercial_reg = db.Column(db.String(100), default='')

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_wallet():
    wallet = Wallet.query.first()
    if not wallet:
        wallet = Wallet()
        db.session.add(wallet)
        db.session.commit()
    return wallet

def get_company_info():
    info = CompanyInfo.query.first()
    if not info:
        info = CompanyInfo()
        db.session.add(info)
        db.session.commit()
    return info

def init_db():
    db.create_all()
    if User.query.count() == 0:
        admin = User(username='admin', name='مدير النظام', role='admin')
        admin.set_password('admin123')
        cashier = User(username='ali', name='علي', role='cashier')
        cashier.set_password('1234')
        db.session.add_all([admin, cashier])
        db.session.commit()
    if Wallet.query.count() == 0:
        db.session.add(Wallet())
        db.session.commit()
    if CompanyInfo.query.count() == 0:
        db.session.add(CompanyInfo())
        db.session.commit()
    if Employee.query.count() == 0:
        for emp in ['علي', 'أحمد', 'محمد']:
            db.session.add(Employee(name=emp))
        db.session.commit()
    if Branch.query.count() == 0:
        for branch in ['الفرع الرئيسي', 'فرع النزهة', 'فرع الأندلس']:
            db.session.add(Branch(name=branch))
        db.session.commit()
    if Channel.query.count() == 0:
        for ch in ['المتجر الإلكتروني', 'سوق كوم', 'واتساب', 'تيك توك', 'انستقرام']:
            db.session.add(Channel(name=ch))
        db.session.commit()
    if SystemSettings.query.filter_by(key='default_invoice_note').count() == 0:
        setting = SystemSettings(key='default_invoice_note', value='شكراً لثقتكم بنا')
        db.session.add(setting)
        db.session.commit()
    if SystemSettings.query.filter_by(key='logo_base64').count() == 0:
        setting = SystemSettings(key='logo_base64', value='')
        db.session.add(setting)
        db.session.commit()

def get_default_invoice_note():
    setting = SystemSettings.query.filter_by(key='default_invoice_note').first()
    if setting:
        return setting.value
    return "شكراً لثقتكم بنا"

def get_logo_base64():
    setting = SystemSettings.query.filter_by(key='logo_base64').first()
    if setting and setting.value:
        return setting.value
    return ""

def calculate_balance():
    wallet = get_wallet()
    total_branch_debt = sum(b.debt for b in Branch.query.all())
    total_pending_commission = sum(c.pending_commission for c in Channel.query.all())
    total_assets = wallet.main_balance + total_branch_debt + total_pending_commission
    total_liabilities = wallet.capital_base + wallet.profits
    balance = total_assets - total_liabilities
    return balance, total_assets, total_liabilities, total_branch_debt, total_pending_commission

# ==================== دالة القالب الأساسي مع تحسين النوافذ المنبثقة ====================
def get_base_html(content, title="البرنامج الذكي", user_name="", is_admin=False):
    company = get_company_info()
    site_title = company.name if company.name else "البرنامج الذكي"
    
    user_profile = f'''
    <div class="mb-6 p-4 bg-gray-800/50 rounded-xl">
        <div class="flex items-center gap-3 mb-3">
            <div class="w-12 h-12 bg-cyan-500 rounded-full flex items-center justify-center text-xl font-bold">{user_name[0] if user_name else 'م'}</div>
            <div>
                <p class="font-bold text-white">{user_name}</p>
                <p class="text-xs text-gray-400">{'مدير النظام' if is_admin else 'كاشير'}</p>
            </div>
        </div>
        <div class="space-y-2">
            <div class="flex justify-between text-sm"><span class="text-gray-400">اسم المستخدم:</span><span class="text-white">{current_user.username if current_user.is_authenticated else ''}</span></div>
            <button id="openChangePasswordModal" class="btn-warning w-full py-2 rounded-xl text-sm mt-2"><i class="fas fa-key ml-1"></i> تغيير كلمة المرور</button>
        </div>
    </div>
    
    <div id="changePasswordModal" class="fixed inset-0 bg-black/70 hidden items-center justify-center z-50 transition-all duration-300">
        <div class="bg-gray-900 rounded-2xl p-6 w-full max-w-md mx-4 transform transition-all shadow-2xl border border-gray-700">
            <h2 class="text-2xl font-bold mb-4 flex items-center gap-2"><i class="fas fa-lock text-cyan-400"></i> تغيير كلمة المرور</h2>
            <div class="space-y-3">
                <div><label class="block text-sm font-medium mb-1">كلمة المرور الحالية</label><input type="password" id="modalOldPass" class="w-full px-4 py-2 rounded-xl bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"></div>
                <div><label class="block text-sm font-medium mb-1">كلمة المرور الجديدة</label><input type="password" id="modalNewPass" class="w-full px-4 py-2 rounded-xl bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"></div>
                <div><label class="block text-sm font-medium mb-1">تأكيد كلمة المرور الجديدة</label><input type="password" id="modalConfirmPass" class="w-full px-4 py-2 rounded-xl bg-gray-800 border border-gray-700 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"></div>
                <div class="flex gap-3 mt-4"><button id="savePasswordBtn" class="btn-primary flex-1 py-2 rounded-xl"><i class="fas fa-save ml-2"></i> حفظ</button><button id="closePasswordModal" class="bg-red-600 hover:bg-red-700 flex-1 py-2 rounded-xl"><i class="fas fa-times ml-2"></i> إلغاء</button></div>
            </div>
        </div>
    </div>
    '''
    
    admin_links = ''
    if is_admin:
        admin_links = '''
                <a href="/debts" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-landmark w-5"></i> المديونية</a>
                <a href="/commissions" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-percent w-5"></i> العمولات</a>
                <a href="/settings" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-sliders-h w-5"></i> الإعدادات</a>
                <a href="/manage" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-users w-5"></i> الإدارة</a>
                <a href="/activity-log" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-history w-5"></i> سجل العمليات</a>
                <a href="/restore" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-undo-alt w-5"></i> استعادة نسخة</a>
    '''
    
    return f'''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover">
    <title>{title} - {site_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ -webkit-tap-highlight-color: transparent; }}
        body {{ font-family: 'Tajawal', sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; }}
        .sidebar {{ background: linear-gradient(180deg, #0f3460 0%, #16213e 100%); transition: transform 0.3s ease; }}
        .card {{ background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 1rem; transition: all 0.3s ease; }}
        .card:hover {{ transform: translateY(-5px); }}
        .btn-primary {{ background: linear-gradient(135deg, #00b4d8, #0077b6); }}
        .btn-primary:hover, .btn-success:hover, .btn-danger:hover {{ transform: scale(1.02); }}
        .btn-success {{ background: linear-gradient(135deg, #06d6a0, #059669); }}
        .btn-danger {{ background: linear-gradient(135deg, #ef476f, #c1121f); }}
        .btn-warning {{ background: linear-gradient(135deg, #ffd166, #f4a261); }}
        @media (max-width: 768px) {{ .sidebar {{ transform: translateX(-100%); position: fixed; top: 0; right: 0; height: 100%; width: 85%; max-width: 280px; z-index: 1000; overflow-y: auto; }} .sidebar.open {{ transform: translateX(0); }} }}
        .toast {{ position: fixed; bottom: 20px; left: 20px; z-index: 1000; animation: slideIn 0.3s ease; }}
        @keyframes slideIn {{ from {{ transform: translateX(100%); opacity: 0; }} to {{ transform: translateX(0); opacity: 1; }} }}
        input, select, textarea {{ transition: all 0.2s ease; background: #1e293b; border-color: #334155; color: #e2e8f0; }}
        input:focus, select:focus, textarea:focus {{ border-color: #00b4d8; outline: none; box-shadow: 0 0 0 2px rgba(0,180,216,0.2); }}
        .product-card {{ transition: all 0.2s ease; cursor: pointer; background: #1e293b; }}
        .product-card:hover {{ transform: translateY(-3px); background: #2d3748; }}
        .product-card.selected {{ background: rgba(0,180,216,0.3); border: 1px solid #00b4d8; }}
        .payment-btn {{ transition: all 0.2s ease; cursor: pointer; background: #1e293b; border: 2px solid #334155; }}
        .payment-btn.selected {{ background: #00b4d8; color: #1a1a2e; border-color: #00b4d8; }}
        table {{ width: 100%; border-collapse: collapse; overflow-x: auto; display: block; }}
        @media (min-width: 768px) {{ table {{ display: table; }} }}
        th, td {{ padding: 8px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        @media (min-width: 768px) {{ th, td {{ padding: 12px; }} }}
        th {{ background: rgba(0,180,216,0.2); font-weight: bold; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .stat-card {{ background: rgba(0,0,0,0.3); border-radius: 1rem; padding: 0.75rem; text-align: center; }}
        @media (min-width: 768px) {{ .stat-card {{ padding: 1rem; }} }}
        .debt-card {{ background: rgba(255,255,255,0.03); border-radius: 1rem; padding: 1rem; border-right: 3px solid #00b4d8; }}
        .logo-img {{ max-width: 50px; max-height: 50px; border-radius: 50%; object-fit: cover; }}
        @media (min-width: 768px) {{ .logo-img {{ max-width: 60px; max-height: 60px; }} }}
        .mode-toggle {{ cursor: pointer; transition: all 0.3s ease; }}
        .mode-toggle:hover {{ transform: scale(1.1); }}
        .balance-card {{ background: rgba(0,0,0,0.4); border-radius: 1rem; padding: 1rem; text-align: center; }}
        .balance-positive {{ color: #10b981; }}
        .balance-negative {{ color: #ef4444; }}
        .balance-zero {{ color: #f59e0b; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }}
        @media (min-width: 768px) {{ .grid {{ gap: 1.5rem; }} }}
        .modal-overlay {{
            position: fixed;
            inset: 0;
            background-color: rgba(0,0,0,0.7);
            backdrop-filter: blur(4px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }}
        .modal-container {{
            background: #1e293b;
            border-radius: 1.5rem;
            padding: 1.5rem;
            max-width: 90%;
            width: 100%;
            max-height: 85vh;
            overflow-y: auto;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
            border: 1px solid rgba(0,180,216,0.3);
            transform: scale(0.95);
            transition: transform 0.2s ease;
        }}
        .modal-container.active {{
            transform: scale(1);
        }}
        .checkbox-group {{
            background: #0f172a;
            border-radius: 1rem;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            transition: 0.2s;
        }}
        .checkbox-group:hover {{
            background: #1e293b;
        }}
    </style>
</head>
<body class="text-gray-200">
    <div id="sidebar" class="sidebar fixed top-0 right-0 h-full w-72 z-50 transition-transform duration-300 overflow-y-auto">
        <div class="p-4">
            <div class="flex justify-between items-center mb-4">
                <button id="closeSidebar" class="lg:hidden text-2xl text-white">&times;</button>
                <div class="text-center flex-1">
                    <div id="logoDisplay"></div>
                    <h2 class="text-xl font-bold text-cyan-400">{site_title}</h2>
                </div>
            </div>
            {user_profile}
            <nav class="space-y-1">
                <a href="/dashboard" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-chart-line w-5"></i> الرئيسية</a>
                <a href="/sales" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-cart-shopping w-5"></i> شاشة البيع</a>
                <a href="/products" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-boxes w-5"></i> المنتجات</a>
                <a href="/reports" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-chart-bar w-5"></i> التقارير</a>
                <a href="/company-settings" class="nav-link flex items-center gap-3 p-3 rounded-xl hover:bg-white/10"><i class="fas fa-building w-5"></i> بيانات الشركة</a>
                {admin_links}
            </nav>
            <div class="mt-6 pt-4 border-t border-gray-700">
                <div class="flex justify-between items-center mb-4">
                    <button id="themeToggle" class="mode-toggle flex items-center gap-2 p-2 rounded-xl hover:bg-white/10">
                        <i id="themeIcon" class="fas fa-moon"></i>
                        <span id="themeText">وضع ليلي</span>
                    </button>
                </div>
                <hr class="border-gray-700 mb-4">
                <p class="text-xs text-center text-gray-500 mb-2">{FOOTER_TEXT}</p>
                <a href="/logout" class="flex items-center gap-3 p-3 rounded-xl hover:bg-red-500/20 text-red-400"><i class="fas fa-sign-out-alt w-5"></i> تسجيل خروج</a>
            </div>
        </div>
    </div>

    <div class="lg:hidden fixed top-0 right-0 left-0 bg-gray-900/95 z-40 p-3 flex justify-between items-center shadow-lg">
        <button id="openSidebar" class="text-2xl text-white"><i class="fas fa-bars"></i></button>
        <h1 class="text-lg font-bold text-cyan-400">{site_title}</h1>
        <div class="w-8"></div>
    </div>

    <div id="mainContent" class="transition-all duration-300 lg:mr-72">
        <div class="container mx-auto p-3 lg:p-6 pt-14 lg:pt-6">
            {content}
        </div>
    </div>

    <div id="toastContainer"></div>

    <script>
        const sidebar = document.getElementById('sidebar');
        document.getElementById('openSidebar')?.addEventListener('click', () => sidebar.classList.add('open'));
        document.getElementById('closeSidebar')?.addEventListener('click', () => sidebar.classList.remove('open'));
        function setTheme(isDark) {{
            if(isDark) {{
                document.body.classList.remove('light-mode');
                localStorage.setItem('theme', 'dark');
                document.getElementById('themeIcon').className = 'fas fa-moon';
                document.getElementById('themeText').innerText = 'وضع ليلي';
            }} else {{
                document.body.classList.add('light-mode');
                localStorage.setItem('theme', 'light');
                document.getElementById('themeIcon').className = 'fas fa-sun';
                document.getElementById('themeText').innerText = 'وضع نهاري';
            }}
        }}
        const savedTheme = localStorage.getItem('theme');
        if(savedTheme === 'light') setTheme(false);
        else setTheme(true);
        document.getElementById('themeToggle').addEventListener('click', () => {{
            const isDark = !document.body.classList.contains('light-mode');
            setTheme(!isDark);
        }});
        function showToast(msg, type) {{
            type = type || 'success';
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            const colors = {{ success: 'bg-green-600', error: 'bg-red-600', info: 'bg-blue-600', warning: 'bg-yellow-600' }};
            toast.className = 'toast ' + (colors[type] || colors.success) + ' text-white px-4 py-2 rounded-xl shadow-lg mb-2 text-sm';
            toast.innerHTML = msg;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }}
        async function loadLogo() {{
            try {{
                const res = await fetch('/api/logo');
                const data = await res.json();
                if(data.logo) document.getElementById('logoDisplay').innerHTML = '<img src="' + data.logo + '" class="logo-img mx-auto mb-2">';
            }} catch(e) {{ console.error(e); }}
        }}
        document.getElementById('openChangePasswordModal')?.addEventListener('click', () => {{
            document.getElementById('changePasswordModal').classList.remove('hidden');
            document.getElementById('changePasswordModal').classList.add('flex');
        }});
        document.getElementById('closePasswordModal')?.addEventListener('click', () => {{
            document.getElementById('changePasswordModal').classList.add('hidden');
            document.getElementById('changePasswordModal').classList.remove('flex');
        }});
        document.getElementById('savePasswordBtn')?.addEventListener('click', async () => {{
            const oldPass = document.getElementById('modalOldPass').value;
            const newPass = document.getElementById('modalNewPass').value;
            const confirmPass = document.getElementById('modalConfirmPass').value;
            if(!oldPass || !newPass) {{ showToast('الرجاء تعبئة جميع الحقول','error'); return; }}
            if(newPass !== confirmPass) {{ showToast('كلمتا المرور غير متطابقتين','error'); return; }}
            const res = await fetch('/change-password', {{
                method: 'POST',
                headers: {{'Content-Type':'application/json'}},
                body: JSON.stringify({{old_password: oldPass, new_password: newPass}})
            }});
            if(res.ok) {{ showToast('✅ تم تغيير كلمة المرور بنجاح','success'); document.getElementById('closePasswordModal').click(); document.getElementById('modalOldPass').value=''; document.getElementById('modalNewPass').value=''; document.getElementById('modalConfirmPass').value=''; }}
            else {{ const data=await res.json(); showToast(data.error,'error'); }}
        }});
        loadLogo();
        window.showToast = showToast;
    </script>
</body>
</html>
'''

# ==================== صفحة تسجيل الدخول ====================
LOGIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - البرنامج الذكي</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Tajawal', sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            position: relative;
            overflow-x: hidden;
        }
        .animated-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
        }
        .animated-bg span {
            position: absolute;
            display: block;
            width: 20px;
            height: 20px;
            background: rgba(255,255,255,0.05);
            bottom: -150px;
            animation: floatUp 15s infinite;
            border-radius: 50%;
        }
        @keyframes floatUp {
            0% { transform: translateY(0) rotate(0deg); opacity: 0; }
            50% { opacity: 0.5; }
            100% { transform: translateY(-1000px) rotate(720deg); opacity: 0; }
        }
        .login-card {
            background: rgba(255,255,255,0.08);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
            transition: all 0.3s ease;
        }
        .login-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 30px 60px -12px rgba(0,0,0,0.6);
        }
        .input-field {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 1rem;
            padding: 0.875rem 1rem;
            color: white;
            transition: all 0.3s ease;
        }
        .input-field:focus {
            outline: none;
            border-color: #00b4d8;
            background: rgba(255,255,255,0.15);
            box-shadow: 0 0 0 3px rgba(0,180,216,0.2);
        }
        .input-field::placeholder {
            color: rgba(255,255,255,0.5);
        }
        .login-btn {
            background: linear-gradient(135deg, #00b4d8, #0077b6);
            border-radius: 1rem;
            padding: 0.875rem;
            font-weight: bold;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .login-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 10px 25px -5px rgba(0,180,216,0.3);
        }
        .icon-box {
            width: 70px;
            height: 70px;
            background: linear-gradient(135deg, #00b4d8, #0077b6);
            border-radius: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.05); opacity: 0.8; }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        .footer-text {
            font-size: 0.75rem;
            color: rgba(255,255,255,0.4);
            text-align: center;
            margin-top: 2rem;
        }
    </style>
</head>
<body>
    <div class="animated-bg" id="bgAnimation"></div>
    <div class="relative z-10 min-h-screen flex items-center justify-center p-4">
        <div class="login-card w-full max-w-md p-8">
            <div class="text-center mb-8">
                <div class="icon-box pulse">
                    <i class="fas fa-chart-line text-4xl text-white"></i>
                </div>
                <h1 class="text-3xl font-bold text-white mb-2">البرنامج الذكي</h1>
                <p class="text-cyan-300">لإدارة المبيعات ونقاط البيع</p>
                <div class="w-20 h-1 bg-gradient-to-r from-cyan-400 to-blue-600 mx-auto mt-4 rounded-full"></div>
            </div>
            <form id="loginForm" class="space-y-5">
                <div>
                    <label class="block text-white text-sm font-medium mb-2">
                        <i class="fas fa-user ml-2 text-cyan-400"></i> اسم المستخدم
                    </label>
                    <input type="text" id="username" required placeholder="أدخل اسم المستخدم" class="input-field w-full">
                </div>
                <div>
                    <label class="block text-white text-sm font-medium mb-2">
                        <i class="fas fa-lock ml-2 text-cyan-400"></i> كلمة المرور
                    </label>
                    <input type="password" id="password" required placeholder="••••••••" class="input-field w-full">
                </div>
                <button type="submit" class="login-btn w-full text-white">
                    <i class="fas fa-sign-in-alt ml-2"></i> تسجيل الدخول
                </button>
            </form>
            <div id="errorMsg" class="text-red-400 text-center mt-4 text-sm"></div>
            <div class="footer-text">
                <p>جميع الحقوق محفوظة © علي حسين المسلم - 0546446382</p>
            </div>
        </div>
    </div>
    <script>
        const bgAnimation = document.getElementById('bgAnimation');
        const shapesCount = 30;
        for (let i = 0; i < shapesCount; i++) {
            const shape = document.createElement('span');
            const size = Math.random() * 30 + 10;
            const left = Math.random() * 100;
            const duration = Math.random() * 20 + 10;
            const delay = Math.random() * 10;
            shape.style.width = size + 'px';
            shape.style.height = size + 'px';
            shape.style.left = left + '%';
            shape.style.animationDuration = duration + 's';
            shape.style.animationDelay = delay + 's';
            shape.style.background = `rgba(${Math.random() * 100 + 100}, ${Math.random() * 100 + 100}, ${Math.random() * 100 + 150}, ${Math.random() * 0.1 + 0.05})`;
            bgAnimation.appendChild(shape);
        }
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.querySelector('.login-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin ml-2"></i> جاري التحقق...';
            btn.disabled = true;
            try {
                const res = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('username').value,
                        password: document.getElementById('password').value
                    })
                });
                const data = await res.json();
                if (data.success) {
                    window.location.href = data.redirect;
                } else {
                    document.getElementById('errorMsg').innerText = data.error;
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            } catch (err) {
                document.getElementById('errorMsg').innerText = 'خطأ في الاتصال بالخادم';
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });
        document.getElementById('password').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.querySelector('.login-btn').click();
            }
        });
    </script>
</body>
</html>
'''

# ==================== Routes ====================
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return LOGIN_PAGE

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        login_user(user)
        log_activity(user, "تسجيل دخول", f"تسجيل دخول من {request.remote_addr}")
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    return jsonify({'success': False, 'error': 'بيانات الدخول غير صحيحة'}), 401

@app.route('/dashboard')
@login_required
def dashboard():
    is_admin = current_user.role == 'admin'
    if is_admin:
        balance, total_assets, total_liabilities, total_debt, total_commission = calculate_balance()
        balance_class = "balance-positive" if balance > 0 else ("balance-negative" if balance < 0 else "balance-zero")
        balance_text = "فائض" if balance > 0 else ("عجز" if balance < 0 else "متزن")
        total_net_profit = db.session.query(func.sum(Sale.net_profit)).scalar() or 0
        admin_stats = f'''
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-6 mt-2">
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-building text-2xl lg:text-3xl text-purple-400"></i><span class="text-xs lg:text-sm text-gray-400">رأس المال</span></div><h2 class="text-xl lg:text-3xl font-bold text-purple-400" id="capitalBase">0.00</h2><p class="text-xs text-gray-400 mt-1">ريال سعودي</p></div>
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-chart-simple text-2xl lg:text-3xl text-indigo-400"></i><span class="text-xs lg:text-sm text-gray-400">صافي الربح الفعلي</span></div><h2 class="text-xl lg:text-3xl font-bold text-indigo-400" id="netProfitActual">0.00</h2><p class="text-xs text-gray-400 mt-1">(سعر البيع - التكلفة)</p></div>
        </div>
        <div class="card rounded-2xl p-4 lg:p-6">
            <h2 class="text-xl lg:text-2xl font-bold mb-3 flex items-center gap-2"><i class="fas fa-scale-balanced text-cyan-400"></i> الموازنة</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <div class="bg-gray-800 rounded-xl p-2 lg:p-3"><p class="text-gray-400 text-xs lg:text-sm">إجمالي الأصول</p><p class="text-xl lg:text-2xl font-bold text-cyan-400" id="totalAssets">0.00</p><p class="text-xs text-gray-500">(محفظة + مديونية + عمولات)</p></div>
                <div class="bg-gray-800 rounded-xl p-2 lg:p-3"><p class="text-gray-400 text-xs lg:text-sm">إجمالي الخصوم</p><p class="text-xl lg:text-2xl font-bold text-purple-400" id="totalLiabilities">0.00</p><p class="text-xs text-gray-500">(رأس مال + أرباح)</p></div>
            </div>
            <div class="balance-card {balance_class} p-3"><p class="text-gray-400 text-xs lg:text-sm">الموازنة (الأصول - الخصوم)</p><p class="text-2xl lg:text-3xl font-bold {balance_class}" id="balanceValue">{balance:,.2f}</p><p class="text-xs">الحالة: {balance_text}</p></div>
        </div>
        '''
        wallet_url = '/api/wallet'
        balance_url = '/api/balance'
        netprofit_url = '/api/net-profit'
    else:
        admin_stats = ''
        wallet_url = '/api/wallet/cashier'
        balance_url = '#'
        netprofit_url = '#'
    
    content = f'''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">📊 لوحة التحكم</h1>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-6">
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-wallet text-2xl lg:text-3xl text-cyan-400"></i><span class="text-xs lg:text-sm text-gray-400">محفظة الشراء</span></div><h2 class="text-xl lg:text-3xl font-bold text-cyan-400" id="mainBalance">0.00</h2><p class="text-xs text-gray-400 mt-1">ريال سعودي</p></div>
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-hourglass-half text-2xl lg:text-3xl text-yellow-400"></i><span class="text-xs lg:text-sm text-gray-400">عمولات معلقة</span></div><h2 class="text-xl lg:text-3xl font-bold text-yellow-400" id="pendingCommission">0.00</h2><p class="text-xs text-gray-400 mt-1">ريال سعودي</p></div>
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-chart-line text-2xl lg:text-3xl text-green-400"></i><span class="text-xs lg:text-sm text-gray-400">الأرباح المحققة</span></div><h2 class="text-xl lg:text-3xl font-bold text-green-400" id="profits">0.00</h2><p class="text-xs text-gray-400 mt-1">ريال سعودي</p></div>
            <div class="card rounded-2xl p-3 lg:p-6"><div class="flex items-center justify-between mb-2"><i class="fas fa-chart-simple text-2xl lg:text-3xl text-indigo-400"></i><span class="text-xs lg:text-sm text-gray-400">صافي الربح الفعلي</span></div><h2 class="text-xl lg:text-3xl font-bold text-indigo-400" id="netProfitActual">0.00</h2><p class="text-xs text-gray-400 mt-1">(سعر البيع - التكلفة)</p></div>
        </div>
        {admin_stats}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3">🏆 أفضل المنتجات مبيعاً</h2><div id="topProducts" class="space-y-2"><div class="text-center text-gray-500 py-4">جاري التحميل...</div></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3">⭐ أفضل الموظفين أداءً</h2><div id="topEmployees" class="space-y-2"><div class="text-center text-gray-500 py-4">جاري التحميل...</div></div></div>
        </div>
        <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3">⚠️ المنتجات المنتهية الصلاحية</h2><div id="expiredProducts" class="space-y-2"><div class="text-center text-gray-500 py-4">جاري التحميل...</div></div></div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-lg lg:text-xl font-bold mb-3">📈 المبيعات اليومية (آخر 7 أيام)</h2><canvas id="dailySalesChart" height="200"></canvas></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-lg lg:text-xl font-bold mb-3">🥧 توزيع المبيعات حسب المنتج</h2><canvas id="productPieChart" height="200"></canvas></div>
        </div>
    </div>
    <script>
        async function loadWallet() {{
            try {{ 
                const res = await fetch('{wallet_url}'); 
                const data = await res.json();
                document.getElementById('mainBalance').innerHTML = data.main_balance.toFixed(2);
                document.getElementById('pendingCommission').innerHTML = data.pending_commission.toFixed(2);
                document.getElementById('profits').innerHTML = data.profits.toFixed(2);
                {f"document.getElementById('capitalBase').innerHTML = data.capital_base.toFixed(2);" if is_admin else ""}
                {f"const balanceRes = await fetch('{balance_url}'); const balanceData = await balanceRes.json(); document.getElementById('totalAssets').innerHTML = balanceData.total_assets.toFixed(2); document.getElementById('totalLiabilities').innerHTML = balanceData.total_liabilities.toFixed(2); document.getElementById('balanceValue').innerHTML = balanceData.balance.toFixed(2);" if is_admin else ""}
                {f"const netProfit = await fetch('{netprofit_url}').then(r=>r.json()); document.getElementById('netProfitActual').innerHTML = netProfit.toFixed(2);" if is_admin else ""}
            }} catch(e) {{ console.error(e); }} 
        }}
        async function loadAdvancedStats() {{
            try {{
                const res = await fetch('/api/advanced-stats');
                const data = await res.json();
                const topProductsDiv = document.getElementById('topProducts');
                if(data.top_products && data.top_products.length > 0) {{
                    topProductsDiv.innerHTML = data.top_products.map((p, idx) => `<div class="bg-gray-800 rounded-xl p-2 lg:p-3 flex justify-between items-center"><div><span class="text-cyan-400 font-bold ml-2">${{idx+1}}</span> ${{p.name}}</div><div><span class="text-green-400">${{p.count}}</span> فاتورة</div></div>`).join('');
                }} else {{
                    topProductsDiv.innerHTML = '<div class="text-center text-gray-500 py-4">لا توجد مبيعات بعد</div>';
                }}
                const topEmployeesDiv = document.getElementById('topEmployees');
                if(data.top_employees && data.top_employees.length > 0) {{
                    topEmployeesDiv.innerHTML = data.top_employees.map((e, idx) => `<div class="bg-gray-800 rounded-xl p-2 lg:p-3 flex justify-between items-center"><div><span class="text-cyan-400 font-bold ml-2">${{idx+1}}</span> ${{e.name}}</div><div><span class="text-yellow-400">${{e.count}}</span> فاتورة</div></div>`).join('');
                }} else {{
                    topEmployeesDiv.innerHTML = '<div class="text-center text-gray-500 py-4">لا توجد مبيعات بعد</div>';
                }}
            }} catch(e) {{ console.error(e); }}
        }}
        async function loadExpiredProducts() {{
            try {{
                const res = await fetch('/api/expired-products');
                const expired = await res.json();
                const expiredDiv = document.getElementById('expiredProducts');
                if(expired.length > 0) {{
                    expiredDiv.innerHTML = expired.map(p => `<div class="bg-red-900/30 rounded-xl p-2 lg:p-3 flex justify-between items-center border-r-2 border-red-500"><div><span class="font-bold">${{p.product}}</span><br><span class="text-xs text-gray-400">فاتورة: ${{p.order_id}} | عميل: ${{p.customer}}</span></div><div class="text-red-400 text-xs lg:text-sm">تاريخ الانتهاء: ${{p.expiry_date}}</div></div>`).join('');
                }} else {{
                    expiredDiv.innerHTML = '<div class="text-center text-green-400 py-4">✅ لا توجد منتجات منتهية الصلاحية</div>';
                }}
            }} catch(e) {{ console.error(e); }}
        }}
        async function loadCharts() {{
            try {{
                const res = await fetch('/api/charts-data');
                const data = await res.json();
                new Chart(document.getElementById('dailySalesChart'), {{
                    type: 'line',
                    data: {{ labels: data.daily_labels, datasets: [{{ label: 'إجمالي المبيعات (ريال)', data: data.daily_totals, borderColor: '#00b4d8', backgroundColor: 'rgba(0,180,216,0.1)', tension: 0.3, fill: true }}] }},
                    options: {{ responsive: true, maintainAspectRatio: true }}
                }});
                new Chart(document.getElementById('productPieChart'), {{
                    type: 'pie',
                    data: {{ labels: data.product_labels, datasets: [{{ data: data.product_counts, backgroundColor: ['#00b4d8', '#06d6a0', '#ffd166', '#ef476f', '#7209b7'] }}] }},
                    options: {{ responsive: true, maintainAspectRatio: true }}
                }});
            }} catch(e) {{ console.error(e); }}
        }}
        loadWallet(); loadAdvancedStats(); loadExpiredProducts(); loadCharts();
    </script>
    '''
    company = get_company_info()
    site_title = company.name if company.name else "البرنامج الذكي"
    return get_base_html(content, "لوحة التحكم", current_user.name, is_admin)

@app.route('/api/wallet/cashier')
@login_required
def api_wallet_cashier():
    if current_user.role != 'admin':
        w = get_wallet()
        return jsonify({'main_balance': w.main_balance, 'pending_commission': w.pending_commission, 'profits': 0, 'capital_base': 0})
    return jsonify({'error': 'unauthorized'}), 403

@app.route('/api/net-profit')
@admin_required
def api_net_profit():
    total = db.session.query(func.sum(Sale.net_profit)).scalar() or 0
    return jsonify(float(total))

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    if not current_user.check_password(old_password):
        return jsonify({'error': 'كلمة المرور الحالية غير صحيحة'}), 400
    if len(new_password) < 4:
        return jsonify({'error': 'كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل'}), 400
    current_user.set_password(new_password)
    db.session.commit()
    log_activity(current_user, "تغيير كلمة المرور", "تم تغيير كلمة المرور بنجاح")
    return jsonify({'success': True})

@app.route('/activity-log')
@admin_required
def activity_log():
    content = '''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">📋 سجل العمليات</h1>
        <div class="card rounded-2xl p-4 lg:p-6">
            <h2 class="text-lg lg:text-xl font-bold mb-3">🔍 بحث متقدم</h2>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                <div><label class="block text-sm font-medium mb-1">نص البحث</label><input type="text" id="searchText" placeholder="إجراء أو تفاصيل..." class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                <div><label class="block text-sm font-medium mb-1">من تاريخ</label><input type="date" id="searchDateFrom" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                <div><label class="block text-sm font-medium mb-1">إلى تاريخ</label><input type="date" id="searchDateTo" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                <div><label class="block text-sm font-medium mb-1">اسم المستخدم</label><input type="text" id="searchUser" placeholder="اسم المستخدم" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            </div>
            <div class="flex gap-2 mb-4"><button id="searchBtn" class="btn-primary px-4 py-2 rounded-xl text-sm"><i class="fas fa-search ml-1"></i> بحث</button><button id="resetSearchBtn" class="btn-warning px-4 py-2 rounded-xl text-sm"><i class="fas fa-undo ml-1"></i> إعادة ضبط</button></div>
            <div class="overflow-x-auto"><table class="w-full min-w-[600px]"><thead><tr class="border-b border-gray-700"><th class="py-2 px-2 text-sm">التاريخ والوقت</th><th class="py-2 px-2 text-sm">المستخدم</th><th class="py-2 px-2 text-sm">الإجراء</th><th class="py-2 px-2 text-sm">التفاصيل</th><th class="py-2 px-2 text-sm">عنوان IP</th></tr></thead><tbody id="logsTable"><tr><td colspan="5" class="text-center py-8 text-gray-500">جاري التحميل...</td></tr></tbody></table></div>
        </div>
    </div>
    <script>
        async function searchLogs() {
            const params = new URLSearchParams();
            const searchText = document.getElementById('searchText').value;
            const dateFrom = document.getElementById('searchDateFrom').value;
            const dateTo = document.getElementById('searchDateTo').value;
            const user = document.getElementById('searchUser').value;
            if(searchText) params.append('q', searchText);
            if(dateFrom) params.append('date_from', dateFrom);
            if(dateTo) params.append('date_to', dateTo);
            if(user) params.append('user', user);
            try {
                const res = await fetch(`/api/activity-log/search?${params.toString()}`);
                const logs = await res.json();
                const tbody = document.getElementById('logsTable');
                if(logs.length === 0) { tbody.innerHTML='<tr><td colspan="5" class="text-center py-8 text-gray-500">لا توجد سجلات</td></tr>'; return; }
                tbody.innerHTML = logs.map(log => `<tr class="border-b border-gray-800 hover:bg-gray-800/50"><td class="py-2 px-2 text-sm">${log.timestamp}</td><td class="py-2 px-2 text-sm">${log.user_name}</td><td class="py-2 px-2 text-sm">${log.action}</td><td class="py-2 px-2 text-sm">${log.details}</td><td class="py-2 px-2 text-sm">${log.ip_address}</td></tr>`).join('');
            } catch(e) { showToast('خطأ في البحث', 'error'); }
        }
        document.getElementById('searchBtn').onclick = searchLogs;
        document.getElementById('resetSearchBtn').onclick = () => { document.getElementById('searchText').value = ''; document.getElementById('searchDateFrom').value = ''; document.getElementById('searchDateTo').value = ''; document.getElementById('searchUser').value = ''; searchLogs(); };
        searchLogs();
    </script>
    '''
    return get_base_html(content, "سجل العمليات", current_user.name, True)

@app.route('/products')
@login_required
def products():
    is_admin = current_user.role == 'admin'
    if is_admin:
        admin_columns = '''
                <th class="text-right py-2 px-2">التكلفة</th><th class="text-right py-2 px-2">العمولة</th><th class="text-right py-2 px-2">السعر الشامل</th><th class="text-right py-2 px-2">الربح</th>
        '''
        admin_actions = '<th class="text-right py-2 px-2">الإجراءات</th>'
        add_product_form = '''
        <div class="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <div><label class="block text-sm font-medium mb-1">اسم المنتج *</label><input type="text" id="productName" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <div><label class="block text-sm font-medium mb-1">التكلفة (ريال) *</label><input type="number" id="productCost" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <div><label class="block text-sm font-medium mb-1">العمولة (ريال) *</label><input type="number" id="productCommission" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <div><label class="block text-sm font-medium mb-1">سعر البيع (ريال) *</label><input type="number" id="productPrice" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <div><label class="block text-sm font-medium mb-1">السعر الشامل *</label><input type="number" id="productTotal" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <div><label class="block text-sm font-medium mb-1">📅 مدة الصلاحية (شهور)</label><input type="number" id="productExpiry" step="1" value="0" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        </div>
        <button id="addProductBtn" class="btn-success mt-3 px-4 py-2 rounded-xl font-bold text-sm"><i class="fas fa-plus ml-1"></i> إضافة المنتج</button>
        '''
        edit_product_fields = '''
        <div class="space-y-2"><div><label class="block text-sm font-medium mb-1">اسم المنتج</label><input type="text" id="editName" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        <div><label class="block text-sm font-medium mb-1">التكلفة</label><input type="number" id="editCost" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        <div><label class="block text-sm font-medium mb-1">العمولة</label><input type="number" id="editCommission" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        <div><label class="block text-sm font-medium mb-1">سعر البيع</label><input type="number" id="editPrice" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        <div><label class="block text-sm font-medium mb-1">السعر الشامل</label><input type="number" id="editTotal" step="0.01" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        <div><label class="block text-sm font-medium mb-1">مدة الصلاحية (شهور)</label><input type="number" id="editExpiry" step="1" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
        </div>
        '''
    else:
        admin_columns = ''
        admin_actions = ''
        add_product_form = '<div class="text-yellow-400 p-3 text-center">👋 غير مسموح بإضافة أو تعديل المنتجات. يمكنك فقط عرض المنتجات.</div>'
        edit_product_fields = '<div>غير مسموح بالتعديل</div>'
    
    content = f'''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">📦 إدارة المنتجات</h1>
        <div class="card rounded-2xl p-4 lg:p-6">
            <h2 class="text-xl lg:text-2xl font-bold mb-3">➕ إضافة منتج جديد</h2>
            {add_product_form}
        </div>
        <div class="card rounded-2xl p-4 lg:p-6">
            <div class="flex justify-between items-center mb-3 flex-wrap gap-2">
                <h2 class="text-xl lg:text-2xl font-bold">📋 قائمة المنتجات</h2>
                <div class="flex gap-2"><input type="text" id="productSearch" placeholder="🔍 بحث باسم المنتج..." class="px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 w-48 text-sm"><button id="refreshBtn" class="btn-primary px-3 py-2 rounded-xl text-sm"><i class="fas fa-sync-alt ml-1"></i> تحديث</button></div>
            </div>
            <div id="productsLoading" class="text-center py-8 text-gray-400">جاري تحميل المنتجات...</div>
            <div class="overflow-x-auto"><table class="w-full min-w-[800px]" id="productsTable" style="display: none;"><thead><tr class="border-b border-gray-700"><th class="text-right py-2 px-2">#</th><th class="text-right py-2 px-2">المنتج</th>{admin_columns}<th class="text-right py-2 px-2">سعر البيع</th><th class="text-right py-2 px-2">الصلاحية</th>{admin_actions}</tr></thead><tbody id="productsTableBody"></tbody></table></div>
        </div>
    </div>
    {'<div class="modal-overlay" id="editProductModal"><div class="modal-container"><h2 class="text-xl font-bold mb-3">✏️ تعديل المنتج</h2><input type="hidden" id="editProductId">'+edit_product_fields+'<div class="flex gap-2 mt-3"><button id="saveEditBtn" class="btn-primary flex-1 py-2 rounded-xl text-sm"><i class="fas fa-save ml-1"></i> حفظ</button><button id="closeEditModal" class="btn-danger flex-1 py-2 rounded-xl text-sm"><i class="fas fa-times ml-1"></i> إلغاء</button></div></div></div>' if is_admin else ''}
    <script>
        let allProducts = [];
        async function loadProducts() {{
            try {{
                document.getElementById('productsLoading').style.display = 'block';
                document.getElementById('productsTable').style.display = 'none';
                const res = await fetch('/api/products');
                if(!res.ok) throw new Error('فشل تحميل المنتجات');
                allProducts = await res.json();
                renderProducts(allProducts);
                document.getElementById('productsLoading').style.display = 'none';
                document.getElementById('productsTable').style.display = 'table';
            }} catch(e){{ console.error(e); document.getElementById('productsLoading').innerHTML = '<div class="text-red-400 text-center py-4">❌ خطأ في تحميل المنتجات</div>'; showToast('خطأ في تحميل المنتجات', 'error'); }}
        }}
        function escapeHtml(str) {{ return str.replace(/[&<>]/g, function(m) {{ if(m === '&') return '&amp;'; if(m === '<') return '&lt;'; if(m === '>') return '&gt;'; return m; }}); }}
        function renderProducts(products) {{
            const tbody = document.getElementById('productsTableBody');
            if(products.length === 0){{ tbody.innerHTML = '<tr><td colspan="10" class="text-center py-8 text-gray-500">لا توجد منتجات</td></tr>'; return; }}
            const isAdmin = {str(is_admin).lower()};
            tbody.innerHTML = products.map((p, idx) => {{
                let cols = `<td class="py-2 px-2">${{idx+1}}</td><td class="py-2 px-2 font-bold text-cyan-400">${{escapeHtml(p.name)}}</td>`;
                if(isAdmin) {{
                    cols += `<td class="py-2 px-2 text-yellow-400">${{p.cost.toFixed(2)}}</td><td class="py-2 px-2 text-cyan-400">${{p.commission.toFixed(2)}}</td><td class="py-2 px-2 text-blue-400">${{p.total_price.toFixed(2)}}</td><td class="py-2 px-2 text-purple-400">${{(p.selling_price - p.cost).toFixed(2)}}</td>`;
                }}
                cols += `<td class="py-2 px-2 text-green-400">${{p.selling_price.toFixed(2)}}</td><td class="py-2 px-2">${{p.expiry_months || 0}} شهر</td>`;
                if(isAdmin) {{
                    cols += `<td class="py-2 px-2"><button onclick="openEditModal(${{p.id}}, '${{escapeHtml(p.name)}}', ${{p.cost}}, ${{p.commission}}, ${{p.selling_price}}, ${{p.total_price}}, ${{p.expiry_months}})" class="btn-warning px-2 py-1 rounded-lg text-xs ml-1"><i class="fas fa-edit"></i> تعديل</button><button onclick="deleteProduct(${{p.id}}, '${{escapeHtml(p.name)}}')" class="btn-danger px-2 py-1 rounded-lg text-xs"><i class="fas fa-trash"></i> حذف</button></td>`;
                }}
                return `<tr class="border-b border-gray-800 hover:bg-gray-800/50">${{cols}}</tr>`;
            }}).join('');
        }}
        {'window.openEditModal = (id, name, cost, commission, price, total, expiry) => {{ document.getElementById("editProductId").value = id; document.getElementById("editName").value = name; document.getElementById("editCost").value = cost; document.getElementById("editCommission").value = commission; document.getElementById("editPrice").value = price; document.getElementById("editTotal").value = total; document.getElementById("editExpiry").value = expiry; document.getElementById("editProductModal").style.display = "flex"; setTimeout(()=>document.querySelector("#editProductModal .modal-container").classList.add("active"),10); }}; document.getElementById("closeEditModal").onclick = () => {{ document.getElementById("editProductModal").style.display = "none"; document.querySelector("#editProductModal .modal-container").classList.remove("active"); }}; document.getElementById("saveEditBtn").onclick = async () => {{ const id = document.getElementById("editProductId").value; const newName = document.getElementById("editName").value.trim(); const newCost = parseFloat(document.getElementById("editCost").value); const newCommission = parseFloat(document.getElementById("editCommission").value); const newPrice = parseFloat(document.getElementById("editPrice").value); const newTotal = parseFloat(document.getElementById("editTotal").value); const newExpiry = parseInt(document.getElementById("editExpiry").value) || 0; if(!newName || isNaN(newCost) || isNaN(newCommission) || isNaN(newPrice) || isNaN(newTotal)) {{ showToast("الرجاء تعبئة جميع الحقول بشكل صحيح", "error"); return; }} if(newCost <= 0 || newCommission < 0 || newPrice <= 0 || newTotal <= 0) {{ showToast("القيم يجب أن تكون أرقاماً موجبة", "error"); return; }} try {{ const res = await fetch(`/api/products/${{id}}`, {{ method: "PUT", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{ name: newName, cost: newCost, commission: newCommission, selling_price: newPrice, total_price: newTotal, expiry_months: newExpiry }}) }}); if(res.ok) {{ showToast("✅ تم تعديل المنتج بنجاح", "success"); document.getElementById("closeEditModal").click(); loadProducts(); }} else {{ const error = await res.json(); showToast(error.error || "فشل التعديل", "error"); }} }} catch(e) {{ showToast("خطأ في الاتصال", "error"); }} }};' if is_admin else ''}
        document.getElementById('productSearch').addEventListener('input', function(e) {{ const searchTerm = e.target.value.toLowerCase().trim(); if(searchTerm === '') renderProducts(allProducts); else {{ const filtered = allProducts.filter(p => p.name.toLowerCase().includes(searchTerm)); renderProducts(filtered); }} }});
        {'window.deleteProduct = async (id, name) => {{ if(confirm(`⚠️ هل أنت متأكد من حذف المنتج "${{name}}"؟`)){{ try {{ const res = await fetch(`/api/products/${{id}}`, {{ method: "DELETE" }}); if(res.ok){{ showToast(`✅ تم حذف المنتج "${{name}}"`, "success"); loadProducts(); }} else {{ showToast("فشل حذف المنتج", "error"); }} }} catch(e) {{ showToast("خطأ في الاتصال", "error"); }} }} }}; document.getElementById("addProductBtn").onclick = async () => {{ const name = document.getElementById("productName").value.trim(); const cost = parseFloat(document.getElementById("productCost").value); const commission = parseFloat(document.getElementById("productCommission").value); const price = parseFloat(document.getElementById("productPrice").value); const total = parseFloat(document.getElementById("productTotal").value); const expiry_months = parseInt(document.getElementById("productExpiry").value) || 0; if(!name || isNaN(cost) || isNaN(commission) || isNaN(price) || isNaN(total)) {{ showToast("الرجاء تعبئة جميع الحقول", "error"); return; }} if(cost <= 0 || commission < 0 || price <= 0 || total <= 0) {{ showToast("القيم يجب أن تكون أرقاماً موجبة", "error"); return; }} try {{ const res = await fetch("/api/products", {{ method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{name, cost, commission, selling_price: price, total_price: total, expiry_months}}) }}); if(res.ok) {{ showToast(`✅ تمت إضافة المنتج "${{name}}"`, "success"); document.getElementById("productName").value = ""; document.getElementById("productCost").value = ""; document.getElementById("productCommission").value = ""; document.getElementById("productPrice").value = ""; document.getElementById("productTotal").value = ""; document.getElementById("productExpiry").value = "0"; loadProducts(); }} else {{ const error = await res.json(); showToast(error.error || "فشل الإضافة", "error"); }} }} catch(e) {{ showToast("خطأ في الاتصال", "error"); }} }};' if is_admin else ''}
        document.getElementById('refreshBtn').onclick = loadProducts;
        loadProducts();
    </script>
    '''
    return get_base_html(content, "المنتجات", current_user.name, is_admin)

@app.route('/sales')
@login_required
def sales():
    default_note = get_default_invoice_note()
    content = f'''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">🛒 شاشة البيع</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6">
                <h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-file-invoice text-cyan-400"></i> إنشاء فاتورة جديدة</h2>
                <form id="saleForm" class="space-y-3">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3"><div><label class="block text-sm font-medium mb-1">📄 رقم الفاتورة *</label><input type="text" id="orderId" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div><label class="block text-sm font-medium mb-1">👤 الموظف *</label><select id="employee" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">اختر الموظف</option></select></div></div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3"><div><label class="block text-sm font-medium mb-1">👤 اسم العميل *</label><input type="text" id="customerName" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div><label class="block text-sm font-medium mb-1">📞 رقم الجوال *</label><input type="tel" id="customerPhone" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div></div>
                    <div><label class="block text-sm font-medium mb-1">🆔 رقم الهوية (اختياري)</label><input type="text" id="customerId" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3"><div><label class="block text-sm font-medium mb-1">📦 المنتج *</label><select id="product" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">اختر المنتج</option></select></div><div><label class="block text-sm font-medium mb-1">💰 سعر البيع *</label><input type="number" id="sellingPrice" step="0.01" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div></div>
                    <div><label class="block text-sm font-medium mb-1">📅 تاريخ انتهاء الصلاحية</label><input type="text" id="expiryDate" readonly class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 opacity-70 text-sm"></div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3"><div><label class="block text-sm font-medium mb-1">📍 الفرع *</label><select id="branch" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">اختر الفرع</option></select></div><div><label class="block text-sm font-medium mb-1">📡 مصدر التفعيل *</label><select id="channel" required class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">اختر المصدر</option></select></div></div>
                    <div><label class="block text-sm font-medium mb-1">💳 طريقة الدفع *</label><div class="grid grid-cols-3 gap-2"><button type="button" data-payment="مدى / شبكة" class="payment-btn py-2 rounded-xl text-sm hover:border-cyan-500">💳 مدى / شبكة</button><button type="button" data-payment="كاش" class="payment-btn py-2 rounded-xl text-sm hover:border-cyan-500">💵 كاش</button><button type="button" data-payment="تحويل بنكي" class="payment-btn py-2 rounded-xl text-sm hover:border-cyan-500">🏦 تحويل بنكي</button></div><input type="hidden" id="paymentMethod" required></div>
                    <div><label class="block text-sm font-medium mb-1">📝 ملاحظات</label><textarea id="notes" rows="2" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm">{default_note}</textarea></div>
                    <div class="flex gap-2"><button type="submit" class="btn-primary flex-1 py-2 rounded-xl font-bold text-sm"><i class="fas fa-save ml-1"></i> حفظ الفاتورة</button><button type="button" id="resetBtn" class="btn-danger px-4 py-2 rounded-xl font-bold text-sm"><i class="fas fa-eraser ml-1"></i> تصفير</button></div>
                </form>
            </div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-boxes text-cyan-400"></i> اختر المنتج</h2><div class="grid grid-cols-2 gap-2 max-h-[500px] overflow-y-auto" id="productsGrid"><div class="col-span-2 text-center text-gray-500 py-8">جاري تحميل المنتجات...</div></div></div>
        </div>
    </div>
    <script>
        let selectedProduct = null, selectedPayment = null;
        function updateExpiryDate(expiryMonths) {{ if(expiryMonths > 0) {{ const expiryDate = new Date(); expiryDate.setMonth(expiryDate.getMonth() + expiryMonths); document.getElementById('expiryDate').value = expiryDate.toLocaleDateString('ar-SA'); }} else {{ document.getElementById('expiryDate').value = 'لا يوجد صلاحية'; }} }}
        async function loadSalesData() {{
            try {{
                const [products, employees, branches, channels] = await Promise.all([ fetch('/api/products').then(r=>r.json()), fetch('/api/employees').then(r=>r.json()), fetch('/api/branches').then(r=>r.json()), fetch('/api/channels').then(r=>r.json()) ]);
                const productSelect = document.getElementById('product');
                productSelect.innerHTML = '<option value="">اختر المنتج</option>' + products.map(p=>`<option value="${{p.name}}" data-cost="${{p.cost}}" data-commission="${{p.commission}}" data-price="${{p.selling_price}}" data-expiry="${{p.expiry_months||0}}">${{p.name}}</option>`).join('');
                document.getElementById('employee').innerHTML = '<option value="">اختر الموظف</option>' + employees.map(e=>`<option value="${{e.name}}">${{e.name}}</option>`).join('');
                document.getElementById('branch').innerHTML = '<option value="">اختر الفرع</option>' + branches.map(b=>`<option value="${{b.name}}">${{b.name}}</option>`).join('');
                document.getElementById('channel').innerHTML = '<option value="">اختر المصدر</option>' + channels.map(c=>`<option value="${{c.name}}">${{c.name}}</option>`).join('');
                const grid = document.getElementById('productsGrid');
                grid.innerHTML = products.map(p=>`<div class="product-card p-3 rounded-xl text-center" data-name="${{p.name}}" data-cost="${{p.cost}}" data-commission="${{p.commission}}" data-price="${{p.selling_price}}" data-expiry="${{p.expiry_months||0}}"><div class="font-bold text-sm">${{p.name}}</div><div class="text-cyan-400 text-lg font-bold mt-1">${{p.selling_price.toFixed(2)}} ريال</div>${{p.expiry_months>0?`<div class="text-xs text-yellow-400 mt-1">📅 صلاحية ${{p.expiry_months}} شهر</div>`:''}}</div>`).join('');
                document.querySelectorAll('.product-card').forEach(card => {{ card.onclick = () => {{ document.querySelectorAll('.product-card').forEach(c=>c.classList.remove('selected')); card.classList.add('selected'); selectedProduct = {{ name: card.dataset.name, cost: parseFloat(card.dataset.cost), commission: parseFloat(card.dataset.commission), price: parseFloat(card.dataset.price), expiry: parseInt(card.dataset.expiry) }}; document.getElementById('product').value = selectedProduct.name; document.getElementById('sellingPrice').value = selectedProduct.price; updateExpiryDate(selectedProduct.expiry); }}; }});
            }} catch(e) {{ showToast('خطأ في التحميل','error'); }} }}
        document.getElementById('product').onchange = (e) => {{ const opt = e.target.selectedOptions[0]; if(opt && opt.value) {{ selectedProduct = {{ name: opt.value, cost: parseFloat(opt.dataset.cost), commission: parseFloat(opt.dataset.commission), price: parseFloat(opt.dataset.price), expiry: parseInt(opt.dataset.expiry) }}; document.getElementById('sellingPrice').value = selectedProduct.price; updateExpiryDate(selectedProduct.expiry); document.querySelectorAll('.product-card').forEach(c=>c.classList.remove('selected')); }} }};
        document.querySelectorAll('.payment-btn').forEach(btn => {{ btn.onclick = () => {{ document.querySelectorAll('.payment-btn').forEach(b=>b.classList.remove('selected','border-cyan-500','bg-cyan-500/20')); btn.classList.add('selected','border-cyan-500','bg-cyan-500/20'); selectedPayment = btn.dataset.payment; document.getElementById('paymentMethod').value = selectedPayment; }}; }});
        document.getElementById('resetBtn').onclick = () => {{ document.getElementById('saleForm').reset(); selectedProduct = null; selectedPayment = null; document.getElementById('paymentMethod').value = ''; document.getElementById('expiryDate').value = ''; document.querySelectorAll('.product-card').forEach(c=>c.classList.remove('selected')); document.querySelectorAll('.payment-btn').forEach(b=>b.classList.remove('selected','border-cyan-500','bg-cyan-500/20')); showToast('تم تصفير جميع المدخلات','info'); }};
        document.getElementById('saleForm').onsubmit = async (e) => {{ e.preventDefault(); const formData = {{ order_id: document.getElementById('orderId').value, customer_name: document.getElementById('customerName').value, customer_phone: document.getElementById('customerPhone').value, customer_id: document.getElementById('customerId').value, product: document.getElementById('product').value, cost: selectedProduct?.cost || 0, commission: selectedProduct?.commission || 0, selling_price: parseFloat(document.getElementById('sellingPrice').value), total_price: parseFloat(document.getElementById('sellingPrice').value), employee: document.getElementById('employee').value, branch: document.getElementById('branch').value, channel: document.getElementById('channel').value, payment_method: document.getElementById('paymentMethod').value, notes: document.getElementById('notes').value, expiry_months: selectedProduct?.expiry || 0 }}; const required = ['order_id','customer_name','customer_phone','product','selling_price','employee','branch','channel','payment_method']; for(let f of required) if(!formData[f]) {{ showToast(`الرجاء تعبئة حقل ${{f.replace('_',' ')}}`,'error'); return; }} if(!selectedProduct) {{ showToast('الرجاء اختيار منتج','error'); return; }} try {{ const res = await fetch('/api/sale', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(formData) }}); const result = await res.json(); if(result.success) {{ showToast(`✅ تم حفظ الفاتورة رقم ${{result.order_id}}`, 'success'); document.getElementById('resetBtn').click(); if(confirm('هل تريد طباعة الفاتورة؟')) window.open(`/api/invoice/print/${{result.order_id}}`, '_blank'); }} else showToast(result.error, 'error'); }} catch(e) {{ showToast('خطأ في الاتصال','error'); }} }};
        loadSalesData();
    </script>
    '''
    return get_base_html(content, "شاشة البيع", current_user.name, current_user.role == 'admin')

@app.route('/reports')
@login_required
def reports():
    is_admin = current_user.role == 'admin'
    column_selector = '''
    <div id="columnSelectorModal" class="modal-overlay">
        <div class="modal-container max-w-lg">
            <h2 class="text-xl font-bold mb-3 flex items-center gap-2"><i class="fas fa-columns text-cyan-400"></i> اختيار الأعمدة للتصدير/الطباعة</h2>
            <div class="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto mb-4">
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="date" checked> التاريخ</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="order_id" checked> رقم الطلب</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="customer_name" checked> اسم العميل</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="customer_phone" checked> رقم الجوال</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="product_name" checked> المنتج</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="branch_name" checked> الفرع</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="employee_name" checked> الموظف</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="selling_price" checked> سعر البيع</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="payment_method" checked> طريقة الدفع</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="channel_name"> مصدر التفعيل</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="notes"> الملاحظات</label>
                ''' + ('''<label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="cost"> التكلفة</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="commission"> العمولة</label>
                <label class="checkbox-group flex items-center gap-2"><input type="checkbox" value="net_profit"> صافي الربح</label>''' if is_admin else '') + '''
            </div>
            <div class="flex gap-2">
                <button id="confirmExportExcel" class="btn-success flex-1 py-2 rounded-xl"><i class="fas fa-file-excel ml-1"></i> تصدير Excel</button>
                <button id="confirmPrintReport" class="btn-primary flex-1 py-2 rounded-xl"><i class="fas fa-print ml-1"></i> طباعة</button>
                <button id="closeColumnSelector" class="bg-gray-600 px-4 py-2 rounded-xl"><i class="fas fa-times"></i> إلغاء</button>
            </div>
        </div>
    </div>
    '''
    
    content = f'''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">📊 التقارير المتقدمة</h1>
        <div class="card rounded-2xl p-4 lg:p-6">
            <h2 class="text-xl lg:text-2xl font-bold mb-3">🔍 فلترة التقارير</h2>
            <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-3">
                <div><label class="block text-sm font-medium mb-1">📅 من تاريخ</label><input type="date" id="dateFrom" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                <div><label class="block text-sm font-medium mb-1">📅 إلى تاريخ</label><input type="date" id="dateTo" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
                <div><label class="block text-sm font-medium mb-1">📍 الفرع</label><select id="filterBranch" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">الكل</option></select></div>
                <div><label class="block text-sm font-medium mb-1">👤 الموظف</label><select id="filterEmployee" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">الكل</option></select></div>
                <div><label class="block text-sm font-medium mb-1">📞 رقم الجوال</label><input type="text" id="filterPhone" placeholder="رقم الجوال" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            </div>
            <div class="flex gap-2 flex-wrap"><button id="applyFilter" class="btn-primary px-4 py-2 rounded-xl text-sm"><i class="fas fa-search ml-1"></i> تطبيق</button><button id="resetFilter" class="btn-warning px-4 py-2 rounded-xl text-sm"><i class="fas fa-undo ml-1"></i> إعادة ضبط</button><button id="openColumnSelectorBtn" class="btn-success px-4 py-2 rounded-xl text-sm"><i class="fas fa-file-excel ml-1"></i> تصدير / طباعة متقدمة</button><button id="backupBtn" class="btn-success px-4 py-2 rounded-xl text-sm"><i class="fas fa-database ml-1"></i> نسخ احتياطي</button></div>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div class="stat-card"><i class="fas fa-file-invoice text-xl lg:text-3xl text-cyan-400 mb-1"></i><h3 class="text-sm lg:text-lg">عدد الفواتير</h3><p class="text-xl lg:text-2xl font-bold" id="statCount">0</p></div>
            <div class="stat-card"><i class="fas fa-chart-line text-xl lg:text-3xl text-green-400 mb-1"></i><h3 class="text-sm lg:text-lg">إجمالي المبيعات</h3><p class="text-xl lg:text-2xl font-bold" id="statTotalSales">0.00</p><p class="text-xs">سعر البيع</p></div>
            <div class="stat-card"><i class="fas fa-chart-line text-xl lg:text-3xl text-red-400 mb-1"></i><h3 class="text-sm lg:text-lg">إجمالي المشتريات</h3><p class="text-xl lg:text-2xl font-bold" id="statTotalPurchases">0.00</p><p class="text-xs">السعر الشامل</p></div>
            <div class="stat-card"><i class="fas fa-percent text-xl lg:text-3xl text-yellow-400 mb-1"></i><h3 class="text-sm lg:text-lg">إجمالي العمولات</h3><p class="text-xl lg:text-2xl font-bold" id="statCommission">0.00</p><p class="text-xs">ريال</p></div>
            {'<div class="stat-card"><i class="fas fa-chart-pie text-xl lg:text-3xl text-purple-400 mb-1"></i><h3 class="text-sm lg:text-lg">صافي الربح</h3><p class="text-xl lg:text-2xl font-bold" id="statProfit">0.00</p><p class="text-xs">(بيع + عمولة - شامل)</p></div>' if is_admin else '<div class="stat-card"></div>'}
        </div>
        <div class="card rounded-2xl p-4 lg:p-6">
            <div class="flex justify-between items-center mb-3 flex-wrap gap-2"><h2 class="text-xl lg:text-2xl font-bold">📋 قائمة المبيعات</h2><button id="refreshTable" class="btn-primary px-3 py-2 rounded-xl text-sm"><i class="fas fa-sync-alt ml-1"></i> تحديث</button></div>
            <div class="overflow-x-auto"><table class="w-full min-w-[800px]"><thead><tr id="tableHeader">{'<th>التاريخ</th><th>رقم الطلب</th><th>العميل</th><th>الجوال</th><th>المنتج</th><th>الفرع</th><th>الموظف</th><th>سعر البيع</th>' + ('<th>التكلفة</th><th>العمولة</th><th>صافي الربح</th>' if is_admin else '') + '<th>طباعة</th><th>واتساب</th><th>تعديل</th><th>حذف</th><tr>'}</thead><tbody id="reportsTable"><tr><td colspan="13" class="text-center py-8 text-gray-500">جاري التحميل...</td></tr></tbody></table></div>
        </div>
    </div>
    {column_selector}
    <script>
        const isAdmin = {str(is_admin).lower()};
        let currentSales = [];
        async function loadSalesData() {{ try {{ const res = await fetch('/api/sales-filtered'); currentSales = await res.json(); applyFilter(); }} catch(e) {{ showToast('خطأ في التحميل', 'error'); }} }}
        async function loadFilterOptions() {{ try {{ const [branches, employees] = await Promise.all([ fetch('/api/branches').then(r=>r.json()), fetch('/api/employees').then(r=>r.json()) ]); document.getElementById('filterBranch').innerHTML = '<option value="">الكل</option>' + branches.map(b=>`<option value="${{b.name}}">${{b.name}}</option>`).join(''); document.getElementById('filterEmployee').innerHTML = '<option value="">الكل</option>' + employees.map(e=>`<option value="${{e.name}}">${{e.name}}</option>`).join(''); }} catch(e) {{ console.error(e); }} }}
        function applyFilter() {{ const dateFrom = document.getElementById('dateFrom').value, dateTo = document.getElementById('dateTo').value, branch = document.getElementById('filterBranch').value, employee = document.getElementById('filterEmployee').value, phone = document.getElementById('filterPhone').value; let filtered = [...currentSales]; if(dateFrom) filtered = filtered.filter(s => s.date.split(' ')[0] >= dateFrom); if(dateTo) filtered = filtered.filter(s => s.date.split(' ')[0] <= dateTo); if(branch) filtered = filtered.filter(s => s.branch_name === branch); if(employee) filtered = filtered.filter(s => s.employee_name === employee); if(phone) filtered = filtered.filter(s => s.customer_phone.includes(phone)); updateStats(filtered); renderTable(filtered); }}
        function updateStats(filtered) {{ const count = filtered.length, totalSales = filtered.reduce((sum, s) => sum + s.selling_price, 0), totalPurchases = filtered.reduce((sum, s) => sum + (s.total_price || s.selling_price), 0), commission = filtered.reduce((sum, s) => sum + (s.commission || 0), 0), profit = filtered.reduce((sum, s) => sum + (s.selling_price + s.commission - (s.total_price || s.selling_price)), 0); document.getElementById('statCount').innerHTML = count; document.getElementById('statTotalSales').innerHTML = totalSales.toFixed(2); document.getElementById('statTotalPurchases').innerHTML = totalPurchases.toFixed(2); document.getElementById('statCommission').innerHTML = commission.toFixed(2); if(isAdmin) document.getElementById('statProfit').innerHTML = profit.toFixed(2); }}
        function renderTable(filtered) {{ const tbody = document.getElementById('reportsTable'); if(filtered.length === 0) {{ tbody.innerHTML='<tr><td colspan="13" class="text-center py-8 text-gray-500">لا توجد بيانات</td></tr>'; return; }} tbody.innerHTML = filtered.map(s => {{
            let row = `<tr class="border-b border-gray-800 hover:bg-gray-800/50"><td class="py-2 px-2 text-sm">${{s.date}}</td><td class="py-2 px-2 text-sm font-bold text-cyan-400">${{s.order_id}}</td><td class="py-2 px-2 text-sm">${{s.customer_name}}</td><td class="py-2 px-2 text-sm">${{s.customer_phone}}</td><td class="py-2 px-2 text-sm">${{s.product_name}}</td><td class="py-2 px-2 text-sm">${{s.branch_name}}</td><td class="py-2 px-2 text-sm">${{s.employee_name}}</td><td class="py-2 px-2 text-sm text-green-400">${{s.selling_price.toFixed(2)}}</td>`;
            if(isAdmin) row += `<td class="py-2 px-2 text-sm text-yellow-400">${{s.cost?.toFixed(2)||0}}</td><td class="py-2 px-2 text-sm text-cyan-400">${{s.commission?.toFixed(2)||0}}</td><td class="py-2 px-2 text-sm text-purple-400">${{(s.selling_price + (s.commission||0) - (s.total_price||s.selling_price)).toFixed(2)}}</td>`;
            row += `<td class="py-2 px-2 text-sm"><button onclick="reprintInvoice('${{s.order_id}}')" class="btn-primary px-2 py-1 rounded-lg text-xs"><i class="fas fa-print"></i> طباعة</button></td>
                    <td class="py-2 px-2 text-sm"><button onclick="sendWhatsApp('${{s.order_id}}', '${{s.customer_phone}}')" class="btn-success px-2 py-1 rounded-lg text-xs"><i class="fab fa-whatsapp"></i> واتساب</button></td>
                    <td class="py-2 px-2 text-sm">${{isAdmin ? `<button onclick="editSalePrice('${{s.order_id}}', ${{s.selling_price}})" class="btn-warning px-2 py-1 rounded-lg text-xs"><i class="fas fa-edit"></i> تعديل</button>` : '<span class="text-gray-500">-</span>'}}</td>
                    <td class="py-2 px-2 text-sm"><button onclick="deleteSale('${{s.order_id}}')" class="btn-danger px-2 py-1 rounded-lg text-xs"><i class="fas fa-trash"></i> حذف</button></td></tr>`;
            return row;
        }}).join(''); }}
        window.sendWhatsApp = (orderId, phone) => {{ window.open(`/api/invoice/whatsapp/${{orderId}}`, '_blank'); }};
        window.editSalePrice = async (orderId, currentPrice) => {{ const newPrice = parseFloat(prompt("أدخل السعر الجديد:", currentPrice)); if(isNaN(newPrice) || newPrice <= 0) {{ showToast('سعر غير صالح', 'error'); return; }} if(confirm(`تغيير سعر الفاتورة ${{orderId}} من ${{currentPrice}} إلى ${{newPrice}} ريال؟`)) {{ try {{ const res = await fetch(`/api/sales/${{orderId}}/price`, {{ method: 'PUT', headers: {{'Content-Type':'application/json'}}, body: JSON.stringify({{selling_price: newPrice}}) }}); if(res.ok) {{ showToast('✅ تم تعديل السعر', 'success'); loadSalesData(); }} else showToast('فشل التعديل', 'error'); }} catch(e) {{ showToast('خطأ', 'error'); }} }} }};
        window.deleteSale = async (orderId) => {{ if(confirm(`⚠️ هل أنت متأكد من حذف الفاتورة رقم ${{orderId}} نهائياً؟`)){{ try {{ const res = await fetch(`/api/sales/${{orderId}}`, {{ method: 'DELETE' }}); if(res.ok){{ showToast(`تم حذف الفاتورة رقم ${{orderId}}`, 'success'); loadSalesData(); }} else showToast('فشل الحذف', 'error'); }} catch(e){{ showToast('خطأ في الاتصال', 'error'); }} }} }};
        window.reprintInvoice = (orderId) => {{ window.open(`/api/invoice/print/${{orderId}}`, '_blank'); }};
        async function exportWithColumns() {{
            const selectedCols = Array.from(document.querySelectorAll('#columnSelectorModal input[type="checkbox"]:checked')).map(cb => cb.value);
            if(selectedCols.length === 0) {{ showToast('الرجاء اختيار عمود واحد على الأقل', 'error'); return; }}
            const branch = document.getElementById('filterBranch').value, employee = document.getElementById('filterEmployee').value, dateFrom = document.getElementById('dateFrom').value, dateTo = document.getElementById('dateTo').value, phone = document.getElementById('filterPhone').value;
            const params = new URLSearchParams({{ branch, employee, dateFrom, dateTo, phone, cols: selectedCols.join(',') }});
            window.location.href = `/api/export-excel?${{params.toString()}}`;
            document.getElementById('closeColumnSelector').click();
        }}
        async function printWithColumns() {{
            const selectedCols = Array.from(document.querySelectorAll('#columnSelectorModal input[type="checkbox"]:checked')).map(cb => cb.value);
            if(selectedCols.length === 0) {{ showToast('الرجاء اختيار عمود واحد على الأقل', 'error'); return; }}
            const branch = document.getElementById('filterBranch').value, employee = document.getElementById('filterEmployee').value, dateFrom = document.getElementById('dateFrom').value, dateTo = document.getElementById('dateTo').value, phone = document.getElementById('filterPhone').value;
            const params = new URLSearchParams({{ branch, employee, dateFrom, dateTo, phone, cols: selectedCols.join(',') }});
            window.open(`/api/print-report?${{params.toString()}}`, '_blank');
            document.getElementById('closeColumnSelector').click();
        }}
        document.getElementById('openColumnSelectorBtn').onclick = () => {{
            document.getElementById('columnSelectorModal').style.display = 'flex';
            setTimeout(()=>document.querySelector('#columnSelectorModal .modal-container').classList.add('active'),10);
        }};
        document.getElementById('closeColumnSelector').onclick = () => {{
            document.getElementById('columnSelectorModal').style.display = 'none';
            document.querySelector('#columnSelectorModal .modal-container').classList.remove('active');
        }};
        document.getElementById('confirmExportExcel').onclick = exportWithColumns;
        document.getElementById('confirmPrintReport').onclick = printWithColumns;
        document.getElementById('backupBtn').onclick = () => {{ window.location.href = '/api/backup'; }};
        document.getElementById('applyFilter').onclick = applyFilter; document.getElementById('resetFilter').onclick = () => {{ document.getElementById('dateFrom').value = ''; document.getElementById('dateTo').value = ''; document.getElementById('filterBranch').value = ''; document.getElementById('filterEmployee').value = ''; document.getElementById('filterPhone').value = ''; applyFilter(); }}; document.getElementById('refreshTable').onclick = loadSalesData;
        const today = new Date().toISOString().split('T')[0]; const thirtyDaysAgo = new Date(); thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30); document.getElementById('dateFrom').value = thirtyDaysAgo.toISOString().split('T')[0]; document.getElementById('dateTo').value = today;
        loadFilterOptions(); loadSalesData();
    </script>
    '''
    return get_base_html(content, "التقارير", current_user.name, is_admin)

@app.route('/debts')
@admin_required
def debts():
    content = '''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">🏦 مديونية الفروع</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6"><div class="flex justify-between items-center mb-3"><h2 class="text-xl lg:text-2xl font-bold"><i class="fas fa-list text-cyan-400 ml-1"></i> الفروع والمديونية</h2><button id="refreshDebts" class="btn-primary px-3 py-2 rounded-xl text-sm"><i class="fas fa-sync-alt ml-1"></i> تحديث</button></div><div id="branchesList" class="space-y-2 max-h-[500px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div><div class="mt-4 pt-3 border-t border-gray-700"><div class="debt-card flex justify-between items-center p-3"><span class="font-bold">🏦 إجمالي المديونية</span><span class="text-xl lg:text-2xl font-bold text-red-400" id="totalDebt">0.00 ريال</span></div></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-history text-cyan-400 ml-1"></i> سجل التسديدات</h2><div class="mb-3"><input type="text" id="searchPayment" placeholder="🔍 بحث باسم الفرع" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div id="paymentLogs" class="space-y-2 max-h-[400px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div><div class="mt-3"><button id="clearLogs" class="btn-danger w-full py-2 rounded-xl text-sm"><i class="fas fa-trash ml-1"></i> مسح سجل التسديدات</button></div></div>
        </div>
    </div>
    <script>
        let branchesData = [];
        async function loadBranches() { try { const res = await fetch('/api/branches'); branchesData = await res.json(); renderBranches(); } catch(e) { showToast('خطأ في التحميل', 'error'); } }
        function renderBranches() { const container = document.getElementById('branchesList'); let total = 0; if(branchesData.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد فروع</div>'; document.getElementById('totalDebt').innerHTML='0.00 ريال'; return; } container.innerHTML = branchesData.map(branch => { total += branch.debt; return `<div class="debt-card p-3"><div class="flex justify-between items-center flex-wrap gap-2"><div><h3 class="font-bold">${branch.name}</h3><p class="text-xl font-bold ${branch.debt>0?'text-red-400':'text-green-400'}">${branch.debt.toFixed(2)} ريال</p></div>${branch.debt>0?`<div class="flex gap-2"><input type="number" id="amount_${branch.id}" placeholder="المبلغ" class="w-24 px-2 py-1 rounded-xl bg-gray-700 border border-gray-600 text-center text-sm"><button onclick="payDebt(${branch.id}, ${branch.debt}, '${branch.name}')" class="btn-success px-3 py-1 rounded-xl text-sm"><i class="fas fa-money-bill-wave ml-1"></i> تسديد</button></div>`:'<span class="text-green-400 text-sm"><i class="fas fa-check-circle ml-1"></i> مافي مديونية</span>'}</div></div>`; }).join(''); document.getElementById('totalDebt').innerHTML = total.toFixed(2)+' ريال'; }
        async function payDebt(id, currentDebt, branchName) { const amountInput = document.getElementById(`amount_${id}`); const amount = parseFloat(amountInput.value); if(isNaN(amount)||amount<=0){ showToast('الرجاء إدخال مبلغ صحيح','error'); return; } if(amount>currentDebt){ showToast('المبلغ أكبر من المديونية','error'); return; } try { const res = await fetch(`/api/branches/${id}/pay`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})}); if(res.ok){ showToast(`✅ تم تسديد ${amount.toFixed(2)} ريال من فرع ${branchName}`,'success'); amountInput.value=''; loadBranches(); loadPaymentLogs(); } else showToast('فشل تسديد المبلغ','error'); } catch(e){ showToast('خطأ في الاتصال','error'); } }
        async function loadPaymentLogs() { try { const res = await fetch('/api/payment-logs'); let logs = await res.json(); const search = document.getElementById('searchPayment')?.value||''; if(search) logs = logs.filter(log=>log.branch_name.includes(search)); const container = document.getElementById('paymentLogs'); if(logs.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد تسديدات</div>'; return; } container.innerHTML = logs.map(log=>`<div class="bg-gray-800 rounded-xl p-2 hover:bg-gray-700 transition"><div class="flex justify-between items-center"><div><p class="font-bold text-cyan-400 text-sm">${log.branch_name}</p><p class="text-xs text-gray-400">${log.date}</p></div><p class="text-green-400 font-bold">${log.amount.toFixed(2)} ريال</p></div></div>`).join(''); } catch(e){ console.error(e); } }
        document.getElementById('refreshDebts').onclick = () => { loadBranches(); loadPaymentLogs(); };
        document.getElementById('searchPayment')?.addEventListener('input', loadPaymentLogs);
        document.getElementById('clearLogs').onclick = async () => { if(confirm('⚠️ هل أنت متأكد من مسح سجل التسديدات بالكامل؟')) { try { await fetch('/api/clear-payment-logs', { method: 'DELETE' }); showToast('تم مسح سجل التسديدات', 'success'); loadPaymentLogs(); } catch(e) { showToast('خطأ في مسح السجل', 'error'); } } };
        loadBranches(); loadPaymentLogs();
    </script>
    '''
    return get_base_html(content, "المديونية", current_user.name, True)

@app.route('/commissions')
@admin_required
def commissions():
    content = '''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">💰 إدارة العمولات</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6"><div class="flex justify-between items-center mb-3"><h2 class="text-xl lg:text-2xl font-bold"><i class="fas fa-chart-pie text-cyan-400 ml-1"></i> العمولات المعلقة حسب المصدر</h2><button id="refreshChannels" class="btn-primary px-3 py-2 rounded-xl text-sm"><i class="fas fa-sync-alt ml-1"></i> تحديث</button></div><div id="channelsList" class="space-y-2 max-h-[400px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div><div class="mt-4 pt-3 border-t border-gray-700"><div class="debt-card flex justify-between items-center p-3"><span class="font-bold">📊 إجمالي العمولات المعلقة</span><span class="text-xl lg:text-2xl font-bold text-yellow-400" id="totalCommission">0.00 ريال</span></div></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-hand-holding-usd text-green-400 ml-1"></i> تحصيل العمولات</h2><div class="bg-gray-800 rounded-xl p-3 mb-3 text-center"><p class="text-gray-400 text-sm">الرصيد المتاح للتحصيل</p><p class="text-3xl lg:text-4xl font-bold text-green-400" id="availableCommission">0.00</p><p class="text-xs text-gray-500">ريال سعودي</p></div><div class="space-y-3"><div><label class="block text-sm font-medium mb-1">💰 اختر المصدر</label><select id="commissionChannel" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="">اختر المصدر</option></select></div><div><label class="block text-sm font-medium mb-1">المبلغ المراد تحصيله</label><input type="number" id="collectAmount" step="0.01" placeholder="أدخل المبلغ" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-center text-sm"></div><div><label class="block text-sm font-medium mb-1">📈 وجهة التحصيل</label><div class="grid grid-cols-2 gap-2"><button id="targetWalletBtn" class="target-btn py-2 rounded-xl bg-green-600 border-2 border-green-500 font-bold text-sm transition">💰 إضافة للمحفظة</button><button id="targetProfitBtn" class="target-btn py-2 rounded-xl bg-gray-700 border-2 border-gray-600 font-bold text-sm transition">📈 إضافة للأرباح</button></div><input type="hidden" id="collectTarget" value="wallet"></div><button id="collectBtn" class="btn-primary w-full py-2 rounded-xl font-bold text-sm transition"><i class="fas fa-check-circle ml-1"></i> تأكيد التحصيل</button></div><div class="mt-4"><h3 class="font-bold mb-2 text-sm">📋 سجل التحصيل</h3><div id="collectionLog" class="max-h-[200px] overflow-y-auto space-y-1"><div class="text-center text-gray-500 py-4 text-sm">لا توجد عمليات تحصيل</div></div></div></div>
        </div>
    </div>
    <script>
        let collectionHistory = [], currentChannels = [];
        async function loadChannelsCommissions() { try { const res = await fetch('/api/channels'); currentChannels = await res.json(); renderChannels(); const channelSelect = document.getElementById('commissionChannel'); channelSelect.innerHTML = '<option value="">اختر المصدر</option>' + currentChannels.map(ch => `<option value="${ch.id}" data-name="${ch.name}" data-amount="${ch.pending_commission}">${ch.name} (${ch.pending_commission.toFixed(2)} ريال)</option>`).join(''); } catch(e) { showToast('خطأ في التحميل','error'); } }
        function renderChannels() { const container = document.getElementById('channelsList'); let total = 0; if(currentChannels.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد مصادر تفعيل</div>'; document.getElementById('totalCommission').innerHTML='0.00 ريال'; document.getElementById('availableCommission').innerHTML='0.00'; return; } container.innerHTML = currentChannels.map(ch => { total += ch.pending_commission; const percentage = total>0?(ch.pending_commission/total)*100:0; return `<div class="bg-gray-800 rounded-xl p-2 hover:bg-gray-700 transition"><div class="flex justify-between items-center"><div><i class="fas fa-satellite-dish text-cyan-400 ml-1"></i><span class="font-bold text-sm">${ch.name}</span></div><div><span class="text-yellow-400 font-bold text-sm">${ch.pending_commission.toFixed(2)}</span><span class="text-xs text-gray-500 mr-1">ريال</span></div></div><div class="w-full bg-gray-700 rounded-full h-1.5 mt-1"><div class="bg-yellow-400 h-1.5 rounded-full" style="width: ${Math.min(100,percentage)}%"></div></div></div>`; }).join(''); document.getElementById('totalCommission').innerHTML = total.toFixed(2)+' ريال'; document.getElementById('availableCommission').innerHTML = total.toFixed(2); }
        document.getElementById('targetWalletBtn').onclick = () => { document.getElementById('targetWalletBtn').classList.remove('bg-gray-700','border-gray-600'); document.getElementById('targetWalletBtn').classList.add('bg-green-600','border-green-500'); document.getElementById('targetProfitBtn').classList.remove('bg-green-600','border-green-500'); document.getElementById('targetProfitBtn').classList.add('bg-gray-700','border-gray-600'); document.getElementById('collectTarget').value = 'wallet'; };
        document.getElementById('targetProfitBtn').onclick = () => { document.getElementById('targetProfitBtn').classList.remove('bg-gray-700','border-gray-600'); document.getElementById('targetProfitBtn').classList.add('bg-green-600','border-green-500'); document.getElementById('targetWalletBtn').classList.remove('bg-green-600','border-green-500'); document.getElementById('targetWalletBtn').classList.add('bg-gray-700','border-gray-600'); document.getElementById('collectTarget').value = 'profit'; };
        document.getElementById('collectBtn').onclick = async () => { const channelId = document.getElementById('commissionChannel').value; const amount = parseFloat(document.getElementById('collectAmount').value); const target = document.getElementById('collectTarget').value; if(!channelId){ showToast('الرجاء اختيار المصدر','error'); return; } if(isNaN(amount)||amount<=0){ showToast('الرجاء إدخال مبلغ صحيح','error'); return; } try { const res = await fetch('/api/commissions/collect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channelId, amount, target})}); const result = await res.json(); if(result.success){ showToast(`✅ تم تحصيل ${result.collected.toFixed(2)} ريال من ${result.channelName}`,'success'); document.getElementById('collectAmount').value=''; document.getElementById('commissionChannel').value=''; loadChannelsCommissions(); const logEntry = { date: new Date().toLocaleString('ar-SA'), amount: result.collected, channel: result.channelName, target: target==='wallet'?'المحفظة':'الأرباح' }; collectionHistory.unshift(logEntry); updateCollectionLog(); } else showToast(result.error,'error'); } catch(e){ showToast('خطأ في الاتصال','error'); } };
        function updateCollectionLog() { const container = document.getElementById('collectionLog'); if(collectionHistory.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-4 text-sm">لا توجد عمليات تحصيل</div>'; return; } container.innerHTML = collectionHistory.slice(0,10).map(log=>`<div class="bg-gray-800 rounded-xl p-2 flex justify-between items-center hover:bg-gray-700 transition"><div><p class="text-xs">${log.date}</p><p class="text-xs text-gray-400">${log.channel} → ${log.target}</p></div><p class="text-green-400 font-bold text-sm">${log.amount.toFixed(2)} ريال</p></div>`).join(''); }
        document.getElementById('refreshChannels').onclick = loadChannelsCommissions;
        loadChannelsCommissions();
    </script>
    '''
    return get_base_html(content, "العمولات", current_user.name, True)

@app.route('/settings')
@admin_required
def settings():
    content = '''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">⚙️ الإعدادات</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-coins text-yellow-400 ml-1"></i> إدارة السيولة</h2><div class="bg-gray-800 rounded-xl p-3 mb-3 text-center"><p class="text-gray-400 text-sm">رصيد المحفظة الحالي</p><p class="text-2xl lg:text-3xl font-bold text-cyan-400" id="mainBalance">0.00</p><p class="text-xs text-gray-500">ريال سعودي</p></div><div class="grid grid-cols-2 gap-2 mb-3"><div><label class="block text-sm font-medium mb-1">➕ إضافة سيولة</label><input type="number" id="addAmount" step="0.01" placeholder="المبلغ" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="addLiquidityBtn" class="btn-success w-full mt-1 py-1 rounded-xl text-sm"><i class="fas fa-plus ml-1"></i> إضافة</button></div><div><label class="block text-sm font-medium mb-1">➖ خصم سيولة</label><input type="number" id="deductAmount" step="0.01" placeholder="المبلغ" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="deductLiquidityBtn" class="btn-danger w-full mt-1 py-1 rounded-xl text-sm"><i class="fas fa-minus ml-1"></i> خصم</button></div></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-chart-line text-purple-400 ml-1"></i> رأس المال</h2><div class="bg-gray-800 rounded-xl p-3 mb-3"><p class="text-gray-400 text-sm">رأس المال الحالي</p><p class="text-2xl lg:text-3xl font-bold text-purple-400" id="capitalBase">0.00</p><p class="text-xs text-gray-500">ريال سعودي</p></div><div class="flex gap-2"><input type="number" id="newCapital" step="0.01" placeholder="قيمة رأس المال الجديدة" class="flex-1 px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="updateCapitalBtn" class="btn-primary px-3 py-2 rounded-xl text-sm"><i class="fas fa-edit ml-1"></i> تحديث</button></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-image text-cyan-400 ml-1"></i> شعار الشركة</h2><div class="text-center mb-3"><div id="logoPreview"></div><input type="file" id="logoInput" accept="image/*" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="uploadLogoBtn" class="btn-primary w-full mt-2 py-2 rounded-xl text-sm"><i class="fas fa-upload ml-1"></i> رفع الشعار</button></div></div>
            <div class="card rounded-2xl p-4 lg:p-6"><h2 class="text-xl lg:text-2xl font-bold mb-3"><i class="fas fa-file-alt text-cyan-400 ml-1"></i> النص الثابت للفاتورة</h2><p class="text-gray-400 text-xs mb-2">هذا النص سيظهر تلقائياً في جميع الفواتير</p><textarea id="defaultNote" rows="3" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm">جاري التحميل...</textarea><button id="saveNoteBtn" class="btn-primary w-full mt-2 py-2 rounded-xl text-sm"><i class="fas fa-save ml-1"></i> حفظ النص</button></div>
            <div class="card rounded-2xl p-4 lg:p-6 border-2 border-red-500/50 col-span-full"><h2 class="text-xl lg:text-2xl font-bold mb-3 flex items-center gap-2 text-red-400"><i class="fas fa-exclamation-triangle"></i> منطقة الخطر</h2><p class="text-gray-400 text-xs mb-3">⚠️ تهيئة النظام ستحذف جميع البيانات (المبيعات، المنتجات، الفروع، الموظفين، إلخ) وترجع النظام إلى الإعدادات الافتراضية. هذا الإجراء لا يمكن التراجع عنه!</p><button id="resetSystemBtn" class="w-full py-2 rounded-xl font-bold bg-red-600 hover:bg-red-700 transition text-sm"><i class="fas fa-database ml-1"></i> تهيئة النظام بالكامل</button></div>
        </div>
    </div>
    <script>
        async function loadWalletData() { try { const res = await fetch('/api/wallet'); const data = await res.json(); document.getElementById('mainBalance').innerHTML = data.main_balance.toFixed(2); document.getElementById('capitalBase').innerHTML = data.capital_base.toFixed(2); } catch(e) { showToast('خطأ في التحميل', 'error'); } }
        async function loadDefaultNote() { try { const res = await fetch('/api/invoice/default-note'); const data = await res.json(); document.getElementById('defaultNote').value = data.note; } catch(e) { showToast('خطأ في تحميل النص', 'error'); } }
        async function loadLogoPreview() { try { const res = await fetch('/api/logo'); const data = await res.json(); if(data.logo) document.getElementById('logoPreview').innerHTML = '<img src="'+data.logo+'" class="max-w-[60px] mx-auto rounded-xl mb-1">'; } catch(e) { console.error(e); } }
        document.getElementById('addLiquidityBtn').onclick = async () => { const amount = parseFloat(document.getElementById('addAmount').value); if(isNaN(amount)||amount<=0){ showToast('الرجاء إدخال مبلغ صحيح','error'); return; } try { const res = await fetch('/api/wallet/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})}); if(res.ok){ showToast('✅ تمت إضافة '+amount.toFixed(2)+' ريال','success'); document.getElementById('addAmount').value=''; loadWalletData(); } else showToast('فشل إضافة المبلغ','error'); } catch(e){ showToast('خطأ في الاتصال','error'); } };
        document.getElementById('deductLiquidityBtn').onclick = async () => { const amount = parseFloat(document.getElementById('deductAmount').value); if(isNaN(amount)||amount<=0){ showToast('الرجاء إدخال مبلغ صحيح','error'); return; } try { const res = await fetch('/api/wallet/deduct',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})}); if(res.ok){ showToast('✅ تم خصم '+amount.toFixed(2)+' ريال','success'); document.getElementById('deductAmount').value=''; loadWalletData(); } else { const data=await res.json(); showToast(data.error,'error'); } } catch(e){ showToast('خطأ في الاتصال','error'); } };
        document.getElementById('updateCapitalBtn').onclick = async () => { const capital = parseFloat(document.getElementById('newCapital').value); if(isNaN(capital)||capital<=0){ showToast('الرجاء إدخال قيمة صحيحة','error'); return; } try { const res = await fetch('/api/wallet/capital',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({capital})}); if(res.ok){ showToast('✅ تم تحديث رأس المال إلى '+capital.toFixed(2)+' ريال','success'); document.getElementById('newCapital').value=''; loadWalletData(); } else showToast('فشل تحديث رأس المال','error'); } catch(e){ showToast('خطأ في الاتصال','error'); } };
        document.getElementById('saveNoteBtn').onclick = async () => { const note = document.getElementById('defaultNote').value; try { const res = await fetch('/api/invoice/default-note',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note})}); if(res.ok){ showToast('✅ تم حفظ النص الثابت','success'); } else showToast('فشل حفظ النص','error'); } catch(e){ showToast('خطأ في الاتصال','error'); } };
        document.getElementById('uploadLogoBtn').onclick = async () => { const file = document.getElementById('logoInput').files[0]; if(!file){ showToast('اختر صورة أولاً','error'); return; } const formData = new FormData(); formData.append('logo', file); const res = await fetch('/api/upload-logo',{method:'POST',body:formData}); if(res.ok){ showToast('✅ تم رفع الشعار','success'); loadLogoPreview(); setTimeout(()=>location.reload(),1000); } else showToast('فشل الرفع','error'); };
        document.getElementById('resetSystemBtn').onclick = async () => { const password = prompt('🔐 لتأكيد تهيئة النظام، الرجاء إدخال الرقم السري للمدير:'); if(!password) return; if(confirm('⚠️ تحذير أخير! هل أنت متأكد من تهيئة النظام بالكامل؟ هذا الإجراء لا يمكن التراجع عنه!')) { try { const res = await fetch('/api/reset-system',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})}); if(res.ok){ showToast('✅ تمت تهيئة النظام بنجاح، سيتم إعادة تحميل الصفحة','success'); setTimeout(()=>window.location.reload(),2000); } else { const data=await res.json(); showToast(data.error,'error'); } } catch(e){ showToast('خطأ في الاتصال','error'); } } };
        loadWalletData(); loadDefaultNote(); loadLogoPreview();
    </script>
    '''
    return get_base_html(content, "الإعدادات", current_user.name, True)

@app.route('/company-settings')
@login_required
def company_settings():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    company = get_company_info()
    content = f'''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">🏢 بيانات الشركة والمؤسسة</h1>
        <div class="card rounded-2xl p-4 lg:p-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3"><div><label class="block text-sm font-medium mb-1">اسم الشركة / المؤسسة</label><input type="text" id="companyName" value="{company.name}" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div><label class="block text-sm font-medium mb-1">رقم السجل التجاري</label><input type="text" id="commercialReg" value="{company.commercial_reg}" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div><label class="block text-sm font-medium mb-1">الرقم الضريبي</label><input type="text" id="taxNumber" value="{company.tax_number}" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div><label class="block text-sm font-medium mb-1">رقم الهاتف</label><input type="text" id="companyPhone" value="{company.phone}" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div><div class="md:col-span-2"><label class="block text-sm font-medium mb-1">العنوان</label><input type="text" id="companyAddress" value="{company.address}" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div></div>
            <button id="saveCompanyBtn" class="btn-primary mt-4 w-full py-2 rounded-xl font-bold text-sm"><i class="fas fa-save ml-1"></i> حفظ بيانات الشركة</button>
        </div>
        <div class="text-center text-gray-500 text-xs">حقوق الملكية: {FOOTER_TEXT}</div>
    </div>
    <script> document.getElementById('saveCompanyBtn').onclick = async () => {{ const data = {{ name: document.getElementById('companyName').value, address: document.getElementById('companyAddress').value, tax_number: document.getElementById('taxNumber').value, phone: document.getElementById('companyPhone').value, commercial_reg: document.getElementById('commercialReg').value }}; const res = await fetch('/api/company-info', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(data) }}); if(res.ok) showToast('✅ تم حفظ بيانات الشركة', 'success'); else showToast('فشل الحفظ', 'error'); setTimeout(() => location.reload(), 1000); }}; </script>
    '''
    return get_base_html(content, "بيانات الشركة", current_user.name, True)

@app.route('/manage')
@admin_required
def manage():
    content = '''
    <div class="space-y-4">
        <h1 class="text-2xl lg:text-3xl font-bold mb-4">👥 إدارة النظام</h1>
        <div class="card rounded-2xl p-4 lg:p-6">
            <div class="flex border-b border-gray-700 mb-4 overflow-x-auto">
                <button class="tab-btn px-4 py-2 font-bold border-b-2 border-cyan-500 text-cyan-400 text-sm" data-tab="employees"><i class="fas fa-users ml-1"></i> الموظفين</button>
                <button class="tab-btn px-4 py-2 font-bold text-gray-400 hover:text-white text-sm" data-tab="branches"><i class="fas fa-store ml-1"></i> الفروع</button>
                <button class="tab-btn px-4 py-2 font-bold text-gray-400 hover:text-white text-sm" data-tab="channels"><i class="fas fa-satellite-dish ml-1"></i> مصادر التفعيل</button>
                <button class="tab-btn px-4 py-2 font-bold text-gray-400 hover:text-white text-sm" data-tab="users"><i class="fas fa-user-shield ml-1"></i> المستخدمين</button>
            </div>
            <div id="tab-employees" class="tab-content"><div class="flex gap-2 mb-3"><input type="text" id="newEmployee" placeholder="اسم الموظف الجديد" class="flex-1 px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="addEmployeeBtn" class="btn-success px-4 py-2 rounded-xl text-sm"><i class="fas fa-plus ml-1"></i> إضافة</button></div><div id="employeesList" class="space-y-2 max-h-[400px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div></div>
            <div id="tab-branches" class="tab-content hidden"><div class="flex gap-2 mb-3"><input type="text" id="newBranch" placeholder="اسم الفرع الجديد" class="flex-1 px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="addBranchBtn" class="btn-success px-4 py-2 rounded-xl text-sm"><i class="fas fa-plus ml-1"></i> إضافة</button></div><div id="branchesList" class="space-y-2 max-h-[400px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div></div>
            <div id="tab-channels" class="tab-content hidden"><div class="flex gap-2 mb-3"><input type="text" id="newChannel" placeholder="اسم المصدر الجديد" class="flex-1 px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><button id="addChannelBtn" class="btn-success px-4 py-2 rounded-xl text-sm"><i class="fas fa-plus ml-1"></i> إضافة</button></div><div id="channelsList" class="space-y-2 max-h-[400px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div></div>
            <div id="tab-users" class="tab-content hidden"><div class="grid grid-cols-1 lg:grid-cols-2 gap-4"><div><h3 class="font-bold mb-2 text-sm">➕ إضافة مستخدم جديد</h3><div class="space-y-2"><input type="text" id="newUsername" placeholder="اسم المستخدم" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><input type="text" id="newUserFullname" placeholder="الاسم الكامل" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><input type="password" id="newUserPassword" placeholder="كلمة المرور" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><select id="newUserRole" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"><option value="cashier">كاشير</option><option value="admin">مدير</option></select><button id="addUserBtn" class="btn-primary w-full py-2 rounded-xl text-sm"><i class="fas fa-user-plus ml-1"></i> إضافة مستخدم</button></div></div><div><h3 class="font-bold mb-2 text-sm">📋 قائمة المستخدمين</h3><div id="usersList" class="space-y-2 max-h-[350px] overflow-y-auto"><div class="text-center text-gray-500 py-8">جاري التحميل...</div></div></div></div></div>
        </div>
    </div>
    <script>
        let currentTab='employees';
        document.querySelectorAll('.tab-btn').forEach(btn=>{ btn.onclick=()=>{ document.querySelectorAll('.tab-btn').forEach(b=>{ b.classList.remove('border-cyan-500','text-cyan-400'); b.classList.add('text-gray-400'); }); btn.classList.add('border-cyan-500','text-cyan-400'); btn.classList.remove('text-gray-400'); currentTab=btn.dataset.tab; document.querySelectorAll('.tab-content').forEach(c=>c.classList.add('hidden')); document.getElementById(`tab-${currentTab}`).classList.remove('hidden'); if(currentTab==='employees') loadEmployees(); else if(currentTab==='branches') loadBranchesAdmin(); else if(currentTab==='channels') loadChannelsAdmin(); else if(currentTab==='users') loadUsers(); }; });
        async function loadEmployees() { try { const res = await fetch('/api/employees'); const employees = await res.json(); const container = document.getElementById('employeesList'); if(employees.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد موظفين</div>'; return; } container.innerHTML = employees.map(emp=>`<div class="bg-gray-800 rounded-xl p-2 flex justify-between items-center"><span class="text-sm"><i class="fas fa-user ml-1 text-cyan-400"></i> ${emp.name}</span><button onclick="deleteEmployee(${emp.id}, '${emp.name}')" class="text-red-400 hover:text-red-300 text-sm"><i class="fas fa-trash"></i> حذف</button></div>`).join(''); } catch(e){ showToast('خطأ في التحميل','error'); } }
        async function deleteEmployee(id,name) { if(confirm(`حذف الموظف "${name}"؟`)){ const res = await fetch(`/api/employees/${id}`,{method:'DELETE'}); if(res.ok){ showToast(`تم حذف الموظف ${name}`,'success'); loadEmployees(); } } }
        document.getElementById('addEmployeeBtn').onclick = async () => { const name = document.getElementById('newEmployee').value.trim(); if(!name){ showToast('الرجاء إدخال اسم الموظف','error'); return; } const res = await fetch('/api/employees',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}); if(res.ok){ showToast(`تمت إضافة الموظف ${name}`,'success'); document.getElementById('newEmployee').value=''; loadEmployees(); } };
        async function loadBranchesAdmin() { try { const res = await fetch('/api/branches'); const branches = await res.json(); const container = document.getElementById('branchesList'); if(branches.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد فروع</div>'; return; } container.innerHTML = branches.map(branch=>`<div class="bg-gray-800 rounded-xl p-2 flex justify-between items-center"><span class="text-sm"><i class="fas fa-store ml-1 text-cyan-400"></i> ${branch.name}</span><button onclick="deleteBranch(${branch.id}, '${branch.name}')" class="text-red-400 hover:text-red-300 text-sm"><i class="fas fa-trash"></i> حذف</button></div>`).join(''); } catch(e){ showToast('خطأ في التحميل','error'); } }
        async function deleteBranch(id,name) { if(confirm(`حذف الفرع "${name}"؟`)){ const res = await fetch(`/api/branches/${id}`,{method:'DELETE'}); if(res.ok){ showToast(`تم حذف الفرع ${name}`,'success'); loadBranchesAdmin(); } } }
        document.getElementById('addBranchBtn').onclick = async () => { const name = document.getElementById('newBranch').value.trim(); if(!name){ showToast('الرجاء إدخال اسم الفرع','error'); return; } const res = await fetch('/api/branches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}); if(res.ok){ showToast(`تمت إضافة الفرع ${name}`,'success'); document.getElementById('newBranch').value=''; loadBranchesAdmin(); } };
        async function loadChannelsAdmin() { try { const res = await fetch('/api/channels'); const channels = await res.json(); const container = document.getElementById('channelsList'); if(channels.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد مصادر تفعيل</div>'; return; } container.innerHTML = channels.map(ch=>`<div class="bg-gray-800 rounded-xl p-2 flex justify-between items-center"><span class="text-sm"><i class="fas fa-satellite-dish ml-1 text-cyan-400"></i> ${ch.name}</span><button onclick="deleteChannel(${ch.id}, '${ch.name}')" class="text-red-400 hover:text-red-300 text-sm"><i class="fas fa-trash"></i> حذف</button></div>`).join(''); } catch(e){ showToast('خطأ في التحميل','error'); } }
        async function deleteChannel(id,name) { if(confirm(`حذف المصدر "${name}"؟`)){ const res = await fetch(`/api/channels/${id}`,{method:'DELETE'}); if(res.ok){ showToast(`تم حذف المصدر ${name}`,'success'); loadChannelsAdmin(); } } }
        document.getElementById('addChannelBtn').onclick = async () => { const name = document.getElementById('newChannel').value.trim(); if(!name){ showToast('الرجاء إدخال اسم المصدر','error'); return; } const res = await fetch('/api/channels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}); if(res.ok){ showToast(`تمت إضافة المصدر ${name}`,'success'); document.getElementById('newChannel').value=''; loadChannelsAdmin(); } };
        async function loadUsers() { try { const res = await fetch('/api/users'); const users = await res.json(); const container = document.getElementById('usersList'); if(users.length===0){ container.innerHTML='<div class="text-center text-gray-500 py-8">لا توجد مستخدمين</div>'; return; } container.innerHTML = users.map(user=>`<div class="bg-gray-800 rounded-xl p-2 flex justify-between items-center"><div><p class="font-bold text-sm">${user.name}</p><p class="text-xs text-gray-400">@${user.username} | ${user.role==='admin'?'مدير':'كاشير'}</p></div>${user.username!=='admin'?`<button onclick="deleteUser(${user.id}, '${user.username}')" class="text-red-400 hover:text-red-300 text-sm"><i class="fas fa-trash"></i> حذف</button>`:'<span class="text-gray-500 text-xs"><i class="fas fa-crown"></i> رئيسي</span>'}</div>`).join(''); } catch(e){ showToast('خطأ في التحميل','error'); } }
        async function deleteUser(id,username) { if(confirm(`حذف المستخدم "${username}"؟`)){ const res = await fetch(`/api/users/${id}`,{method:'DELETE'}); if(res.ok){ showToast(`تم حذف المستخدم ${username}`,'success'); loadUsers(); } } }
        document.getElementById('addUserBtn').onclick = async () => { const username = document.getElementById('newUsername').value.trim(); const name = document.getElementById('newUserFullname').value.trim(); const password = document.getElementById('newUserPassword').value; const role = document.getElementById('newUserRole').value; if(!username||!name||!password){ showToast('الرجاء تعبئة جميع الحقول','error'); return; } const res = await fetch('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,name,password,role})}); if(res.ok){ showToast(`تمت إضافة المستخدم ${username}`,'success'); document.getElementById('newUsername').value=''; document.getElementById('newUserFullname').value=''; document.getElementById('newUserPassword').value=''; loadUsers(); } else { const data=await res.json(); showToast(data.error,'error'); } };
        loadEmployees();
    </script>
    '''
    return get_base_html(content, "الإدارة", current_user.name, True)

@app.route('/restore')
@admin_required
def restore_page():
    content = '''
    <div class="card rounded-2xl p-4 lg:p-6 max-w-md mx-auto">
        <h1 class="text-xl lg:text-2xl font-bold mb-4">🔄 استعادة نسخة احتياطية</h1>
        <div class="space-y-3">
            <div class="bg-yellow-900/30 p-3 rounded-xl text-yellow-400 text-sm"><i class="fas fa-exclamation-triangle ml-1"></i> تحذير: استعادة النسخة الاحتياطية ستستبدل جميع البيانات الحالية!</div>
            <div><label class="block text-sm font-medium mb-1">اختر ملف النسخة الاحتياطية (.json أو .json.gz)</label><input type="file" id="backupFile" accept=".json,.gz" class="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-sm"></div>
            <button id="restoreBtn" class="btn-primary w-full py-2 rounded-xl font-bold text-sm"><i class="fas fa-upload ml-1"></i> استعادة البيانات</button>
            <a href="/settings" class="btn-warning block text-center w-full py-2 rounded-xl font-bold text-sm"><i class="fas fa-arrow-right ml-1"></i> العودة للإعدادات</a>
        </div>
    </div>
    <script> document.getElementById('restoreBtn').onclick = async () => { const file = document.getElementById('backupFile').files[0]; if(!file){ showToast('الرجاء اختيار ملف', 'error'); return; } if(!confirm('⚠️ تحذير! استعادة النسخة الاحتياطية ستحذف جميع البيانات الحالية. هل أنت متأكد؟')) return; const formData = new FormData(); formData.append('backup_file', file); const res = await fetch('/api/restore-backup', { method: 'POST', body: formData }); if(res.ok){ showToast('✅ تم استعادة النسخة الاحتياطية بنجاح', 'success'); setTimeout(()=>location.href='/dashboard', 2000); } else { const data=await res.json(); showToast(data.error, 'error'); } }; </script>
    '''
    return get_base_html(content, "استعادة نسخة احتياطية", current_user.name, True)

@app.route('/logout')
@login_required
def logout():
    log_activity(current_user, "تسجيل خروج", f"خروج من {request.remote_addr}")
    logout_user()
    return redirect(url_for('index'))

# ==================== API Endpoints ====================
@app.route('/api/wallet')
@admin_required
def api_wallet():
    w = get_wallet()
    return jsonify({'main_balance': w.main_balance, 'pending_commission': w.pending_commission, 'profits': w.profits, 'capital_base': w.capital_base})

@app.route('/api/balance')
@admin_required
def api_balance():
    balance, total_assets, total_liabilities, total_debt, total_commission = calculate_balance()
    return jsonify({'balance': balance, 'total_assets': total_assets, 'total_liabilities': total_liabilities, 'total_debt': total_debt, 'total_commission': total_commission})

@app.route('/api/advanced-stats')
@login_required
def advanced_stats():
    top_products = db.session.query(Sale.product_name, func.count(Sale.id).label('count'), func.sum(Sale.total_price).label('total')).group_by(Sale.product_name).order_by(func.count(Sale.id).desc()).limit(5).all()
    top_employees = db.session.query(Sale.employee_name, func.count(Sale.id).label('count')).group_by(Sale.employee_name).order_by(func.count(Sale.id).desc()).limit(3).all()
    return jsonify({'top_products': [{'name': p[0], 'count': p[1], 'total': float(p[2]) if p[2] else 0} for p in top_products], 'top_employees': [{'name': e[0], 'count': e[1]} for e in top_employees]})

@app.route('/api/expired-products')
@login_required
def api_expired_products():
    today = datetime.utcnow()
    expired = Sale.query.filter(Sale.expiry_date <= today, Sale.expiry_date.isnot(None)).all()
    return jsonify([{'order_id': s.order_id, 'product': s.product_name, 'expiry_date': s.expiry_date.strftime('%Y-%m-%d'), 'customer': s.customer_name} for s in expired])

@app.route('/api/charts-data')
@login_required
def api_charts_data():
    daily_totals = []
    daily_labels = []
    for i in range(6, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        daily_labels.append(date.strftime('%Y-%m-%d'))
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        total = db.session.query(func.sum(Sale.selling_price)).filter(Sale.date.between(start, end)).scalar() or 0
        daily_totals.append(float(total))
    top_products = db.session.query(Sale.product_name, func.count(Sale.id)).group_by(Sale.product_name).order_by(func.count(Sale.id).desc()).limit(5).all()
    product_labels = [p[0] for p in top_products]
    product_counts = [p[1] for p in top_products]
    return jsonify({'daily_labels': daily_labels, 'daily_totals': daily_totals, 'product_labels': product_labels, 'product_counts': product_counts})

@app.route('/api/backup')
@admin_required
def backup_database():
    data = {
        'products': [{'id': p.id, 'name': p.name, 'cost': p.cost, 'commission': p.commission, 'selling_price': p.selling_price, 'total_price': p.total_price, 'expiry_months': p.expiry_months} for p in Product.query.all()],
        'employees': [{'id': e.id, 'name': e.name} for e in Employee.query.all()],
        'branches': [{'id': b.id, 'name': b.name, 'debt': b.debt} for b in Branch.query.all()],
        'channels': [{'id': c.id, 'name': c.name, 'pending_commission': c.pending_commission} for c in Channel.query.all()],
        'sales': [{'order_id': s.order_id, 'customer_name': s.customer_name, 'customer_phone': s.customer_phone, 'product_name': s.product_name, 'selling_price': s.selling_price, 'total_price': s.total_price, 'date': s.date.isoformat(), 'net_profit': s.net_profit, 'cost': s.cost, 'commission': s.commission, 'employee_name': s.employee_name, 'branch_name': s.branch_name, 'channel_name': s.channel_name, 'payment_method': s.payment_method} for s in Sale.query.all()],
        'wallet': {'main_balance': get_wallet().main_balance, 'profits': get_wallet().profits, 'capital_base': get_wallet().capital_base},
        'company_info': {'name': get_company_info().name, 'address': get_company_info().address}
    }
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    compressed = gzip.compress(json_str.encode('utf-8'))
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
    return send_file(io.BytesIO(compressed), download_name=filename, as_attachment=True)

@app.route('/api/restore-backup', methods=['POST'])
@admin_required
def restore_backup():
    if 'backup_file' not in request.files:
        return jsonify({'error': 'لا يوجد ملف'}), 400
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400
    try:
        file_content = file.read()
        if file.filename.endswith('.gz'):
            json_str = gzip.decompress(file_content).decode('utf-8')
        else:
            json_str = file_content.decode('utf-8')
        data = json.loads(json_str)
        db.session.query(Sale).delete()
        db.session.query(Product).delete()
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.query(Channel).delete()
        for p in data.get('products', []):
            product = Product(id=p['id'], name=p['name'], cost=p['cost'], commission=p['commission'], selling_price=p['selling_price'], total_price=p.get('total_price', 0), expiry_months=p.get('expiry_months', 0))
            db.session.add(product)
        for e in data.get('employees', []):
            emp = Employee(id=e['id'], name=e['name'])
            db.session.add(emp)
        for b in data.get('branches', []):
            branch = Branch(id=b['id'], name=b['name'], debt=b.get('debt', 0))
            db.session.add(branch)
        for c in data.get('channels', []):
            channel = Channel(id=c['id'], name=c['name'], pending_commission=c.get('pending_commission', 0))
            db.session.add(channel)
        for s in data.get('sales', []):
            sale = Sale(order_id=s['order_id'], customer_name=s['customer_name'], customer_phone=s['customer_phone'], product_name=s['product_name'], selling_price=s.get('selling_price', 0), total_price=s.get('total_price', 0), date=datetime.fromisoformat(s['date']), net_profit=s.get('net_profit', 0), cost=s.get('cost', 0), commission=s.get('commission', 0), employee_name=s.get('employee_name', ''), branch_name=s.get('branch_name', ''), channel_name=s.get('channel_name', ''), payment_method=s.get('payment_method', 'كاش'))
            db.session.add(sale)
        if 'wallet' in data:
            wallet = get_wallet()
            wallet.main_balance = data['wallet'].get('main_balance', 0)
            wallet.profits = data['wallet'].get('profits', 0)
            wallet.capital_base = data['wallet'].get('capital_base', 0)
        db.session.commit()
        log_activity(current_user, "استعادة نسخة احتياطية", "تم استعادة البيانات من ملف النسخ الاحتياطي")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'فشل الاستعادة: {str(e)}'}), 500

@app.route('/api/wallet/add', methods=['POST'])
@admin_required
def api_add_liquidity():
    data = request.get_json()
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'error': 'مبلغ غير صالح'}), 400
    w = get_wallet()
    w.main_balance += amount
    db.session.commit()
    log_activity(current_user, "إضافة سيولة", f"تمت إضافة {amount:.2f} ريال للمحفظة")
    return jsonify({'success': True})

@app.route('/api/wallet/deduct', methods=['POST'])
@admin_required
def api_deduct_liquidity():
    data = request.get_json()
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'error': 'مبلغ غير صالح'}), 400
    w = get_wallet()
    if amount > w.main_balance:
        return jsonify({'error': 'الرصيد غير كافٍ'}), 400
    w.main_balance -= amount
    db.session.commit()
    log_activity(current_user, "خصم سيولة", f"تم خصم {amount:.2f} ريال من المحفظة")
    return jsonify({'success': True})

@app.route('/api/wallet/capital', methods=['POST'])
@admin_required
def api_update_capital():
    data = request.get_json()
    capital = float(data['capital'])
    if capital <= 0:
        return jsonify({'error': 'قيمة غير صالحة'}), 400
    w = get_wallet()
    w.capital_base = capital
    db.session.commit()
    log_activity(current_user, "تحديث رأس المال", f"تم تعيين رأس المال إلى {capital:.2f} ريال")
    return jsonify({'success': True})

@app.route('/api/products')
@login_required
def api_get_products():
    products = Product.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'cost': p.cost, 'commission': p.commission, 'selling_price': p.selling_price, 'total_price': p.total_price, 'expiry_months': p.expiry_months} for p in products])

@app.route('/api/products', methods=['POST'])
@admin_required
def api_add_product():
    data = request.get_json()
    existing = Product.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({'error': 'منتج بنفس الاسم موجود'}), 400
    product = Product(name=data['name'], cost=float(data['cost']), commission=float(data['commission']), selling_price=float(data['selling_price']), total_price=float(data['total_price']), expiry_months=int(data.get('expiry_months', 0)))
    db.session.add(product)
    db.session.commit()
    log_activity(current_user, "إضافة منتج", f"تمت إضافة منتج: {data['name']}")
    return jsonify({'success': True})

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@admin_required
def api_update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    if 'name' in data:
        existing = Product.query.filter(Product.name == data['name'], Product.id != product_id).first()
        if existing:
            return jsonify({'error': 'منتج بنفس الاسم موجود'}), 400
        product.name = data['name']
    if 'cost' in data:
        product.cost = float(data['cost'])
    if 'commission' in data:
        product.commission = float(data['commission'])
    if 'selling_price' in data:
        product.selling_price = float(data['selling_price'])
    if 'total_price' in data:
        product.total_price = float(data['total_price'])
    if 'expiry_months' in data:
        product.expiry_months = int(data.get('expiry_months', 0))
    db.session.commit()
    log_activity(current_user, "تعديل منتج", f"تم تعديل بيانات المنتج: {product.name}")
    return jsonify({'success': True})

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@admin_required
def api_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    log_activity(current_user, "حذف منتج", f"تم حذف منتج: {product.name}")
    return jsonify({'success': True})

@app.route('/api/employees')
@login_required
def api_get_employees():
    employees = Employee.query.all()
    return jsonify([{'id': e.id, 'name': e.name} for e in employees])

@app.route('/api/employees', methods=['POST'])
@admin_required
def api_add_employee():
    data = request.get_json()
    emp = Employee(name=data['name'])
    db.session.add(emp)
    db.session.commit()
    log_activity(current_user, "إضافة موظف", f"تمت إضافة موظف: {data['name']}")
    return jsonify({'success': True})

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@admin_required
def api_delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    db.session.delete(emp)
    db.session.commit()
    log_activity(current_user, "حذف موظف", f"تم حذف موظف: {emp.name}")
    return jsonify({'success': True})

@app.route('/api/branches')
@login_required
def api_get_branches():
    branches = Branch.query.all()
    return jsonify([{'id': b.id, 'name': b.name, 'debt': b.debt} for b in branches])

@app.route('/api/branches', methods=['POST'])
@admin_required
def api_add_branch():
    data = request.get_json()
    branch = Branch(name=data['name'])
    db.session.add(branch)
    db.session.commit()
    log_activity(current_user, "إضافة فرع", f"تمت إضافة فرع: {data['name']}")
    return jsonify({'success': True})

@app.route('/api/branches/<int:branch_id>', methods=['DELETE'])
@admin_required
def api_delete_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    db.session.delete(branch)
    db.session.commit()
    log_activity(current_user, "حذف فرع", f"تم حذف فرع: {branch.name}")
    return jsonify({'success': True})

@app.route('/api/branches/<int:branch_id>/pay', methods=['POST'])
@admin_required
def api_pay_branch(branch_id):
    data = request.get_json()
    branch = Branch.query.get_or_404(branch_id)
    amount = float(data['amount'])
    if amount <= 0 or amount > branch.debt:
        return jsonify({'error': 'مبلغ غير صالح'}), 400
    branch.debt -= amount
    wallet = get_wallet()
    wallet.main_balance += amount
    payment_log = PaymentLog(branch_name=branch.name, amount=amount)
    db.session.add(payment_log)
    db.session.commit()
    log_activity(current_user, "تسديد مديونية", f"تم تسديد {amount:.2f} ريال من فرع {branch.name}")
    return jsonify({'success': True})

@app.route('/api/payment-logs')
@admin_required
def api_get_payment_logs():
    logs = PaymentLog.query.order_by(PaymentLog.date.desc()).all()
    return jsonify([{'id': l.id, 'date': l.date.strftime('%Y-%m-%d %H:%M'), 'branch_name': l.branch_name, 'amount': l.amount} for l in logs])

@app.route('/api/clear-payment-logs', methods=['DELETE'])
@admin_required
def api_clear_payment_logs():
    PaymentLog.query.delete()
    db.session.commit()
    log_activity(current_user, "مسح سجل التسديدات", "تم مسح جميع سجلات التسديدات")
    return jsonify({'success': True})

@app.route('/api/channels')
@login_required
def api_get_channels():
    channels = Channel.query.all()
    return jsonify([{'id': c.id, 'name': c.name, 'pending_commission': c.pending_commission} for c in channels])

@app.route('/api/channels', methods=['POST'])
@admin_required
def api_add_channel():
    data = request.get_json()
    channel = Channel(name=data['name'])
    db.session.add(channel)
    db.session.commit()
    log_activity(current_user, "إضافة مصدر تفعيل", f"تمت إضافة مصدر: {data['name']}")
    return jsonify({'success': True})

@app.route('/api/channels/<int:channel_id>', methods=['DELETE'])
@admin_required
def api_delete_channel(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    db.session.delete(channel)
    db.session.commit()
    log_activity(current_user, "حذف مصدر تفعيل", f"تم حذف مصدر: {channel.name}")
    return jsonify({'success': True})

@app.route('/api/sales-filtered')
@login_required
def api_get_sales_filtered():
    branch = request.args.get('branch', '')
    employee = request.args.get('employee', '')
    date_from = request.args.get('dateFrom', '')
    date_to = request.args.get('dateTo', '')
    phone = request.args.get('phone', '')
    query = Sale.query
    if branch:
        query = query.filter_by(branch_name=branch)
    if employee:
        query = query.filter_by(employee_name=employee)
    if date_from:
        query = query.filter(Sale.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Sale.date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    if phone:
        query = query.filter(Sale.customer_phone.contains(phone))
    sales = query.order_by(Sale.date.desc()).all()
    return jsonify([{'order_id': s.order_id, 'date': s.date.strftime('%Y-%m-%d %H:%M'), 'customer_name': s.customer_name, 'customer_phone': s.customer_phone, 'product_name': s.product_name, 'selling_price': s.selling_price, 'total_price': s.total_price, 'branch_name': s.branch_name, 'employee_name': s.employee_name, 'net_profit': s.net_profit, 'commission': s.commission, 'cost': s.cost} for s in sales])

@app.route('/api/sales/<order_id>', methods=['DELETE'])
@admin_required
def api_delete_sale(order_id):
    sale = Sale.query.filter_by(order_id=order_id).first()
    if not sale:
        return jsonify({'error': 'الفاتورة غير موجودة'}), 404
    if sale.commission_status == 'collected':
        return jsonify({'error': 'لا يمكن حذف فاتورة تم تحصيل عمولتها. قم باسترداد العمولة أولاً.'}), 400
    wallet = get_wallet()
    wallet.main_balance += sale.selling_price
    branch = Branch.query.filter_by(name=sale.branch_name).first()
    if branch:
        branch.debt -= sale.selling_price
    channel = Channel.query.filter_by(name=sale.channel_name).first()
    if channel:
        channel.pending_commission -= sale.commission
    wallet.pending_commission -= sale.commission
    db.session.delete(sale)
    db.session.commit()
    log_activity(current_user, "حذف فاتورة", f"تم حذف فاتورة رقم: {order_id} واسترجاع المبلغ {sale.selling_price:.2f} ريال")
    return jsonify({'success': True})

@app.route('/api/sales/<order_id>/price', methods=['PUT'])
@admin_required
def api_update_sale_price(order_id):
    sale = Sale.query.filter_by(order_id=order_id).first_or_404()
    data = request.get_json()
    new_price = float(data.get('selling_price'))
    if new_price <= 0:
        return jsonify({'error': 'سعر غير صالح'}), 400
    old_price = sale.selling_price
    diff = new_price - old_price
    sale.selling_price = new_price
    sale.total_price = new_price
    sale.net_profit = new_price - sale.cost - sale.commission
    wallet = get_wallet()
    if diff > 0:
        if wallet.main_balance < diff:
            return jsonify({'error': f'رصيد المحفظة غير كافٍ لتغطية الزيادة (المطلوب: {diff:.2f} ريال)'}), 400
        wallet.main_balance -= diff
    else:
        wallet.main_balance += (-diff)
    branch = Branch.query.filter_by(name=sale.branch_name).first()
    if branch:
        branch.debt += diff
    db.session.commit()
    log_activity(current_user, "تعديل سعر فاتورة", f"الفاتورة {order_id}: تغيير السعر من {old_price} إلى {new_price} (فرق {diff:+.2f})")
    return jsonify({'success': True})

@app.route('/api/sale', methods=['POST'])
@login_required
def api_create_sale():
    data = request.get_json()
    wallet = get_wallet()
    if wallet.main_balance < data['selling_price']:
        return jsonify({'error': f'رصيد المحفظة غير كافٍ (المتاح: {wallet.main_balance:.2f} ريال)'}), 400
    existing = Sale.query.filter_by(order_id=data['order_id']).first()
    if existing:
        return jsonify({'error': 'رقم الفاتورة موجود مسبقاً'}), 400
    expiry_date = None
    if data.get('expiry_months', 0) > 0:
        expiry_date = datetime.utcnow() + relativedelta(months=int(data['expiry_months']))
    net_profit = data['selling_price'] - data['cost'] - data['commission']
    sale = Sale(order_id=data['order_id'], due_date=datetime.utcnow() + timedelta(days=60), expiry_date=expiry_date, customer_name=data['customer_name'], customer_phone=data['customer_phone'], customer_id_number=data.get('customer_id',''), product_name=data['product'], cost=data['cost'], commission=data['commission'], selling_price=data['selling_price'], total_price=data['selling_price'], employee_name=data['employee'], branch_name=data['branch'], channel_name=data['channel'], payment_method=data['payment_method'], net_profit=net_profit, notes=data.get('notes',''))
    db.session.add(sale)
    branch = Branch.query.filter_by(name=data['branch']).first()
    if branch:
        branch.debt += data['selling_price']
    channel = Channel.query.filter_by(name=data['channel']).first()
    if channel:
        channel.pending_commission += data['commission']
    wallet.main_balance -= data['selling_price']
    wallet.pending_commission += data['commission']
    db.session.commit()
    log_activity(current_user, "إنشاء فاتورة", f"تم إنشاء فاتورة رقم: {data['order_id']} بقيمة {data['selling_price']:.2f} ريال")
    return jsonify({'success': True, 'order_id': data['order_id']})

@app.route('/api/commissions/collect', methods=['POST'])
@admin_required
def api_collect_commission():
    data = request.get_json()
    channel_id = int(data.get('channelId'))
    amount = float(data['amount'])
    target = data.get('target', 'wallet')
    channel = Channel.query.get_or_404(channel_id)
    wallet = get_wallet()
    if amount <= 0:
        return jsonify({'error': 'المبلغ يجب أن يكون أكبر من صفر'}), 400
    if amount > channel.pending_commission:
        return jsonify({'error': f'المبلغ أكبر من الرصيد المتاح لهذا المصدر ({channel.pending_commission:.2f} ريال)'}), 400
    channel.pending_commission -= amount
    wallet.pending_commission -= amount
    if target == 'wallet':
        wallet.main_balance += amount
    else:
        wallet.profits += amount
    db.session.commit()
    log_activity(current_user, "تحصيل عمولة", f"تم تحصيل {amount:.2f} ريال من {channel.name} (المتبقي: {channel.pending_commission:.2f}) إلى {'المحفظة' if target=='wallet' else 'الأرباح'}")
    return jsonify({'success': True, 'collected': amount, 'channelName': channel.name, 'remaining': channel.pending_commission})

@app.route('/api/company-info', methods=['POST'])
@admin_required
def api_update_company_info():
    data = request.get_json()
    info = get_company_info()
    info.name = data.get('name', 'البرنامج الذكي')
    info.address = data.get('address', '')
    info.tax_number = data.get('tax_number', '')
    info.phone = data.get('phone', '')
    info.commercial_reg = data.get('commercial_reg', '')
    db.session.commit()
    log_activity(current_user, "تحديث بيانات الشركة", "تم تحديث معلومات الشركة")
    return jsonify({'success': True})

@app.route('/api/activity-log/search')
@admin_required
def api_search_activity():
    search_term = request.args.get('q', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    user_name = request.args.get('user', '')
    query = ActivityLog.query
    if search_term:
        query = query.filter(or_(ActivityLog.action.contains(search_term), ActivityLog.details.contains(search_term)))
    if date_from:
        query = query.filter(ActivityLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(ActivityLog.timestamp <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    if user_name:
        query = query.filter(ActivityLog.user_name == user_name)
    logs = query.order_by(ActivityLog.timestamp.desc()).limit(200).all()
    return jsonify([{'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 'user_name': log.user_name, 'action': log.action, 'details': log.details[:100], 'ip_address': log.ip_address} for log in logs])

@app.route('/api/invoice/print/<order_id>')
@login_required
def print_invoice(order_id):
    sale = Sale.query.filter_by(order_id=order_id).first_or_404()
    company = get_company_info()
    default_note = get_default_invoice_note()
    logo = get_logo_base64()
    logo_html = f'<img src="{logo}" style="max-width: 80px; margin-bottom: 15px;">' if logo else ''
    notes = sale.notes if sale.notes else default_note
    expiry_html = ''
    if sale.expiry_date:
        expiry_html = f'<div class="info-row"><span class="info-label">📅 تاريخ الانتهاء:</span><span class="info-value">{sale.expiry_date.strftime("%Y-%m-%d")}</span></div>'
    company_name = company.name if company.name else "البرنامج الذكي"
    html = f'''
    <!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>فاتورة {sale.order_id}</title><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');*{{margin:0;padding:0;box-sizing:border-box;}}body{{font-family:'Tajawal',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;}}.invoice{{max-width:500px;width:100%;margin:auto;background:white;border-radius:25px;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);}}.invoice-header{{background:linear-gradient(135deg,#00b4d8 0%,#0077b6 100%);color:white;padding:25px;text-align:center;}}.invoice-header h1{{font-size:22px;}}.invoice-body{{padding:25px;}}.company-info{{background:#f0f9ff;border-radius:15px;padding:12px;margin-bottom:15px;font-size:12px;text-align:center;}}.customer-info{{background:#f8f9fa;border-radius:15px;padding:15px;margin-bottom:20px;}}.total{{background:linear-gradient(135deg,#00b4d8,#0077b6);color:white;padding:15px;border-radius:15px;text-align:center;margin:20px 0;}}.footer{{text-align:center;padding:15px;background:#f8f9fa;font-size:11px;}}.info-row{{display:flex;justify-content:space-between;margin-bottom:8px;}}.whatsapp-btn{{display:inline-block;background:#25D366;color:white;padding:12px 20px;border-radius:50px;text-decoration:none;font-weight:bold;margin-top:15px;text-align:center;width:100%;box-sizing:border-box;}}.whatsapp-btn:hover{{background:#128C7E;}}@media (max-width:600px){{.invoice-header{{padding:15px;}}.invoice-body{{padding:15px;}}.total{{padding:10px;}}}}</style></head><body><div class="invoice"><div class="invoice-header">{logo_html}<h1>{company_name}</h1><p>فاتورة رقم: {sale.order_id}</p><p>{sale.date.strftime('%Y-%m-%d %H:%M')}</p></div><div class="invoice-body"><div class="company-info"><div>{company.name if company.name else ''}</div><div>{company.address if company.address else ''}</div><div>سجل تجاري: {company.commercial_reg if company.commercial_reg else ''} | الرقم الضريبي: {company.tax_number if company.tax_number else ''}</div><div>هاتف: {company.phone if company.phone else ''}</div></div><div class="customer-info"><div class="info-row"><span>👤 العميل:</span><span>{sale.customer_name}</span></div><div class="info-row"><span>📞 الجوال:</span><span>{sale.customer_phone}</span></div><div class="info-row"><span>📍 الفرع:</span><span>{sale.branch_name}</span></div><div class="info-row"><span>👨‍💼 الموظف:</span><span>{sale.employee_name}</span></div>{expiry_html}</div><div class="info-row"><span>المنتج:</span><span class="font-bold">{sale.product_name}</span></div><div class="info-row"><span>طريقة الدفع:</span><span>{sale.payment_method}</span></div><div class="total"><div>الإجمالي</div><div class="font-bold text-2xl">{sale.selling_price:,.2f} ريال</div></div>{f'<div class="notes p-3 bg-yellow-100 text-yellow-800 rounded-xl my-3"><strong>ملاحظات:</strong><br>{notes}</div>' if notes else ''}<a href="/api/invoice/whatsapp/{sale.order_id}" target="_blank" class="whatsapp-btn"><i class="fab fa-whatsapp"></i> 📱 إرسال الفاتورة عبر واتساب</a></div><div class="footer"><p>{FOOTER_TEXT}</p></div></div><script>setTimeout(() => window.print(), 500);</script></body></html>'''
    return html

@app.route('/api/invoice/whatsapp/<order_id>')
@login_required
def whatsapp_invoice(order_id):
    sale = Sale.query.filter_by(order_id=order_id).first_or_404()
    base_url = request.url_root.rstrip('/')
    invoice_url = f"{base_url}/api/invoice/print/{order_id}"
    message = f"""🛒 *فاتورة رقم: {sale.order_id}*\n💰 المبلغ: {sale.selling_price:,.2f} ريال\n📄 اضغط لفتح الفاتورة: {invoice_url}\n📱 يمكنك طباعتها كـ PDF من المتصفح.\n\n{FOOTER_TEXT}"""
    encoded_msg = urllib.parse.quote(message)
    phone_number = sale.customer_phone.strip()
    if not phone_number.startswith('966') and not phone_number.startswith('05'):
        phone_number = '966' + phone_number.lstrip('0')
    elif phone_number.startswith('05'):
        phone_number = '966' + phone_number[1:]
    whatsapp_url = f"https://wa.me/{phone_number}?text={encoded_msg}"
    return redirect(whatsapp_url)

@app.route('/api/logo', methods=['GET'])
@login_required
def api_get_logo():
    logo = get_logo_base64()
    return jsonify({'logo': logo})

@app.route('/api/upload-logo', methods=['POST'])
@admin_required
def api_upload_logo():
    if 'logo' not in request.files:
        return jsonify({'error': 'لا توجد صورة'}), 400
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400
    if file:
        file_data = file.read()
        base64_data = base64.b64encode(file_data).decode('utf-8')
        mime_type = file.content_type
        logo_data = f"data:{mime_type};base64,{base64_data}"
        setting = SystemSettings.query.filter_by(key='logo_base64').first()
        if setting:
            setting.value = logo_data
        else:
            setting = SystemSettings(key='logo_base64', value=logo_data)
            db.session.add(setting)
        db.session.commit()
        log_activity(current_user, "رفع شعار", "تم تغيير شعار الشركة")
        return jsonify({'success': True})
    return jsonify({'error': 'فشل الرفع'}), 400

@app.route('/api/invoice/default-note', methods=['GET'])
@login_required
def api_get_default_note():
    note = get_default_invoice_note()
    return jsonify({'note': note})

@app.route('/api/invoice/default-note', methods=['POST'])
@admin_required
def api_update_default_note():
    data = request.get_json()
    setting = SystemSettings.query.filter_by(key='default_invoice_note').first()
    if setting:
        setting.value = data['note']
    else:
        setting = SystemSettings(key='default_invoice_note', value=data['note'])
        db.session.add(setting)
    db.session.commit()
    log_activity(current_user, "تحديث نص الفاتورة", "تم تغيير النص الثابت للفاتورة")
    return jsonify({'success': True})

@app.route('/api/reset-system', methods=['POST'])
@admin_required
def api_reset_system():
    data = request.get_json()
    password = data.get('password')
    admin = User.query.filter_by(username='admin').first()
    if not admin or not admin.check_password(password):
        return jsonify({'error': 'كلمة المرور غير صحيحة'}), 401
    db.drop_all()
    db.create_all()
    init_db()
    log_activity(current_user, "تهيئة النظام", "تمت تهيئة النظام بالكامل وحذف جميع البيانات")
    return jsonify({'success': True})

@app.route('/api/users', methods=['GET'])
@admin_required
def api_get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'name': u.name, 'role': u.role} for u in users])

@app.route('/api/users', methods=['POST'])
@admin_required
def api_add_user():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'اسم المستخدم موجود'}), 400
    user = User(username=data['username'], name=data['name'], role=data['role'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    log_activity(current_user, "إضافة مستخدم", f"تمت إضافة مستخدم: {data['username']}")
    return jsonify({'success': True})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        return jsonify({'error': 'لا يمكن حذف المستخدم admin'}), 400
    db.session.delete(user)
    db.session.commit()
    log_activity(current_user, "حذف مستخدم", f"تم حذف مستخدم: {user.username}")
    return jsonify({'success': True})

@app.route('/api/export-excel')
@login_required
def export_excel():
    branch = request.args.get('branch', '')
    employee = request.args.get('employee', '')
    date_from = request.args.get('dateFrom', '')
    date_to = request.args.get('dateTo', '')
    phone = request.args.get('phone', '')
    selected_cols = request.args.get('cols', '').split(',') if request.args.get('cols') else []
    query = Sale.query
    if branch:
        query = query.filter_by(branch_name=branch)
    if employee:
        query = query.filter_by(employee_name=employee)
    if date_from:
        query = query.filter(Sale.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Sale.date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    if phone:
        query = query.filter(Sale.customer_phone.contains(phone))
    sales = query.order_by(Sale.date.desc()).all()
    
    column_map = {
        'date': 'التاريخ', 'order_id': 'رقم الطلب', 'customer_name': 'اسم العميل',
        'customer_phone': 'رقم الجوال', 'product_name': 'المنتج', 'branch_name': 'الفرع',
        'employee_name': 'الموظف', 'selling_price': 'سعر البيع', 'payment_method': 'طريقة الدفع',
        'channel_name': 'مصدر التفعيل', 'notes': 'الملاحظات', 'cost': 'التكلفة',
        'commission': 'العمولة', 'net_profit': 'صافي الربح'
    }
    if not selected_cols or selected_cols == ['']:
        selected_cols = ['date','order_id','customer_name','customer_phone','product_name','branch_name','employee_name','selling_price','payment_method']
    
    data = []
    for s in sales:
        row = {}
        if 'date' in selected_cols:
            row['التاريخ'] = s.date.strftime('%Y-%m-%d %H:%M')
        if 'order_id' in selected_cols:
            row['رقم الطلب'] = s.order_id
        if 'customer_name' in selected_cols:
            row['اسم العميل'] = s.customer_name
        if 'customer_phone' in selected_cols:
            row['رقم الجوال'] = s.customer_phone
        if 'product_name' in selected_cols:
            row['المنتج'] = s.product_name
        if 'branch_name' in selected_cols:
            row['الفرع'] = s.branch_name
        if 'employee_name' in selected_cols:
            row['الموظف'] = s.employee_name
        if 'selling_price' in selected_cols:
            row['سعر البيع'] = s.selling_price
        if 'payment_method' in selected_cols:
            row['طريقة الدفع'] = s.payment_method
        if 'channel_name' in selected_cols:
            row['مصدر التفعيل'] = s.channel_name
        if 'notes' in selected_cols:
            row['الملاحظات'] = s.notes
        if 'cost' in selected_cols and current_user.role == 'admin':
            row['التكلفة'] = s.cost
        if 'commission' in selected_cols and current_user.role == 'admin':
            row['العمولة'] = s.commission
        if 'net_profit' in selected_cols and current_user.role == 'admin':
            row['صافي الربح'] = s.net_profit
        data.append(row)
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='المبيعات', index=False)
    output.seek(0)
    return send_file(output, download_name=f'تقرير_المبيعات_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx', as_attachment=True)

@app.route('/api/print-report')
@login_required
def print_report():
    branch = request.args.get('branch', '')
    employee = request.args.get('employee', '')
    date_from = request.args.get('dateFrom', '')
    date_to = request.args.get('dateTo', '')
    phone = request.args.get('phone', '')
    selected_cols = request.args.get('cols', '').split(',') if request.args.get('cols') else []
    query = Sale.query
    if branch:
        query = query.filter_by(branch_name=branch)
    if employee:
        query = query.filter_by(employee_name=employee)
    if date_from:
        query = query.filter(Sale.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Sale.date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    if phone:
        query = query.filter(Sale.customer_phone.contains(phone))
    sales = query.order_by(Sale.date.desc()).all()
    
    if not selected_cols or selected_cols == ['']:
        selected_cols = ['date','order_id','customer_name','customer_phone','product_name','branch_name','employee_name','selling_price','payment_method']
    
    headers = []
    for col in selected_cols:
        if col == 'date': headers.append('التاريخ')
        elif col == 'order_id': headers.append('رقم الطلب')
        elif col == 'customer_name': headers.append('اسم العميل')
        elif col == 'customer_phone': headers.append('رقم الجوال')
        elif col == 'product_name': headers.append('المنتج')
        elif col == 'branch_name': headers.append('الفرع')
        elif col == 'employee_name': headers.append('الموظف')
        elif col == 'selling_price': headers.append('سعر البيع')
        elif col == 'payment_method': headers.append('طريقة الدفع')
        elif col == 'channel_name': headers.append('مصدر التفعيل')
        elif col == 'notes': headers.append('الملاحظات')
        elif col == 'cost' and current_user.role == 'admin': headers.append('التكلفة')
        elif col == 'commission' and current_user.role == 'admin': headers.append('العمولة')
        elif col == 'net_profit' and current_user.role == 'admin': headers.append('صافي الربح')
    
    rows = ''
    for s in sales:
        row_cells = ''
        for col in selected_cols:
            if col == 'date': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.date.strftime("%Y-%m-%d %H:%M")}</td>'
            elif col == 'order_id': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.order_id}</td>'
            elif col == 'customer_name': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.customer_name}</td>'
            elif col == 'customer_phone': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.customer_phone}</td>'
            elif col == 'product_name': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.product_name}</td>'
            elif col == 'branch_name': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.branch_name}</td>'
            elif col == 'employee_name': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.employee_name}</td>'
            elif col == 'selling_price': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.selling_price:,.2f}</td>'
            elif col == 'payment_method': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.payment_method}</td>'
            elif col == 'channel_name': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.channel_name}</td>'
            elif col == 'notes': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.notes}</td>'
            elif col == 'cost' and current_user.role == 'admin': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.cost:,.2f}</td>'
            elif col == 'commission' and current_user.role == 'admin': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.commission:,.2f}</td>'
            elif col == 'net_profit' and current_user.role == 'admin': row_cells += f'<td style="border:1px solid #ddd;padding:8px">{s.net_profit:,.2f}</td>'
        rows += f'<tr>{row_cells}</tr>'
    
    total_sales = sum(s.selling_price for s in sales)
    total_purchases = sum(s.total_price for s in sales)
    total_commission = sum(s.commission for s in sales)
    total_profit = total_sales + total_commission - total_purchases
    
    html = f'''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تقرير المبيعات</title><style>body{{font-family:'Tajawal',sans-serif;padding:20px;}}table{{width:100%;border-collapse:collapse;}}th,td{{border:1px solid #ddd;padding:8px;text-align:center;}}th{{background:#0f3460;color:white;}}@media (max-width:600px){{th,td{{padding:4px;font-size:12px;}}}}</style></head><body><div style="text-align:center;margin-bottom:20px;"><h1>📊 تقرير المبيعات</h1><p>البرنامج الذكي - {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div><div style="display:flex;justify-content:space-around;margin:20px 0;flex-wrap:wrap;"><div><strong>عدد الفواتير:</strong><br>{len(sales)}</div><div><strong>إجمالي المبيعات (سعر البيع):</strong><br>{total_sales:,.2f} ريال</div><div><strong>إجمالي المشتريات (السعر الشامل):</strong><br>{total_purchases:,.2f} ريال</div><div><strong>إجمالي العمولات:</strong><br>{total_commission:,.2f} ريال</div><div><strong>صافي الربح:</strong><br>{total_profit:,.2f} ريال</div></div><table><thead><tr>{''.join(f'<th>{h}</th>' for h in headers)}</thead><tbody>{rows}</tbody>收入<div style="text-align:center;margin-top:20px;"><p>{FOOTER_TEXT}</p></div><script>window.print();</script></body></html>'''
    return html

# ==================== التشغيل ====================
with app.app_context():
    init_db()
    print("=" * 50)
    print("✅ قاعدة البيانات جاهزة!")
    print("👤 المدير: admin / admin123")
    print("👤 الكاشير: ali / 1234")
    print("=" * 50)
    print("📊 الميزات النهائية بعد التعديلات:")
    print("  ✅ تعديل المنتجات (نافذة منبثقة احترافية)")
    print("  ✅ رسوم بيانية في لوحة التحكم")
    print("  ✅ تغيير كلمة المرور من الملف الشخصي")
    print("  ✅ تعديل سعر الفاتورة من التقارير (مع تحديث المحفظة والمديونية)")
    print("  ✅ حذف الفاتورة مع استرجاع سعر البيع وتحديث المديونية والعمولات")
    print("  ✅ منع حذف الفاتورة إذا تم تحصيل عمولتها")
    print("  ✅ بحث متقدم في سجل العمليات")
    print("  ✅ إرسال الفاتورة عبر واتساب (رابط صفحة الطباعة)")
    print("  ✅ نسخ احتياطي واستعادة")
    print("  ✅ **تعديل: المديونية تسجل سعر البيع وليس السعر الشامل**")
    print("  ✅ **تعديل: في صفحة المبيعات يظهر سعر البيع فقط وليس السعر الشامل**")
    print("  ✅ **تعديل: التقارير بها نافذة منبثقة لاختيار الأعمدة قبل التصدير أو الطباعة**")
    print("  ✅ **تعديل: النوافذ المنبثقة أكثر احترافية (modal-overlay, modal-container, تأثير scale)**")
    print("  ✅ **تعديل: الكاشير لا يرى التكاليف والأرباح والموازنة**")
    print("  ✅ **تعديل: رأس المال ثابت لا يتغير عند تحويل العمولات إلى أرباح**")
    print("  ✅ صلاحية المنتج بالأشهر")
    print("  ✅ تحصيل جزئي للعمولة")
    print("=" * 50)

if __name__ == '__main__':
    app.run()
