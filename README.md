1. crear el contenedor

sudo docker exec -it hexa-dwh-db psql -U hexa_admin -d hexa_dwh

2. Dentro del contenedor, ejecutar los comandos indicados en el archivos comandos.sql

3. cargar entorno de python:
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pandas sqlalchemy psycopg2-binary

4. Ejecutar etl.py para cargar datos en la base:
python3 etl.py

Listo! El contenedor por adentro ya tiene los datos extraidos en el modelo estrella
