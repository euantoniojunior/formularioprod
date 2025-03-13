from flask import Flask, request, render_template, send_file
import csv
import os
import re
import pandas as pd
from datetime import datetime
import pytz

app = Flask(__name__)
CSV_FILE = 'inscricoes.csv'
EXCEL_FILE = 'inscricoes.xlsx'
HEADERS = ["ID", "Nome", "Email", "CPF", "Fone", "IP", "Data/Hora"]

# Garante que o CSV existe e tem cabeçalho correto
def ensure_csv_exists():
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)

# Salva dados no CSV
def save_to_csv(data):
    ensure_csv_exists()
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(data)

# Gera ID único
def gerar_id_unico():
    ensure_csv_exists()
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            linhas = list(csv.reader(file))
            return int(linhas[-1][0]) + 1 if len(linhas) > 1 else 1
    except (ValueError, IndexError):
        return 1

# Validação de CPF (11 dígitos numéricos)
def validar_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)
    return len(cpf) == 11

# Lê registros do CSV
def ler_csv():
    ensure_csv_exists()
    with open(CSV_FILE, mode='r', encoding='utf-8') as file:
        return list(csv.reader(file))


# Exporta os dados para um arquivo Excel com o cabeçalho correto e disponibiliza para download
@app.route('/baixar_excel')
def baixar_excel():
    registros = ler_csv()
    
    if len(registros) > 1:  # Se houver registros além do cabeçalho
        df = pd.DataFrame(registros[1:], columns=HEADERS)  # Usa sempre os HEADERS corretos
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
        return send_file(EXCEL_FILE, as_attachment=True)
    
    return "Nenhum dado para exportar."
    
# Página inicial
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        cpf = request.form.get('cpf')
        fone = request.form.get('fone')

        if not validar_cpf(cpf):
            erro_cpf = "CPF deve ter 11 caracteres numéricos."
            return render_template('form.html', erro_cpf=erro_cpf, nome=nome, email=email, cpf=cpf, fone=fone)

        ip_usuario = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        data_hora = datetime.now(pytz.timezone('America/Rio_Branco')).strftime('%Y-%m-%d %H:%M:%S')
        save_to_csv([gerar_id_unico(), nome, email, cpf, fone, ip_usuario, data_hora])

        return render_template('success.html')
    return render_template('form.html')

# Visualização e exclusão de registros
@app.route('/visualizar', methods=['GET', 'POST'])
def visualizar_csv():
    if request.method == 'POST':
        if request.form.get('limpar_tudo'):
            ensure_csv_exists()
            with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(HEADERS)
        elif request.form.get('excluir'):
            linha_excluir = request.form.get('excluir')
            registros = ler_csv()
            with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(HEADERS)
                for linha in registros[1:]:
                    if linha[0] != linha_excluir:
                        writer.writerow(linha)
        return render_template('visualizar.html', registros=ler_csv())
    return render_template('visualizar.html', registros=ler_csv())

# Rota para baixar o arquivo CSV
@app.route('/download')
def download_file():
    return send_file(CSV_FILE, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
