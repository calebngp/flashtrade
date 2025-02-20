import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # Cargar las variables de entorno desde el archivo .env

try:
    connection = psycopg2.connect(
        user=os.getenv("user"),        # Debe ser en minúsculas
        password=os.getenv("password"),
        host=os.getenv("host"),
        port=os.getenv("port"),
        dbname=os.getenv("dbname")
    )
    print("Conexión exitosa a la base de datos")
    connection.close()
except Exception as e:
    print(f"Error en la conexión: {e}")
