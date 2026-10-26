# Cliente Modbus TCP escrito a mano

## Qué hace

Es un cliente Modbus TCP en Python que solo usa la biblioteca estándar. Construye cada trama byte a byte y la envía al servidor (el simulador del laboratorio, en `127.0.0.1:5020`). Después recibe la respuesta, comprueba que es correcta y devuelve los datos ya decodificados.

Son dos ficheros:

- **`modbus_tcp.py`**, la biblioteca: la cabecera MBAP, una clase por cada función Modbus, el cliente y los errores. Funciona por sí sola desde la consola de Python.
- **`modbus_cli.py`**, el programa de línea de órdenes: ejecuta una sola petición con la biblioteca y escribe el resultado en el formato exacto que pide el guion.

```
practica1/            la entrega que pide el guion
  modbus_tcp.py
  modbus_cli.py
modbus_web.py         interfaz gráfica en el navegador (opcional, ver "Interfaz gráfica")
simulador_modbus      el simulador del laboratorio
```

Los ejemplos de consola se ejecutan desde la carpeta `practica1`.

```python
>>> import modbus_tcp as mb
>>> with mb.ClienteModbusTCP(traza=True) as c:
...     c.leer_holding_registers(107, 3)
TX: 00 01 00 00 00 06 01 03 00 6B 00 03
RX: 00 01 00 00 00 09 01 03 06 02 2B 00 00 00 64
[555, 0, 100]
```

```
$ python3 modbus_cli.py leer-holding 107 3
107 555 555 0x022B
108 0 0 0x0000
109 100 100 0x0064
```

## Qué hace, paso a paso

Una trama Modbus TCP se compone de una **cabecera MBAP** de 7 bytes y una **PDU** (código de función + datos). Cada petición sigue estos pasos:

1. Se crea un objeto de la función, por ejemplo `LeerHoldingRegisters(107, 3)`. Su constructor comprueba que los argumentos están en rango.
2. `ClienteModbusTCP.ejecutar()` pide a la función su PDU con `pdu()`. Delante le pone la cabecera: un transaction ID nuevo, protocol ID 0, Length = 1 + tamaño de la PDU y el Unit ID.
3. Envía la trama con `sendall()`.
4. Lee exactamente 7 bytes, que son la cabecera de la respuesta, y comprueba transaction ID, protocol ID y Length.
5. Lee exactamente Length − 1 bytes más, que son la PDU de la respuesta.
6. Si el código de función vuelve con 0x80 sumado, es una excepción Modbus. Si es un código distinto del pedido, es un error de protocolo.
7. La función comprueba y decodifica su respuesta con `unpack_respuesta()`.

## Funciones implementadas

| Código | Clase | Atajo del cliente | Orden del CLI | Devuelve |
|---|---|---|---|---|
| 0x01 | `LeerCoils` | `leer_coils` | `leer-coils DIR CANT` | lista de bits |
| 0x02 | `LeerEntradasDiscretas` | `leer_entradas_discretas` | `leer-entradas DIR CANT` | lista de bits |
| 0x03 | `LeerHoldingRegisters` | `leer_holding_registers` | `leer-holding DIR CANT` | lista de registros |
| 0x04 | `LeerInputRegisters` | `leer_input_registers` | `leer-input DIR CANT` | lista de registros |
| 0x05 | `EscribirCoil` | `escribir_coil` | `escribir-coil DIR 0\|1` | `(direccion, valor)` del eco |
| 0x06 | `EscribirRegistro` | `escribir_registro` | `escribir-registro DIR VALOR` | `(direccion, valor)` del eco |
| 0x0F | `EscribirCoils` | `escribir_coils` | `escribir-coils DIR V1 V2 …` | `(direccion, cantidad)` |
| 0x10 | `EscribirRegistros` | `escribir_registros` | `escribir-registros DIR V1 V2 …` | `(direccion, cantidad)` |
| 0x17 | `LeerEscribirRegistros` | `leer_escribir_registros` | `leer-escribir DIR_L CANT DIR_E V1 V2 …` | registros leídos |

Todas las clases tienen la misma forma: el constructor guarda y valida los campos, `pdu()` construye la petición y `unpack_respuesta(pdu)` valida y decodifica la respuesta. Las herencias son:

