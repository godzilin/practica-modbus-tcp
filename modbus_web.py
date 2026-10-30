#La interfaz gráfica (en el navegador)
#Arranca un servidor web local y abre el navegador con un formulario HTML sencillo, sin JavaScript.
#Al pulsar Enviar, el formulario se convierte en los argumentos de modbus_cli.py, se ejecuta y se
#muestra debajo lo mismo que escribiría en la consola. Solo usa la biblioteca estándar.

import contextlib
import html
import io
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

# La entrega (modbus_cli.py y modbus_tcp.py) está en la carpeta practica1, junto a este fichero
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'practica1'))
import modbus_cli

# Cada orden del CLI y qué números hay que escribir en "Datos", en el orden de sus argumentos
FUNCIONES = [
    ('leer-holding',       '0x03 Leer holding registers (dirección cantidad)'),
    ('leer-input',         '0x04 Leer input registers (dirección cantidad)'),
    ('leer-coils',         '0x01 Leer coils (dirección cantidad)'),
    ('leer-entradas',      '0x02 Leer entradas discretas (dirección cantidad)'),
    ('escribir-coil',      '0x05 Escribir un coil (dirección valor)'),
    ('escribir-registro',  '0x06 Escribir un registro (dirección valor)'),
    ('escribir-coils',     '0x0F Escribir varios coils (dirección valor valor ...)'),
    ('escribir-registros', '0x10 Escribir varios registros (dirección valor valor ...)'),
    ('leer-escribir',      '0x17 Leer y escribir registros (dir_lectura cantidad dir_escritura valor ...)'),
]

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Cliente Modbus TCP</title></head><body>
<h1>Cliente Modbus TCP</h1>
<form method="post" action="/enviar">
  <p>IP: <input name="ip" value="{ip}"></p>
  <p>Puerto: <input name="puerto" value="{puerto}"></p>
  <p>Unidad: <input name="unidad" value="{unidad}"></p>
  <p>Función: <select name="funcion">{opciones}</select></p>
  <p>Datos (números separados por espacios): <input name="datos" value="{datos}"></p>
  <p><label><input type="checkbox" name="traza" {traza}> Ver tramas enviadas y recibidas</label></p>
  <p><button>Enviar</button></p>
</form>
<form method="post" action="/salir"><button>Salir</button></form>
<h2>Resultado</h2>
<pre>{resultado}</pre>
</body></html>"""


def pagina(campos, resultado=''):
    """ Devuelve el HTML del formulario, rellenado con los valores que se enviaron la última vez. """
    elegida = campos.get('funcion', '')
    opciones = ''.join(f'<option value="{nombre}"{" selected" if nombre == elegida else ""}>{texto}</option>'
                       for nombre, texto in FUNCIONES)
    return PAGINA.format(ip=html.escape(campos.get('ip', '127.0.0.1')),
                         puerto=html.escape(campos.get('puerto', '5020')),
                         unidad=html.escape(campos.get('unidad', '1')),
                         datos=html.escape(campos.get('datos', '')),
                         traza='checked' if 'traza' in campos else '',
                         opciones=opciones,
                         resultado=html.escape(resultado))


def ejecutar_cli(argv):
    """ Ejecuta modbus_cli.main() con esos argumentos y devuelve lo que escribe en la consola.

    El CLI termina con sys.exit() cuando hay un error; aquí se captura para que el
    servidor siga funcionando, y el mensaje del error ya está en la salida.
    """
    salida = io.StringIO()
    sys.argv = ['modbus_cli.py'] + argv
    with contextlib.redirect_stdout(salida):
        try:
            modbus_cli.main()
        except SystemExit:
            pass
    return salida.getvalue()


class Manejador(BaseHTTPRequestHandler):

    def do_GET(self):
        self.responder(pagina({}))

    def do_POST(self):
        if self.path == '/salir':
            self.responder('<h1>Cerrado. Ya puedes cerrar esta pestaña.</h1>')
            # shutdown() espera a que acabe serve_forever(), así que se llama desde otro hilo
            threading.Thread(target=self.server.shutdown).start()
            return
        cuerpo = self.rfile.read(int(self.headers['Content-Length'])).decode()
        campos = {nombre: valores[0] for nombre, valores in parse_qs(cuerpo).items()}
        argv = ['--ip', campos.get('ip', ''), '--puerto', campos.get('puerto', ''),
                '--unidad', campos.get('unidad', '')]
        if 'traza' in campos:
            argv.append('--traza')
        argv += [campos.get('funcion', '')] + campos.get('datos', '').split()
        self.responder(pagina(campos, ejecutar_cli(argv)))

    def responder(self, texto):
        datos = texto.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(datos))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass  # sin una línea en la consola por cada petición


def main():
    # Solo escucha en 127.0.0.1 (no se puede usar desde otro PC) y en un puerto libre
    # que elige el sistema (0), para no chocar con nada que ya esté abierto
    servidor = HTTPServer(('127.0.0.1', 0), Manejador)
    url = f'http://127.0.0.1:{servidor.server_port}'
    print(f'Interfaz abierta en {url} (pulsa Salir en la página para cerrarla)', flush=True)
    webbrowser.open(url)
    servidor.serve_forever()


if __name__ == '__main__':
    main()
