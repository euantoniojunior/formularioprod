import os
from flask import Flask, request, render_template, send_file, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from functools import wraps
import hashlib

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-for-dev')

# Configuração do Banco de Dados
uri = os.getenv("DATABASE_URL", "sqlite:///local.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
if uri.startswith("postgresql://") and "?sslmode=" not in uri:
    if "localhost" not in uri and "127.0.0.1" not in uri:
        uri += "?sslmode=require"
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicializa o banco
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Credenciais do admin (senha em hash)
ADMIN_USER = "admin"
ADMIN_PASS_HASH = hashlib.sha256(os.getenv("ADMIN_PASSWORD", "senac123").encode()).hexdigest()

# Modelo da Tabela Inscrições
class Inscricao(db.Model):
    __tablename__ = 'inscricao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), nullable=False)
    fone = db.Column(db.String(20), nullable=False)
    ip = db.Column(db.String(50), nullable=False)
    data_hora = db.Column(
        db.String(50),
        nullable=False,
        default=lambda: datetime.now(pytz.timezone("America/Rio_Branco")).strftime("%Y-%m-%d %H:%M:%S")
    )

    # Garante que o mesmo CPF não se inscreva duas vezes
    __table_args__ = (db.UniqueConstraint('cpf', name='_cpf_uc'),)


# Função de validação de CPF
def validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito1 = resto if resto < 10 else 0
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito2 = resto if resto < 10 else 0
    return cpf[-2:] == f"{digito1}{digito2}"


# Garante que a tabela seja criada ao iniciar a aplicação
with app.app_context():
    db.create_all()


# Decorador para exigir login
def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        pass_hash = hashlib.sha256(password.encode()).hexdigest()

        if username == ADMIN_USER and pass_hash == ADMIN_PASS_HASH:
            session['logged_in'] = True
            flash("✅ Login realizado com sucesso!", "success")
            return redirect(url_for('visualizar_registros'))
        else:
            flash("❌ Usuário ou senha inválidos.", "danger")

    return '''
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; text-align: center; padding: 50px; }
        .container { background: white; width: 90%; max-width: 400px; margin: auto; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        input, button { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px; font-size: 16px; }
        button { background: #F39200; color: white; border: none; cursor: pointer; }
        button:hover { background: #D17A00; }
        .flash { color: #721c24; background: #f8d7da; padding: 10px; border-radius: 5px; margin: 10px 0; }
    </style>
    <div class="container">
        <h2>Login Admin</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="post">
            <input type="text" name="username" placeholder="Usuário" required>
            <input type="password" name="password" placeholder="Senha" required>
            <button type="submit">Entrar</button>
        </form>
    </div>
    '''


# Rota de logout
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("Você saiu da área administrativa.", "info")
    return redirect(url_for('index'))


# Rota principal com formulário
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        cpf = request.form.get('cpf').replace('.', '').replace('-', '')
        fone = request.form.get('fone')

        if not nome or not email or not cpf or not fone:
            flash("⚠️ Todos os campos são obrigatórios.", "danger")
            return render_template('form.html',
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone)

        if not validar_cpf(cpf):
            erro_cpf = "❌ CPF inválido. Deve ter 11 dígitos válidos."
            return render_template('form.html',
                                   erro_cpf=erro_cpf,
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone)

        ip_usuario = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        nova_inscricao = Inscricao(nome=nome, email=email, cpf=cpf, fone=fone, ip=ip_usuario)
        try:
            db.session.add(nova_inscricao)
            db.session.commit()
            flash("✅ Inscrição realizada com sucesso!", "success")
            return redirect(url_for('index'))
        except IntegrityError:
            db.session.rollback()
            flash("❌ Erro: Este CPF já está cadastrado.", "danger")
            return render_template('form.html',
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone)
        except Exception as e:
            db.session.rollback()
            flash(f"⚠️ Erro ao salvar os dados: {str(e)}", "danger")
            return render_template('form.html',
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone)
    return render_template('form.html')


# Exportar para Excel
@app.route('/baixar_excel')
def baixar_excel():
    try:
        registros = Inscricao.query.all()
        if registros:
            data = [{
                "ID": r.id,
                "Nome": r.nome,
                "Email": r.email,
                "CPF": r.cpf,
                "Fone": r.fone,
                "IP": r.ip,
                "Data/Hora": r.data_hora
            } for r in registros]
            df = pd.DataFrame(data)
            excel_file = "inscricoes.xlsx"
            df.to_excel(excel_file, index=False, engine="openpyxl")
            return send_file(excel_file, as_attachment=True)
        flash("Nenhum dado disponível para exportação.", "warning")
        return redirect(url_for('index'))
    except Exception as e:
        flash("⚠️ Erro ao acessar os dados. Tente novamente mais tarde.", "danger")
        return redirect(url_for('index'))


# Exportar para CSV
@app.route('/download')
def download_file():
    try:
        registros = Inscricao.query.all()
        csv_file = "inscricoes.csv"
        if registros:
            with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
                file.write("ID,Nome,Email,CPF,Fone,IP,Data/Hora\n")
                for r in registros:
                    file.write(f"{r.id},{r.nome},{r.email},{r.cpf},{r.fone},{r.ip},{r.data_hora}\n")
            return send_file(csv_file, as_attachment=True)
        flash("Nenhum dado disponível para exportação.", "warning")
        return redirect(url_for('index'))
    except Exception as e:
        flash("⚠️ Erro ao gerar arquivo. Tente novamente.", "danger")
        return redirect(url_for('index'))


# Visualizar registros (protegido por login)
@app.route('/visualizar', methods=['GET', 'POST'])
@login_requerido
def visualizar_registros():
    if request.method == 'POST':
        if request.form.get('limpar_tudo'):
            db.session.query(Inscricao).delete()
            db.session.commit()
            flash("Todos os registros foram excluídos.", "success")
        elif request.form.get('excluir'):
            id_excluir = request.form.get('excluir')
            Inscricao.query.filter_by(id=id_excluir).delete()
            db.session.commit()
            flash("Registro excluído com sucesso.", "success")
    registros = Inscricao.query.all()
    return render_template('visualizar.html', registros=registros)


# Limpa tabelas
@app.route('/limpar_tabelas', methods=['POST'])
def limpar_tabelas():
    try:
        db.session.query(Inscricao).delete()
        db.session.commit()
        flash("Todas as tabelas foram limpas com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao limpar as tabelas: {e}", "danger")
    return redirect(url_for('index'))


# Roda a aplicação
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
