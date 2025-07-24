import os
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-for-dev')

# Configuração do Banco de Dados (mantida igual ao original)
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


# Modelo da Tabela Inscrições (com campo 'servico')
class Inscricao(db.Model):
    __tablename__ = 'inscricao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), nullable=False, unique=True)
    fone = db.Column(db.String(20), nullable=False)
    servico = db.Column(db.String(100), nullable=True)  # Novo campo
    ip = db.Column(db.String(50), nullable=False)
    data_hora = db.Column(
        db.String(50),
        nullable=False,
        default=lambda: datetime.now(pytz.timezone("America/Rio_Branco")).strftime("%Y-%m-%d %H:%M:%S")
    )


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


# Função para criar coluna 'servico' se não existir
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
            else:
                print("ℹ️ Coluna 'servico' já existe.")
        except Exception as e:
            print(f"❌ Erro ao criar coluna: {e}")
        finally:
            conn.close()


# Cria tabelas e verifica coluna
with app.app_context():
    db.create_all()
    verificar_e_criar_coluna_servico()


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
                                   nome=nome,
                                   email=email,
                                   cpf=cpf,
                                   fone=fone,
                                   servico=servico,
                                   form_erros=['cpf_duplicado'])
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
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


# Visualizar registros
@app.route('/visualizar', methods=['GET', 'POST'])
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
            flash("Registro excluído.", "success")
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
