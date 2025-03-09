from flask import Flask, render_template, request, jsonify
import psycopg2
from dotenv import load_dotenv
import os

app = Flask(__name__, static_folder='static')

@app.template_filter('format_price')
def format_price_filter(value):
    return f"{value:,}".replace(",", ".")

load_dotenv()  # Cargar variables de entorno desde .env

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

@app.route('/')
def home():
    try:
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        cursor = connection.cursor()

        # Obtener productos para cada categoría
        categorias = {
            "accesorios_tenis": [1, 16],  # IDs de ejemplo
            "accesorios_moto": [2, 3, 4],
            "decoracion_hogar": [17, 6],
            "cuidado_personal": [18, 19]
        }

        productos_por_categoria = {}
        for categoria, ids in categorias.items():
            cursor.execute("""
                SELECT p.id, p.name, p.price, pi.image_url 
                FROM products p
                LEFT JOIN product_images pi ON p.id = pi.product_id
                WHERE p.id IN %s
                GROUP BY p.id, pi.image_url
            """, (tuple(ids),))
            productos = []
            for row in cursor.fetchall():
                precio = int(row[2])
                productos.append({"id": row[0], "nombre": row[1], "precio": precio, "imagen": row[3]})
            productos_por_categoria[categoria] = productos

        # Obtener productos más vendidos
        productos_ids = [1, 7, 3, 4]  # Aquí puedes poner los IDs de los productos más vendidos
        cursor.execute("""
            SELECT p.id, p.name, p.price, pi.image_url 
            FROM products p
            LEFT JOIN product_images pi ON p.id = pi.product_id
            WHERE p.id IN %s
            GROUP BY p.id, pi.image_url
        """, (tuple(productos_ids),))  # Convertimos la lista en una tupla para la consulta

        productos_mas_vendidos = []
        for row in cursor.fetchall():
            precio = int(row[2])
            productos_mas_vendidos.append({"id": row[0], "nombre": row[1], "precio": precio, "imagen": row[3]})

        cursor.close()
        connection.close()

        return render_template('home.html', productos_mas_vendidos=productos_mas_vendidos, **productos_por_categoria)

    except Exception as e:
        print(f"Error al obtener productos: {e}")
        return "Error al cargar productos", 500

@app.route('/catalogo')
def catalogo():
    return render_template('catalogo.html')

@app.route('/api/productos')
def api_productos():
    try:
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        cursor = connection.cursor()

        # Obtener todos los productos desde la base de datos
        cursor.execute("""
            SELECT p.id, p.name, p.price, pi.image_url 
            FROM products p
            LEFT JOIN product_images pi ON p.id = pi.product_id
            GROUP BY p.id, pi.image_url
        """)
        productos = []
        for row in cursor.fetchall():
            precio = int(row[2])
            productos.append({"id": row[0], "nombre": row[1], "precio": precio, "imagen": row[3]})

        cursor.close()
        connection.close()

        return jsonify(productos)

    except Exception as e:
        print(f"Error al obtener productos: {e}")
        return jsonify({"error": "Error al cargar productos"}), 500

