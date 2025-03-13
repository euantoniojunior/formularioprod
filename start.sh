#!/bin/sh

# Aplica as migrações do banco de dados (importante para criar as tabelas)
flask db upgrade

# Inicia o servidor Flask
gunicorn -w 4 -b 0.0.0.0:5000 app:app