```
LeerHoldingRegisters (0x03) ─┬─ LeerInputRegisters (0x04)
                             └─ LeerEscribirRegistros (0x17)
LeerCoils (0x01) ─────────── LeerEntradasDiscretas (0x02)
EscribirRegistro (0x06) ──── EscribirCoil (0x05)
EscribirRegistros (0x10)     EscribirCoils (0x0F)
```

## Errores

| Clase | Cuándo salta | Mensaje | Salida del CLI |
|---|---|---|---|
| `ArgumentoInvalido` | Un parámetro está fuera de rango, o un argumento del CLI está mal escrito | `ARGUMENTO INVALIDO: <motivo>` | 2 |
| `ExcepcionModbus` | El servidor responde con código + 0x80 | `EXCEPCION 0xCC NOMBRE` | 3 |
| `ErrorTimeout` | No llega respuesta dentro del `timeout` | `TIMEOUT` | 4 |
| `ErrorConexion` | No se puede conectar, o la conexión se cae al enviar o al recibir | `ERROR DE CONEXION: <motivo>` | 5 |
| `ErrorProtocolo` | La respuesta no es la de la petición enviada (ver abajo) | `ERROR DE PROTOCOLO: <motivo>` | 6 |

`ErrorProtocolo` salta en estos casos:

- el transaction ID no coincide;
- el protocol ID no es 0;
- el Length es imposible;
- el código de función es otro;
- el byte count es incorrecto;
- el eco o la confirmación de una escritura no coincide con lo pedido.

Cómo provocar los errores contra el simulador:

- **Excepción**: leer a partir de la dirección 9999, o deshabilitar una función en *Comportamiento*.
- **Timeout**: en *Comportamiento*, atender solo al Unit ID 1 con la política *Descartar*, y hacer la petición con `--unidad 2`.
- **Conexión**: usar un puerto en el que no escuche nadie, por ejemplo `--puerto 1`.

## El cliente y los argumentos

En la biblioteca, `ClienteModbusTCP(ip, puerto, unidad, timeout, traza)` se usa con `with`: conecta al entrar y cierra la conexión al salir, aunque salte un error. También se puede llamar a mano a `conectar()` y `cerrar()`.

```
python3 modbus_cli.py [--ip IP] [--puerto P] [--unidad U] [--timeout S] [--traza] ORDEN ARGUMENTOS
```

| Opción | Por defecto | Motivo |
|---|---|---|
| `--ip` | `127.0.0.1` | El simulador corre en el mismo PC |
| `--puerto` | `5020` | Sin ser administrador no se puede abrir el 502, así que el simulador usa el 5020 |
| `--unidad` | `1` | Es el Unit ID de los ejemplos del guion y el que atiende el simulador |
| `--timeout` | `5` | Segundos de espera para conectar y para cada `recv()` |
| `--traza` | desactivada | Muestra las tramas `TX:` y `RX:` como en el guion |

Si todo va bien, el CLI escribe:

- en una lectura de bits, una línea por bit: `direccion valor`;
- en una lectura de registros (0x03, 0x04 y 0x17), una línea por registro: `direccion sin_signo con_signo 0xHHHH`;
- en una escritura, `OK`.

Si falla, escribe el mensaje del error y sale con su código.

## Interfaz gráfica

Para usar el cliente sin escribir órdenes:

1. Arranca el simulador (`./simulador_modbus`).
2. Descarga `cliente_modbus` de la página de [Releases](../../releases/latest) y ábrelo con doble clic (o con `chmod +x cliente_modbus && ./cliente_modbus` desde la terminal).
3. Se abre el navegador con un formulario. Elige la función, rellena los campos y pulsa **Enviar**.
4. Al terminar, pulsa **Salir**.

`cliente_modbus` es un único ejecutable para Linux x86-64 que lleva Python dentro, igual que el simulador, así que no hay que instalar nada. Se compiló sobre Debian 11 (glibc 2.31) y funciona en Ubuntu 20.04 o posterior. Si hay Python, también se puede abrir con `python3 modbus_web.py`.

`modbus_web.py` no repite lógica. Convierte el formulario en los argumentos de `modbus_cli.py`, lo ejecuta y enseña lo que escribiría en la consola, así que la salida y los errores son los mismos que en el CLI. El servidor solo escucha en `127.0.0.1`, en un puerto libre que elige el sistema.

Para volver a compilar el ejecutable (hace falta podman o docker):

