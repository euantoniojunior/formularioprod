# Base image com Python 3.11
FROM python:3.11-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copia os arquivos para o container
COPY . /app

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Porta que o app vai rodar
EXPOSE 5000

# Comando para iniciar a aplicação
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
