from flask import Flask, request, render_template, send_file
import psycopg2
from psycopg2 import sql
from datetime import datetime
import pytz
import os

app = Flask(__name__)

# Configuração do banco de dados no Render
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'seu_banco'),
    'user': os.getenv('DB_USER', 'seu_usuario'),
    'password': os.getenv('DB_PASSWORD', 'sua_senha'),
    'host': os.getenv('DB_HOST', 'seu_host'),
    'port': os.getenv('DB_PORT', '5432')
}

# Função para conectar ao banco de dados
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Criar tabela caso não exista
def create_table():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS inscricoes (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    ip VARCHAR(50),
                    data_hora TIMESTAMP NOT NULL
                )
            ''')
            conn.commit()

# Salvar dados no PostgreSQL
def save_to_db(nome, email, ip_usuario):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO inscricoes (nome, email, ip, data_hora)
                VALUES (%s, %s, %s, %s)
            ''', (nome, email, ip_usuario, datetime.now(pytz.timezone('America/Rio_Branco'))))
            conn.commit()

# Rota principal para formulário
def index():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        ip_usuario = request.headers.get('X-Forwarded-For', request.remote_addr)
        try:
            save_to_db(nome, email, ip_usuario)
            return render_template('success.html')
        except psycopg2.IntegrityError:
            return render_template('form.html', erro="Email já cadastrado!"), 400
    return render_template('form.html')

# Rota para resetar o banco de dados (limpa a tabela)
@app.route('/reset_db', methods=['POST'])
def reset_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM inscricoes')
            conn.commit()
    return "Banco de dados resetado com sucesso!"

# Rota para baixar os registros como CSV
@app.route('/download')
def download_file():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM inscricoes')
            registros = cur.fetchall()
    
    # Criar arquivo temporário CSV
    csv_file = 'inscricoes.csv'
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        file.write('ID,Nome,Email,IP,Data/Hora\n')
        for row in registros:
            file.write(','.join(map(str, row)) + '\n')
    
    return send_file(csv_file, as_attachment=True)

if __name__ == '__main__':
    create_table()
    app.run(debug=True, host='0.0.0.0', port=5000)
