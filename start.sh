#!/bin/sh

# Inicia o servidor Flask usando Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
