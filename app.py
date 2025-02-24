from flask import Flask, render_template, request, jsonify
import psycopg2
from dotenv import load_dotenv
import os

app = Flask(__name__)

load_dotenv()  # Cargar variables de entorno desde .env

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/catalogo')
def catalogo():
    productos = [
        {"nombre": "Producto 1", "precio": 10.00},
        {"nombre": "Producto 2", "precio": 15.00},
    ]
    return render_template('catalogo.html', productos=productos)

@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['name']
        telefono = request.form['phone']
        cedula = request.form['cedula']
        productos = request.form['productName'].split(',')
        precios = list(map(float, request.form['productPrice'].split(',')))
        cantidades = list(map(int, request.form['cantidad'].split(',')))

        # Imprimir los datos para verificar que se recibieron correctamente
        print(f"Nombre: {nombre}, Teléfono: {telefono}, Cédula: {cedula}")
        print(f"Productos: {productos}, Precios: {precios}, Cantidades: {cantidades}")

        # Conectar a la base de datos
        try:
            connection = psycopg2.connect(
                user=USER,
                password=PASSWORD,
                host=HOST,
                port=PORT,
                dbname=DBNAME
            )
            cursor = connection.cursor()

            # Verificar si el cliente ya existe
            cursor.execute("SELECT id FROM clientes WHERE cedula = %s", (cedula,))
            cliente = cursor.fetchone()

            # Si el cliente no existe, crearlo
            if not cliente:
                cursor.execute(
                    "INSERT INTO clientes (nombre, telefono, cedula) VALUES (%s, %s, %s) RETURNING id", 
                    (nombre, telefono, cedula)
                )
                cliente_id = cursor.fetchone()[0]
            else:
                cliente_id = cliente[0]

            # Calcular el precio total del pedido
            total_price = sum([precio * cantidad for precio, cantidad in zip(precios, cantidades)])

            # Insertar un solo pedido con el total calculado
            cursor.execute(
                "INSERT INTO pedidos (cliente_id, total_price) VALUES (%s, %s) RETURNING id",
                (cliente_id, total_price)
            )
            pedido_id = cursor.fetchone()[0]

            # Insertar los detalles del pedido (productos)
            for producto, precio, cantidad in zip(productos, precios, cantidades):
                cursor.execute(
                    "INSERT INTO detalle_pedidos (pedido_id, producto, precio, cantidad) VALUES (%s, %s, %s, %s)",
                    (pedido_id, producto, precio, cantidad)
                )

            connection.commit()  # Confirmar la transacción

            cursor.close()
            connection.close()

            # Confirmación al usuario
            return render_template(
                'confirmacion.html',
                nombre=nombre,
                telefono=telefono,
                cedula=cedula,
                pedido_id=pedido_id,
                total_price=total_price,
                productos=productos,
                precios=precios,
                cantidades=cantidades
            )

        except Exception as e:
            print(f"Error al conectar con la base de datos: {e}")
            return jsonify({"error": "No se pudo procesar el pedido, intente nuevamente."})

    return render_template('pedido.html')

@app.route('/gestionpedidos')
def gestion_pedidos():
    try:
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        cursor = connection.cursor()

        cursor.execute("""
            SELECT pedidos.id, clientes.nombre, clientes.telefono, clientes.cedula, pedidos.total_price, pedidos.fecha, 
                   detalle_pedidos.producto, detalle_pedidos.precio
            FROM pedidos
            JOIN clientes ON pedidos.cliente_id = clientes.id
            LEFT JOIN detalle_pedidos ON pedidos.id = detalle_pedidos.pedido_id
        """)

        pedidos_raw = cursor.fetchall()

        # Organizar los pedidos en un diccionario con listas de productos
        pedidos = {}
        for row in pedidos_raw:
            pedido_id = row[0]
            if pedido_id not in pedidos:
                pedidos[pedido_id] = {
                    "id": pedido_id,
                    "nombre": row[1],
                    "telefono": row[2],
                    "cedula": row[3],
                    "total_price": row[4],
                    "fecha": row[5],
                    "productos_precios": []  # Aquí guardamos los productos
                }
            
            # Agregar el producto y su precio si existen
            if row[6]:  # row[6] = producto, row[7] = precio
                pedidos[pedido_id]["productos_precios"].append((row[6], row[7]))

        cursor.close()
        connection.close()

        return render_template("gestionpedidos.html", pedidos=list(pedidos.values()))

    except Exception as e:
        print(f"Error al obtener los pedidos: {e}")
        return "Error al cargar los pedidos", 500

if __name__ == '__main__':
    app.run(debug=True)