@app.route('/detalleproducto/<int:producto_id>')
def detalle_producto(producto_id):
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
            SELECT p.name, p.price, p.description, pi.image_url 
            FROM products p
            LEFT JOIN product_images pi ON p.id = pi.product_id
            WHERE p.id = %s
        """, (producto_id,))
        producto = cursor.fetchone()

        cursor.close()
        connection.close()

        if producto:
            producto_dict = {"nombre": producto[0], "precio": int(producto[1]), "descripcion": producto[2], "imagen": producto[3]}
            return render_template('detalleproducto.html', producto=producto_dict)
        else:
            return "Producto no encontrado", 404

    except Exception as e:
        print(f"Error al obtener producto: {e}")
        return "Error al cargar producto", 500

@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['name']
        telefono = request.form['phone']
        cedula = request.form['cedula']
        productos = request.form['productName'].split('|')
        precios = list(map(float, request.form['productPrice'].split(',')))
        cantidades = list(map(int, request.form['cantidad'].split(',')))
        imagenes = request.form['productImage'].split(',')

        # Imprimir los datos para verificar que se recibieron correctamente
        print(f"Nombre: {nombre}, Teléfono: {telefono}, Cédula: {cedula}")
        print(f"Productos: {productos}, Precios: {precios}, Cantidades: {cantidades}, Imágenes: {imagenes}")

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

            # Insertar un solo pedido con el total calculado y estado inicial 'esperando'
            cursor.execute(
                "INSERT INTO pedidos (cliente_id, total_price, estado) VALUES (%s, %s, %s) RETURNING id",
                (cliente_id, total_price, 'esperando')
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
            productos_precios = [(productos[i], precios[i], cantidades[i], imagenes[i]) for i in range(len(productos))]
            return render_template(
                'confirmacion.html',
                nombre=nombre,
                telefono=telefono,
                cedula=cedula,
                pedido_id=pedido_id,
                total_price=int(total_price),  # Convertir el precio total a entero
                productos_precios=productos_precios
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
                   pedidos.estado, detalle_pedidos.producto, detalle_pedidos.precio, detalle_pedidos.cantidad
            FROM pedidos
            JOIN clientes ON pedidos.cliente_id = clientes.id
            LEFT JOIN detalle_pedidos ON pedidos.id = detalle_pedidos.pedido_id
        """)

        pedidos_raw = cursor.fetchall()

        # Organizar los pedidos en un diccionario con listas de productos
        pedidos = {}
        for row in pedidos_raw:
            pedido_id = row[0]
            if (pedido_id not in pedidos):
                pedidos[pedido_id] = {
                    "id": pedido_id,
                    "nombre": row[1],
                    "telefono": row[2],
                    "cedula": row[3],
                    "total_price": int(row[4]),  # Limpiar ceros decimales
                    "fecha": row[5],
                    "estado": row[6],  # Asegúrate de incluir el estado aquí
                    "productos_precios": []  # Aquí guardamos los productos
                }
            
            # Agregar el producto, su precio y cantidad si existen
            if row[7]:  # row[7] = producto, row[8] = precio, row[9] = cantidad
                pedidos[pedido_id]["productos_precios"].append((row[7], int(row[8]), int(row[9])))  # Limpiar ceros decimales

        cursor.close()
        connection.close()

        return render_template("gestionpedidos.html", pedidos=list(pedidos.values()))

    except Exception as e:
        print(f"Error al obtener los pedidos: {e}")
        return "Error al cargar los pedidos", 500

@app.route('/actualizar_estado_pedido/<int:pedido_id>', methods=['POST'])
def actualizar_estado_pedido(pedido_id):
    nuevo_estado = request.json.get('estado')
    try:
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE pedidos SET estado = %s WHERE id = %s",
            (nuevo_estado, pedido_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error al actualizar el estado del pedido: {e}")
        return jsonify({"error": "No se pudo actualizar el estado del pedido"}), 500

@app.route('/consulta_pedido', methods=['GET'])
def consulta_pedido():
    if not request.args:
        return render_template('consulta_pedido.html')

    nombre = request.args.get('nombre')
    telefono = request.args.get('telefono')
    cedula = request.args.get('cedula')

    print(f"Datos recibidos - Nombre: {nombre}, Teléfono: {telefono}, Cédula: {cedula}")

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
            SELECT pedidos.id, pedidos.fecha, pedidos.estado
            FROM pedidos
            JOIN clientes ON pedidos.cliente_id = clientes.id
            WHERE clientes.nombre = %s AND clientes.telefono = %s AND clientes.cedula = %s
        """, (nombre, telefono, cedula))

        pedidos = cursor.fetchall()

        print(f"Resultado de la consulta: {pedidos}")

        cursor.close()
        connection.close()

        if pedidos:
            pedidos_list = [{"id": pedido[0], "fecha": pedido[1], "estado": pedido[2]} for pedido in pedidos]
            return jsonify(pedidos_list)
        else:
            return jsonify({"error": "No se encontró ningún pedido con los datos proporcionados."})

    except Exception as e:
        print(f"Error al consultar el pedido: {e}")
        return jsonify({"error": "Error al consultar el pedido"}), 500


@app.route('/consulta_pedido/form')
def consulta_pedido_form():
    return render_template('consulta_pedido.html')

@app.route('/calculadora')
def calculadora():
    return render_template('calculadora.html')

if __name__ == '__main__':
    app.run(debug=True)
