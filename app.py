from flask import Flask, request, render_template, send_file, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)

# Configuração do Banco de Dados (Render define DATABASE_URL como variável de ambiente)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "postgresql://antoniojunior:DbEBtCnwzPOgh8yAjVa8CIvSif2EnPUH@dpg-cv4vpslumphs73frdobg-a/formulario_1?sslmode=disable") 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SECRET_KEY'] = 'DbEBtCnwzPOgh8yAjVa8CIvSif2EnPUH'  # Necessário para usar o flash messages

db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Adiciona suporte a migrações

# Modelo da Tabela Inscrições
class Inscricao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), nullable=False, unique=True)
    fone = db.Column(db.String(20), nullable=False)
    ip = db.Column(db.String(50), nullable=False)
    data_hora = db.Column(db.String(50), nullable=False, default=lambda: datetime.now(pytz.timezone("America/Rio_Branco")).strftime("%Y-%m-%d %H:%M:%S"))

# Criação do banco de dados
with app.app_context():
    db.create_all()

# Validação de CPF (11 dígitos numéricos e um básico de validade)
def validar_cpf(cpf):
    # Remove tudo o que não for número
    cpf = "".join(filter(str.isdigit, cpf))
    
    if len(cpf) != 11:
        return False

    # Lógica básica de CPF (aqui pode ser inserida uma validação mais avançada)
    if cpf == cpf[0] * 11:  # Não permite CPFs como 111.111.111-11
        return False
    
    return True

# Exportar os dados para um arquivo Excel
@app.route('/baixar_excel')
def baixar_excel():
    registros = Inscricao.query.all()

    if registros:
        data = [{"ID": r.id, "Nome": r.nome, "Email": r.email, "CPF": r.cpf, "Fone": r.fone, "IP": r.ip, "Data/Hora": r.data_hora} for r in registros]
        df = pd.DataFrame(data)
        excel_file = "inscricoes.xlsx"
        df.to_excel(excel_file, index=False, engine="openpyxl")
        return send_file(excel_file, as_attachment=True)

    flash("Nenhum dado para exportar.", "warning")
    return redirect(url_for('index'))

# Página inicial
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        cpf = request.form.get('cpf')
        fone = request.form.get('fone')

        if not validar_cpf(cpf):
            erro_cpf = "CPF deve ter 11 caracteres numéricos e ser válido."
            return render_template('form.html', erro_cpf=erro_cpf, nome=nome, email=email, cpf=cpf, fone=fone)

        ip_usuario = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        data_hora = datetime.now(pytz.timezone("America/Rio_Branco")).strftime("%Y-%m-%d %H:%M:%S")

        nova_inscricao = Inscricao(nome=nome, email=email, cpf=cpf, fone=fone, ip=ip_usuario, data_hora=data_hora)

        try:
            db.session.add(nova_inscricao)
            db.session.commit()
            flash("Inscrição realizada com sucesso!", "success")
            return render_template('success.html')
        except IntegrityError:
            db.session.rollback()
            flash("Erro: CPF já cadastrado.", "danger")
            return render_template('form.html', nome=nome, email=email, cpf=cpf, fone=fone)

    return render_template('form.html')

# Visualização e exclusão de registros
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
            flash("Registro excluído com sucesso.", "success")

    registros = Inscricao.query.all()
    return render_template('visualizar.html', registros=registros)

# Rota para baixar os dados em CSV
@app.route('/download')
def download_file():
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