```
podman run --rm -v "$PWD":/src:Z -w /tmp docker.io/library/python:3.10-slim-bullseye sh -c \
  "apt-get -qq update && apt-get -qq install -y binutils && pip install pyinstaller && cp /src/modbus_web.py /src/practica1/*.py . \
   && pyinstaller --onefile --name cliente_modbus modbus_web.py && cp dist/cliente_modbus /src/"
```

## Decisiones y por qué

### Organización

- **Dos ficheros, con el cliente dentro de la biblioteca.** El guion pide entregar `modbus_tcp.py` y `modbus_cli.py`, y la demo se hace desde la consola de Python solo con la biblioteca. Por eso todo lo que habla Modbus está en `modbus_tcp.py`. El CLI se limita a traducir argumentos y a dar formato a la salida.
- **Solo la biblioteca estándar** (`socket`, `struct`, `argparse`, `sys`). Lo exige el guion, que no permite bibliotecas Modbus. Además, no hay nada que instalar.
- **Nombres exactos del guion** (`CabeceraMBAP`, `LeerEntradasDiscretas`, `pdu()`, `escribir_registro`…). El corrector automático importa las clases y llama a los métodos por su nombre. Un nombre distinto significa una prueba fallida.
- **Una clase por función.** Cada función sabe construir su petición y leer su respuesta, y `ejecutar()` no conoce ninguna función concreta. Para añadir una función nueva basta con añadir una clase.
- **Atajos en el cliente** (`leer_coils`, `escribir_registro`…). En la consola es más cómodo escribir `c.leer_coils(0, 8)` que `c.ejecutar(mb.LeerCoils(0, 8))`. Cada atajo es una línea, sin lógica propia.
- **Comentarios en cada clase sobre su tabla de datos** (lectura o escritura, bits o registros). Así se entiende qué función usar sin abrir el guion.

### Herencia

- **0x04 hereda de 0x03 y 0x02 hereda de 0x01.** La trama es idéntica y solo cambia la tabla, que la decide el código de función. Por eso la clase hija solo redefine `CODIGO`, y el código de empaquetar y comprobar está escrito una sola vez.
- **0x05 hereda de 0x06.** Las dos son código + dirección + 2 bytes de valor, y la respuesta es un eco. La 0x05 solo redefine el constructor, porque un coil a ON no viaja como 1 sino como `0xFF00`.
- **0x17 hereda de 0x03.** Su respuesta es exactamente la de la 0x03, así que reutiliza `unpack_respuesta` y el límite de 125 registros. Para eso, la dirección y la cantidad de lectura se guardan con `super()` en `self.direccion` y `self.cantidad`, los nombres que usa la clase padre.
- **0x0F y 0x10 no comparten clase.** Su respuesta es igual, pero la petición se codifica de forma muy distinta (bits empaquetados frente a registros). Juntarlas restaba legibilidad a cambio de pocas líneas.

### Tramas

- **`struct` con `>` (big-endian).** Modbus envía primero el byte más significativo. `struct` lo hace en una línea, y el formato documenta la trama: `>BHH` son 1 + 2 + 2 bytes.
- **Códigos de función en hexadecimal** (`0x0F`, `0x10`, `0x17`), en el código, en los comentarios y en la ayuda del CLI. Así aparecen en las tramas y en el guion, y se evita confundir "10" con diez.
- **`TAM = struct.calcsize(FORMATO)`** en lugar de un 7 escrito a mano. El tamaño sale del formato, así que no pueden contradecirse.
- **El transaction ID aumenta con cada petición y se aplica `& 0xFFFF`.** Así cada respuesta se empareja con su petición, y el número vuelve a 0 después de 65535, que es lo máximo que cabe en 2 bytes.
- **Primero 7 bytes, luego Length − 1.** TCP entrega un flujo de bytes, no mensajes: una respuesta puede llegar partida o pegada a otra. El campo Length es lo único que dice dónde acaba.
- **`_recibir(n)` repite `recv()` hasta reunir n bytes.** `recv()` puede devolver menos de lo pedido. Si devuelve `b''`, el servidor ha cerrado la conexión.
- **Bits: el primero va en el bit 0 del primer byte.** Lo fija la norma. Al leer, se corta en `cantidad` porque el último byte trae relleno a 0. `(cantidad + 7) // 8` es la división redondeando hacia arriba, sin importar `math`.
- **Los negativos se envían en complemento a 2 con `valor & 0xFFFF`.** Un registro son 16 bits sin tipo, y el guion pide aceptar valores de −32768 a 65535. La máscara convierte −5 en `0xFFFB` sin casos especiales. Sin ella, `struct.pack('>H', -5)` falla.
- **Las lecturas devuelven los registros sin signo**, que es lo que viaja por la red. El CLI calcula también el valor con signo (`valor - 0x10000` si el bit `0x8000` está a 1), porque el formato de salida pide los dos.

