#La interfaz gráfica (en el navegador)
#Arranca un servidor web local y abre el navegador con un formulario: se elige la orden, se
#rellenan los campos y se pulsa Enviar. No hay que escribir nada en la terminal.
#
#Cada petición se ejecuta con el mismo programa modbus_cli.py: el formulario se traduce a sus
#argumentos y se muestra lo que escribiría en la consola. Así la salida es idéntica a la del CLI
#y no se repite ninguna lógica. Solo usa la biblioteca estándar: no hay que instalar nada.

import contextlib
import io
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# La entrega (modbus_cli.py y modbus_tcp.py) está en la carpeta practica1, junto a este fichero
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'practica1'))
import modbus_cli

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Cliente Modbus TCP</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
  body { max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
  fieldset { border: 1px solid #8888; border-radius: 8px; margin-bottom: 1rem; }
  label { display: inline-block; margin: .3rem .8rem .3rem 0; }
  input, select, button { font: inherit; padding: .3rem; }
  input { width: 9rem; }
  button { padding: .4rem 1.2rem; cursor: pointer; }
  pre { background: #8882; padding: 1rem; border-radius: 8px; min-height: 3rem; }
</style></head><body>
<h1>Cliente Modbus TCP</h1>
<fieldset><legend>Servidor</legend>
  <label>IP <input id="ip" value="127.0.0.1"></label>
  <label>Puerto <input id="puerto" value="5020"></label>
  <label>Unidad <input id="unidad" value="1"></label>
  <label>Timeout (s) <input id="timeout" value="5"></label>
  <label><input id="traza" type="checkbox" style="width:auto"> Ver tramas (TX/RX)</label>
</fieldset>
<fieldset><legend>Petición</legend>
  <select id="orden"></select>
  <div id="campos"></div>
</fieldset>
<button onclick="enviar()">Enviar</button> <button onclick="salir()">Salir</button>
<pre id="salida"></pre>
<script>
// Cada orden del CLI con los campos que pide, en el mismo orden que sus argumentos
const ORDENES = {
  'leer-holding':       ['0x03 Read Holding Registers', 'Dirección', 'Cantidad'],
  'leer-input':         ['0x04 Read Input Registers', 'Dirección', 'Cantidad'],
  'leer-coils':         ['0x01 Read Coils', 'Dirección', 'Cantidad'],
  'leer-entradas':      ['0x02 Read Discrete Inputs', 'Dirección', 'Cantidad'],
  'escribir-coil':      ['0x05 Write Single Coil', 'Dirección', 'Valor (0 o 1)'],
  'escribir-registro':  ['0x06 Write Single Register', 'Dirección', 'Valor'],
  'escribir-coils':     ['0x0F Write Multiple Coils', 'Dirección', 'Valores (separados por espacios)'],
  'escribir-registros': ['0x10 Write Multiple Registers', 'Dirección', 'Valores (separados por espacios)'],
  'leer-escribir':      ['0x17 Read/Write Multiple Registers', 'Dirección lectura', 'Cantidad', 'Dirección escritura', 'Valores (separados por espacios)'],
};
const orden = document.getElementById('orden');
for (const [nombre, [titulo]] of Object.entries(ORDENES)) orden.add(new Option(titulo, nombre));
orden.onchange = () => document.getElementById('campos').innerHTML = ORDENES[orden.value].slice(1)
  .map(campo => `<label>${campo} <input class="campo"></label>`).join('');
orden.onchange();

const valor = id => document.getElementById(id).value;
async function enviar() {
  const argv = ['--ip', valor('ip'), '--puerto', valor('puerto'), '--unidad', valor('unidad'), '--timeout', valor('timeout')];
  if (document.getElementById('traza').checked) argv.push('--traza');
  argv.push(orden.value);
  // Los campos de valores pueden traer varios números: cada uno es un argumento
  for (const campo of document.querySelectorAll('.campo')) argv.push(...campo.value.split(/\\s+/).filter(Boolean));
  const salida = document.getElementById('salida');
  salida.textContent = 'Enviando...';
  salida.textContent = await (await fetch('/enviar', {method: 'POST', body: JSON.stringify(argv)})).text();
}
async function salir() {
  await fetch('/salir', {method: 'POST'});
  document.body.innerHTML = '<h1>Cerrado. Ya puedes cerrar esta pestaña.</h1>';
}
</script></body></html>"""


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
        self.responder(PAGINA, 'text/html')

    def do_POST(self):
        if self.path == '/salir':
            self.responder('', 'text/plain')
            # shutdown() espera a que acabe serve_forever(), así que se llama desde otro hilo
            threading.Thread(target=self.server.shutdown).start()
        else: 
            argv = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.responder(ejecutar_cli(argv), 'text/plain')

    def responder(self, texto, tipo):
        datos = texto.encode()
        self.send_response(200)
        self.send_header('Content-Type', f'{tipo}; charset=utf-8')
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
