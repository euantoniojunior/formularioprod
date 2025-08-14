import os
from flask import Flask, request, render_template, send_file, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from sqlalchemy import text
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

# Tempo de expiração da sessão (1 hora)
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

# Inicializa o banco
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Credenciais do admin
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
    servico = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(50), nullable=False)
    data_hora = db.Column(
        db.String(50),
        nullable=False,
        default=lambda: datetime.now(pytz.timezone("America/Rio_Branco")).strftime("%Y-%m-%d %H:%M:%S")
    )

    # Restrição: CPF + Serviço únicos
    __table_args__ = (db.UniqueConstraint('cpf', 'servico', name='_cpf_servico_uc'),)


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


# Função para criar coluna 'servico' e restrição única
def verificar_e_criar_coluna_servico():
    with app.app_context():
        conn = db.engine.connect()
        try:
            result = conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'inscricao' AND column_name = 'servico'
                """)
            )
            if not result.fetchone():
                conn.execute(text("ALTER TABLE inscricao ADD COLUMN servico VARCHAR(100)"))
                conn.commit()
                print("✅ Coluna 'servico' criada com sucesso!")

            result = conn.execute(
                text("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'inscricao' 
                    AND constraint_name = '_cpf_servico_uc'
                """)
            )
            if not result.fetchone():
                try:
                    conn.execute(text("""
                        ALTER TABLE inscricao 
                        ADD CONSTRAINT _cpf_servico_uc 
                        UNIQUE (cpf, servico)
                    """))
                    conn.commit()
                    print("✅ Restrição única (CPF + Serviço) adicionada.")
                except Exception as e:
                    print(f"⚠️ A restrição já pode existir: {e}")
                    conn.rollback()
        except Exception as e:
            print(f"❌ Erro ao verificar/criar coluna ou restrição: {e}")
        finally:
            conn.close()


# Cria tabelas e verifica coluna
with app.app_context():
    db.create_all()
    verificar_e_criar_coluna_servico()


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
            session.permanent = True
            flash("✅ Login realizado com sucesso!", "success")
            return redirect(url_for('visualizar_registros'))
        else:
            flash("❌ Usuário ou senha inválidos.", "danger")

    return render_template('login.html')


# Rota de logout
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("Você saiu da área administrativa.", "info")
    return redirect(url_for('index'))


# Rota principal
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        cpf = request.form.get('cpf').replace('.', '').replace('-', '')
        fone = request.form.get('fone')
        servico = request.form.get('servico')

        # Validação de campos obrigatórios
        form_erros = []
        if not nome: form_erros.append('nome')
        if not email: form_erros.append('email')
        if not cpf: form_erros.append('cpf')
        if not fone: form_erros.append('fone')
        if not servico: form_erros.append('servico')

        if form_erros:
            return render_template('form.html',
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico,
                                   form_erros=form_erros)

        if not validar_cpf(cpf):
            return render_template('form.html',
                                   erro_cpf="❌ CPF inválido.",
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico)

        # Força nova conexão
        db.session.close()

        # Verifica duplicidade CPF + Serviço
        ja_existe = Inscricao.query.filter_by(cpf=cpf, servico=servico).first()
        if ja_existe:
            return render_template('form.html',
                                   erro_cpf="❌ Você já está inscrito neste serviço/evento.",
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico)

        ip_usuario = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        nova_inscricao = Inscricao(
            nome=nome,
            email=email,
            cpf=cpf,
            fone=fone,
            servico=servico,
            ip=ip_usuario
        )
        try:
            db.session.add(nova_inscricao)
            db.session.commit()
            flash("✅ Inscrição realizada com sucesso!", "success")
            return redirect(url_for('success'))
        except IntegrityError:
            db.session.rollback()
            return render_template('form.html',
                                   erro_cpf="❌ Você já está inscrito neste serviço/evento.",
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico)
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Erro ao salvar: {str(e)}", "danger")
            return render_template('form.html',
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico)

    return render_template('form.html')


# Rota de sucesso
@app.route('/success')
def success():
    return render_template('success.html')


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
                "Serviço": r.servico,
                "IP": r.ip,
                "Data/Hora": r.data_hora
            } for r in registros]
            df = pd.DataFrame(data)
            excel_file = "inscricoes.xlsx"
            df.to_excel(excel_file, index=False, engine="openpyxl")
            return send_file(excel_file, as_attachment=True)
        flash("Nenhum dado para exportar.", "warning")
        return redirect(url_for('visualizar_registros'))
    except Exception as e:
        flash("Erro ao exportar.", "danger")
        return redirect(url_for('visualizar_registros'))


# Exportar para CSV
@app.route('/download')
def download_file():
    try:
        registros = Inscricao.query.all()
        csv_file = "inscricoes.csv"
        if registros:
            with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
                file.write("ID,Nome,Email,CPF,Fone,Serviço,IP,Data/Hora\n")
                for r in registros:
                    file.write(f"{r.id},{r.nome},{r.email},{r.cpf},{r.fone},{r.servico},{r.ip},{r.data_hora}\n")
            return send_file(csv_file, as_attachment=True)
        flash("Nenhum dado para exportar.", "warning")
        return redirect(url_for('visualizar_registros'))
    except Exception as e:
        flash("Erro ao gerar CSV.", "danger")
        return redirect(url_for('visualizar_registros'))


# Visualizar registros (com autenticação)
@app.route('/visualizar', methods=['GET', 'POST'])
@login_requerido
def visualizar_registros():
    if request.method == 'POST':
        if request.form.get('limpar_tudo'):
            db.session.close()
            try:
                db.session.query(Inscricao).delete()
                db.session.commit()
                flash("Todos os registros foram excluídos.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Erro ao limpar registros.", "danger")
        elif request.form.get('excluir'):
            id_excluir = request.form.get('excluir')
            db.session.close()
            try:
                db.session.query(Inscricao).filter_by(id=id_excluir).delete()
                db.session.commit()
                flash("Registro excluído com sucesso.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Erro ao excluir registro.", "danger")

    registros = Inscricao.query.all()
    return render_template('visualizar.html', registros=registros)


# Limpar tabelas
@app.route('/limpar_tabelas', methods=['POST'])
def limpar_tabelas():
    try:
        db.session.query(Inscricao).delete()
        db.session.commit()
        flash("Tabelas limpas.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao limpar: {e}", "danger")
    return redirect(url_for('index'))


# Iniciar aplicação
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