### Validación

- **Los rangos se comprueban en el constructor con `_comprobar()`.** Si no, `struct` fallaría con un `struct.error` poco claro, o se enviaría una petición que el servidor rechazaría. Los límites (125 y 2000 al leer, 123 y 1968 al escribir, 121 en la 0x17) salen de que la PDU no puede pasar de 253 bytes. Cada uno lleva la cuenta en un comentario.
- **El cliente valida `puerto` y `unidad`.** Un puerto mayor que 65535 da `OverflowError` al conectar. Una unidad mayor que 255 da `struct.error`, porque el Unit ID ocupa 1 byte.
- **Toda respuesta se comprueba antes de usarla.** Una respuesta incorrecta no debe convertirse en datos basura ni en un `IndexError` difícil de entender. Mejor un `ErrorProtocolo` que dice qué campo falla.
- **En las escrituras se comparan bytes.** En 0x05 y 0x06 la respuesta debe ser igual a la petición. En 0x0F y 0x10 debe ser código + dirección + cantidad. Una sola comparación cubre todos los campos y la longitud.
- **La excepción se detecta con `pdu[0] == funcion.CODIGO | 0x80`**, no solo mirando el bit 0x80. Un 0x83 en respuesta a una 0x01 no es una excepción de nuestra petición, sino un error de protocolo.

### Errores

- **Una clase por error, cada una con su `CODIGO_SALIDA` y su mensaje exacto.** El CLI captura las cinco en un solo `except`, escribe `print(e)` y sale con `sys.exit(e.CODIGO_SALIDA)`. No necesita una cadena de `if`.
- **Los errores de `socket` se traducen a errores propios.** `socket.timeout` pasa a ser `ErrorTimeout`, y cualquier otro `OSError` (rechazo, reinicio, tubería rota) pasa a ser `ErrorConexion`. Quien use la biblioteca no necesita conocer `socket`. `socket.timeout` se captura primero porque también es un `OSError`.
- **`e.strerror or e`.** `strerror` da un texto limpio, como "Connection refused". Algunos errores no lo tienen, y entonces se usa la excepción entera.
- **Tabla `NOMBRES` con `.get(codigo, "DESCONOCIDA")`.** Si un servidor devuelve un código de excepción no estándar, el programa no se rompe.
- **Después de una `ExcepcionModbus`, la conexión sigue sirviendo.** La respuesta de excepción se lee entera, así que el flujo queda alineado y la siguiente petición funciona, como pide el guion.

### CLI

- **`argparse` con un subcomando por orden.** Cada orden tiene sus propios argumentos, y `-h` da la ayuda sin escribir nada más.
- **`nargs='+'` en `valores`.** Las escrituras múltiples y la 0x17 aceptan uno o más valores. Los negativos (`-5`) funcionan porque `argparse` no tiene opciones que parezcan números.
- **Subclase `Parser` que redefine `error()`.** `argparse` ya sale con código 2 si un argumento está mal escrito, pero con su propio mensaje. Aquí solo se cambia el mensaje al formato `ARGUMENTO INVALIDO: …`. Los subcomandos heredan la clase sin hacer nada más.
- **Las escrituras escriben `OK` sin mirar lo que devuelven.** Si no ha saltado ningún error, el servidor ya ha confirmado la escritura y el eco se ha comprobado.
- **Mensajes de error por la salida estándar.** El guion los pide como "salida" del programa.
- **La traza va en mayúsculas y con espacios (`hex(" ").upper()`).** Es el formato del guion, así se comparan las tramas a simple vista.

## Límites conocidos

- **En el CLI, los argumentos de la función se validan después de conectar.** Sin servidor, `leer-holding 0 200` da `ERROR DE CONEXION` en vez de `ARGUMENTO INVALIDO`. Con el simulador arrancado, el resultado es el correcto.
- **Con `--traza`, las líneas `TX:` y `RX:` salen por la salida estándar, mezcladas con el resultado.**
- **Tras un timeout no se cierra la conexión.** Si la respuesta llega tarde, la siguiente petición la leerá y dará `ErrorProtocolo` por transaction ID. En el CLI no afecta, porque hace una sola petición.
