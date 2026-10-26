#La biblioteca
#0x03 Read Holding Registers
#   Clase y atajo: CabeceraMBAP ,
#                  ClienteModbusTCP ( conectar ,cerrar , ejecutar ),
#                  LeerHoldingRegisters ,
#                  leer_holding_registers ,
#0x04 Read Input Registers
#   Clase y atajo: LeerInputRegisters ,
#                  leer_input_registers ,
#0x01 Read Coils
#  Clase y atajo: LeerCoils ,
#                 leer_coils ,
#0x02 Read Discrete Inputs
#  Clase y atajo: LeerEntradasDiscretas ,
#                 leer_entradas_discretas ,
#0x06 Write Single Register
#  Clase y atajo: EscribirRegistro ,
#                 escribir_registro ,
#0x05 Write Single Coil
#  Clase y atajo: EscribirCoil ,
#                 escribir_coil ,
#Errores
#  Clases: ExcepcionModbus , ErrorTimeout , ErrorConexion , ArgumentoInvalido , ErrorProtocolo
#0x10 Write Multiple Registers
#  Clase y atajo: EscribirRegistros ,
#                 escribir_registros ,
#0x0F Write Multiple Coils
#  Clase y atajo: EscribirCoils ,
#                 escribir_coils ,
#0x17 Read/Write Multiple Registers
#  Clase y atajo: LeerEscribirRegistros ,
#                 leer_escribir_registros ,
#
#Los nombres de clases, atajos y del método pdu() son los que fija el guion: el corrector
#automático los importa y los llama por su nombre, así que no se pueden cambiar.
#
#Todas las clases de función siguen la misma forma:
#  - __init__ guarda los campos y comprueba que están en rango (si no, ArgumentoInvalido)
#  - pdu() devuelve los bytes de la PDU de la petición (código de función + datos)
#  - unpack_respuesta(pdu) comprueba la PDU de la respuesta y devuelve los datos decodificados
#El cliente no sabe nada de cada función concreta: solo llama a pdu() y a unpack_respuesta().

import socket
import struct


def _comprobar(nombre, valor, minimo, maximo):
    """ Lanza ArgumentoInvalido si valor no está entre minimo y maximo (ambos incluidos).

    Se comprueba antes de empaquetar porque struct, con un valor que no cabe,
    lanza un struct.error poco claro en vez de un error del protocolo.
    """
    if not minimo <= valor <= maximo:
        raise ArgumentoInvalido(f'{nombre} {valor} fuera de rango ({minimo} a {maximo})')


# Empaqueta y desempaqueta los 7 bytes de la cabecera MBAP
class CabeceraMBAP:
    """ Cabecera MBAP, esto es, la cabecera de la trama Modbus TCP. """
    # >HHHB: big-endian, tres enteros de 2 bytes (H) y uno de 1 byte (B)
    FORMATO = '>HHHB'
    TAM = struct.calcsize(FORMATO)  # 7 bytes

    def __init__(self, transaction_id=0, protocol_id=0, length=0, unit_id=0):
        self.transaction_id = transaction_id
        self.protocol_id = protocol_id
        self.length = length  # bytes que siguen: unit_id (1) + PDU
        self.unit_id = unit_id

    def pack(self):
        return struct.pack(self.FORMATO, self.transaction_id, self.protocol_id, self.length, self.unit_id)

    @classmethod # permite llamar a unpack sin crear un objeto CabeceraMBAP primero
    def unpack(cls, data):
        return cls(*struct.unpack(cls.FORMATO, data))


# Función 0x03: lee registros de 16 bits de lectura/escritura
class LeerHoldingRegisters:
    """ Función Modbus 0x03 Read Holding Registers.

    Los holding registers son palabras de 16 bits de LECTURA Y ESCRITURA: guardan
    datos que el cliente puede cambiar (consignas, parámetros, configuración).
    Por eso es la única tabla de registros que también tiene funciones de
    escritura (0x06, 0x10 y 0x17). Es la función más usada de Modbus y la base de las demás:
    la petición es código + dirección + cantidad y la respuesta trae los registros.
    """
    CODIGO = 0x03
    # La PDU de respuesta no puede pasar de 253 bytes: código (1) + byte count (1)
    # + 250 bytes de datos = 125 registros de 2 bytes
    MAX_CANTIDAD = 125

    def __init__(self, direccion, cantidad):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('cantidad', cantidad, 1, self.MAX_CANTIDAD)
        self.direccion = direccion
        self.cantidad = cantidad

    def pdu(self):
        # >BHH: código (1 byte), dirección (2 bytes), cantidad (2 bytes)
        return struct.pack('>BHH', self.CODIGO, self.direccion, self.cantidad)

    def unpack_respuesta(self, pdu):
        # PDU = código + byte count + registros de 2 bytes
        # Antes de leer los registros se comprueba que el servidor manda exactamente
        # los que se pidieron: byte count = 2 * cantidad y la PDU tiene ese tamaño.
        # Sin esto, una respuesta corta daría menos registros sin avisar o un IndexError.
        byte_count = 2 * self.cantidad
        if len(pdu) != 2 + byte_count or pdu[1] != byte_count:
            raise ErrorProtocolo(f'se esperaban {byte_count} bytes de registros')
        return list(struct.unpack(f'>{self.cantidad}H', pdu[2:]))


# Función 0x04: lee registros de 16 bits de solo lectura
class LeerInputRegisters(LeerHoldingRegisters):
    """ Función Modbus 0x04 Read Input Registers.

    Los input registers son palabras de 16 bits de SOLO LECTURA: los rellena el
    propio dispositivo con lo que mide (temperatura, presión, entradas analógicas)
    y el cliente no puede modificarlos. Están en una tabla aparte de los holding,
    así que la dirección 0 de aquí no es la dirección 0 de la función 0x03.
    La trama es idéntica a la 0x03; solo cambia el código, por eso hereda de ella.
    """
    CODIGO = 0x04

# Función 0x01: lee bits de lectura/escritura (salidas digitales)
class LeerCoils:
    """ Función Modbus 0x01 Read Coils.

    Los coils son bits de LECTURA Y ESCRITURA: salidas digitales on/off
    (relés, motores, válvulas). Son el equivalente en bits de los holding.
    La petición es igual que la 0x03, pero la respuesta es distinta: cada bit
    es un coil, 8 coils por byte y el primero en el bit menos significativo.
    Por eso unpack_respuesta desempaqueta bit a bit y corta en 'cantidad',
    ya que el último byte trae bits de relleno a 0.
    """
    CODIGO = 0x01
    # 250 bytes de datos en la respuesta (igual que en la 0x03) x 8 bits = 2000
    MAX_CANTIDAD = 2000

    def __init__(self, direccion, cantidad):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('cantidad', cantidad, 1, self.MAX_CANTIDAD)
        self.direccion = direccion
        self.cantidad = cantidad

    def pdu(self):
        return struct.pack('>BHH', self.CODIGO, self.direccion, self.cantidad)

    def unpack_respuesta(self, pdu):
        # PDU = código + byte count + bytes de coils
        # (cantidad + 7) // 8 es la división redondeando hacia arriba: 10 coils ocupan 2 bytes.
        # Se comprueba que llegan exactamente esos bytes, igual que en la 0x03.
        byte_count = (self.cantidad + 7) // 8
        if len(pdu) != 2 + byte_count or pdu[1] != byte_count:
            raise ErrorProtocolo(f'se esperaban {byte_count} bytes de bits')
        coils_bytes = pdu[2:]
        coils = []
        for byte in coils_bytes:
            for i in range(8):
                if len(coils) < self.cantidad:
                    coils.append((byte >> i) & 0x01)
        return coils

# Función 0x02: lee bits de solo lectura (entradas digitales)
class LeerEntradasDiscretas(LeerCoils):
    """ Función Modbus 0x02 Read Discrete Inputs.

    Los discrete inputs son bits de SOLO LECTURA: entradas digitales on/off
    (sensores, pulsadores). Son el equivalente en bits de los input registers.

    Hereda de LeerCoils por la misma razón que la 0x04 hereda de la 0x03: la
    petición y la respuesta tienen exactamente la misma forma (código + dirección
    + cantidad; byte count + bits empaquetados, 8 por byte, el primero en el bit
    menos significativo). Lo único que cambia es la tabla que se lee, y la tabla
    la decide el código de función. Así el desempaquetado de bits está escrito
    una sola vez y un arreglo en él vale para las dos funciones.
    """
    CODIGO = 0x02

# Función 0x06: escribe un holding register
class EscribirRegistro:
    """ Función Modbus 0x06 Write Single Register.

    Escribe un solo holding register (16 bits) en la dirección indicada.
    La petición es código + dirección + valor y la respuesta es idéntica a la petición.

    Un registro no tiene tipo: son 16 bits. Se admite de -32768 a 65535 para poder
    escribir tanto enteros con signo como sin signo. Los negativos viajan en
    complemento a 2: valor & 0xFFFF se queda con los 16 bits bajos, que es
    justo esa representación (-5 -> 0xFFFB). Sin la máscara, struct.pack('>H', -5)
    falla, porque H solo admite 0..65535.
    """
    CODIGO = 0x06

    def __init__(self, direccion, valor):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('valor', valor, -0x8000, 0xFFFF)
        self.direccion = direccion
        self.valor = valor & 0xFFFF  # valor tal como viaja en la trama

    def pdu(self):
        return struct.pack('>BHH', self.CODIGO, self.direccion, self.valor)

    def unpack_respuesta(self, pdu):
        # PDU = código + dirección + valor
        # La respuesta debe ser un eco exacto de la petición. Comparar los bytes
        # comprueba de una vez el código, la dirección, el valor y la longitud.
        if pdu != self.pdu():
            raise ErrorProtocolo('el eco no coincide con la petición')
        _, direccion, valor = struct.unpack('>BHH', pdu)
        return direccion, valor

# Función 0x05: escribe un coil (on/off)
class EscribirCoil(EscribirRegistro):
    """ Función Modbus 0x05 Write Single Coil.

    Escribe un solo coil (bit) en la dirección indicada.
    La petición es código + dirección + valor (0x0000 o 0xFF00) y la respuesta es idéntica a la petición.

    Hereda de EscribirRegistro porque la trama es la misma (código + dirección +
    2 bytes de valor, con eco como respuesta): pdu() y unpack_respuesta() valen
    tal cual. Solo cambia el código y cómo se traduce el valor a la trama, que
    es lo único que redefine el constructor: ON no viaja como 1 sino como 0xFF00.
    """
    CODIGO = 0x05

    def __init__(self, direccion, valor):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('valor', valor, 0, 1)
        self.direccion = direccion
        self.valor = 0xFF00 if valor else 0x0000

class EscribirRegistros:
    """ Función Modbus 0x10 Write Multiple Registers.

    Escribe varios holding registers (16 bits) a partir de la dirección indicada.
    La petición es código + dirección + cantidad + byte count + valores y la respuesta es código + dirección + cantidad.
    Los valores admiten negativos igual que en la 0x06 (complemento a 2).
    """
    CODIGO = 0x10
    # La PDU de petición no puede pasar de 253 bytes y tiene 6 fijos
    # (código, dirección, cantidad, byte count): quedan 246 bytes = 123 registros
    MAX_CANTIDAD = 123

    def __init__(self, direccion, valores):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('cantidad', len(valores), 1, self.MAX_CANTIDAD)
        for valor in valores:
            _comprobar('valor', valor, -0x8000, 0xFFFF)
        self.direccion = direccion
        self.cantidad = len(valores)
        self.valores = [valor & 0xFFFF for valor in valores]  # complemento a 2, como en la 0x06

    def pdu(self):
        byte_count = self.cantidad * 2
        return struct.pack(f'>BHHB{self.cantidad}H', self.CODIGO, self.direccion, self.cantidad, byte_count, *self.valores)

    def unpack_respuesta(self, pdu):
        # PDU = código + dirección + cantidad
        # El servidor confirma qué ha escrito: tiene que ser la dirección y la cantidad pedidas
        if pdu != struct.pack('>BHH', self.CODIGO, self.direccion, self.cantidad):
            raise ErrorProtocolo('la confirmación no coincide con la petición')
        _, direccion, cantidad = struct.unpack('>BHH', pdu)
        return direccion, cantidad

class EscribirCoils:
    """ Función Modbus 0x0F Write Multiple Coils.

    Escribe varios coils (bits) a partir de la dirección indicada.
    La petición es código + dirección + cantidad + byte count + valores y la respuesta es código + dirección + cantidad.
    """
    CODIGO = 0x0F
    # Los mismos 246 bytes libres que en la 0x10, pero x 8 bits = 1968 coils
    MAX_CANTIDAD = 1968

    def __init__(self, direccion, valores):
        _comprobar('direccion', direccion, 0, 0xFFFF)
        _comprobar('cantidad', len(valores), 1, self.MAX_CANTIDAD)
        for valor in valores:
            _comprobar('valor', valor, 0, 1)
        self.direccion = direccion
        self.cantidad = len(valores)
        self.valores = valores

    #este pdu convierte la lista de valores en bytes, #empaquetando la cantidad de coils y los valores en bits
    def pdu(self):
        byte_count = (self.cantidad + 7) // 8
        coils_bytes = bytearray(byte_count)
        for i, valor in enumerate(self.valores):
            if valor:
                coils_bytes[i // 8] |= (1 << (i % 8)) #esta línea establece el bit correspondiente en el byte adecuado de coils_bytes
        return struct.pack(f'>BHHB{byte_count}s', self.CODIGO, self.direccion, self.cantidad, byte_count, coils_bytes)

    def unpack_respuesta(self, pdu):
        # PDU = código + dirección + cantidad
        # El servidor confirma qué ha escrito: tiene que ser la dirección y la cantidad pedidas
        if pdu != struct.pack('>BHH', self.CODIGO, self.direccion, self.cantidad):
            raise ErrorProtocolo('la confirmación no coincide con la petición')
        _, direccion, cantidad = struct.unpack('>BHH', pdu)
        return direccion, cantidad

class LeerEscribirRegistros(LeerHoldingRegisters):
    """ Función Modbus 0x17 Read/Write Multiple Registers.

    Lee varios holding registers y escribe varios holding registers en una sola transacción.
    La petición es código + dirección de lectura + cantidad de lectura + dirección de escritura + cantidad de escritura + byte count + valores a escribir.
    La respuesta es código + byte count + valores leídos.

    Hereda de LeerHoldingRegisters porque su respuesta es exactamente la de la 0x03
    (byte count + registros leídos). Así reutiliza unpack_respuesta, con su
    comprobación del byte count, y el límite de 125 registros de lectura. Para que
    eso funcione, la dirección y la cantidad de lectura se guardan con super() en
    self.direccion y self.cantidad, los nombres que usa la clase padre. Solo se
    redefinen el constructor (añade la parte de escritura) y pdu().
    """
    CODIGO = 0x17
    # La petición tiene 10 bytes fijos: quedan 243 bytes = 121 registros de escritura
    MAX_ESCRITURA = 121

    def __init__(self, direccion_lectura, cantidad_lectura, direccion_escritura, valores_escritura):
        super().__init__(direccion_lectura, cantidad_lectura)
        _comprobar('direccion de escritura', direccion_escritura, 0, 0xFFFF)
        _comprobar('cantidad de escritura', len(valores_escritura), 1, self.MAX_ESCRITURA)
        for valor in valores_escritura:
            _comprobar('valor', valor, -0x8000, 0xFFFF)
        self.direccion_escritura = direccion_escritura
        self.cantidad_escritura = len(valores_escritura)
        self.valores_escritura = [valor & 0xFFFF for valor in valores_escritura]  # complemento a 2

    def pdu(self):
        byte_count = self.cantidad_escritura * 2
        return struct.pack(f'>BHHHHB{self.cantidad_escritura}H', self.CODIGO, self.direccion, self.cantidad, self.direccion_escritura, self.cantidad_escritura, byte_count, *self.valores_escritura)


# Se conecta al servidor, envía las peticiones y devuelve las respuestas decodificadas.
# Está en la biblioteca (y no en modbus_cli.py) porque el guion lo pide así: la demo
# se hace desde la consola de Python solo con modbus_tcp, y el CLI es una capa fina encima.
class ClienteModbusTCP:
    """ Cliente Modbus TCP.

    Con traza=True imprime cada trama enviada (TX) y recibida (RX) en hexadecimal,
    en mayúsculas y con los bytes separados por espacios, igual que el guion:
        TX: 00 01 00 00 00 06 01 03 00 6B 00 03
        RX: 00 01 00 00 00 09 01 03 06 02 2B 00 00 00 64
    Así se pueden comparar a simple vista con las tramas de ejemplo.
    """
    def __init__(self, ip='127.0.0.1', puerto=5020, unidad=1, timeout=5, traza=False):
        # Se comprueban aquí porque luego fallarían con errores poco claros:
        # un puerto > 65535 da OverflowError al conectar y una unidad > 255 da
        # struct.error al empaquetar la cabecera (Unit ID ocupa 1 byte)
        _comprobar('puerto', puerto, 1, 0xFFFF)
        _comprobar('unidad', unidad, 0, 0xFF)
        self.ip = ip
        self.puerto = puerto
        self.unidad = unidad
        self.timeout = timeout
        self.traza = traza
        self.socket = None
        self.transaction_id = 0

    def conectar(self):
        try:
            self.socket = socket.create_connection((self.ip, self.puerto), self.timeout)
        except OSError as e:
            raise ErrorConexion(e.strerror or e)

    def cerrar(self):
        if self.socket:
            self.socket.close()
        self.socket = None

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *exc):
        self.cerrar()

    def _trazar(self, sentido, trama):
        if self.traza:
            print(f'{sentido}: {trama.hex(" ").upper()}')

    def _recibir(self, n):
        """ Recibe exactamente n bytes (TCP puede partir la respuesta). """
        datos = b''
        while len(datos) < n:
            try:
                trozo = self.socket.recv(n - len(datos))
            except socket.timeout:
                raise ErrorTimeout()
            except OSError as e:
                # Cualquier otro fallo del socket (p. ej. conexión reiniciada por el servidor).
                # Va después de socket.timeout porque timeout también es un OSError
                raise ErrorConexion(e.strerror or e)
            if not trozo:
                raise ErrorConexion('El servidor cerró la conexión')
            datos += trozo
        return datos

    def ejecutar(self, funcion):
        """ Envía la función, espera la respuesta y la devuelve ya decodificada. """
        if not self.socket:
            raise ErrorConexion('Cliente no conectado')

        self.transaction_id = (self.transaction_id + 1) & 0xFFFF
        pdu = funcion.pdu()
        cabecera = CabeceraMBAP(self.transaction_id, 0, 1 + len(pdu), self.unidad)
        trama = cabecera.pack() + pdu
        self._trazar('TX', trama)
        try:
            self.socket.sendall(trama)
        except OSError as e:
            # Si la conexión se ha caído, sendall lanza OSError (p. ej. BrokenPipeError).
            # Se traduce a ErrorConexion para que quien use la biblioteca no tenga que conocer socket
            raise ErrorConexion(e.strerror or e)

        bytes_cabecera = self._recibir(CabeceraMBAP.TAM)
        resp = CabeceraMBAP.unpack(bytes_cabecera)
        # Comprobaciones de la cabecera de la respuesta, antes de fiarse de ella:
        # - transaction ID: el servidor copia el de la petición; si es otro, esta
        #   respuesta no es la de nuestra petición (p. ej. una respuesta atrasada)
        # - protocol ID: siempre 0 en Modbus
        # - length: cuenta Unit ID (1) + PDU (1 a 253), así que va de 2 a 254. Fuera
        #   de ese rango no se sabe cuántos bytes leer
        if resp.transaction_id != self.transaction_id:
            raise ErrorProtocolo(f'transaction ID {resp.transaction_id}, se esperaba {self.transaction_id}')
        if resp.protocol_id != 0:
            raise ErrorProtocolo(f'protocol ID {resp.protocol_id}, se esperaba 0')
        if not 2 <= resp.length <= 254:
            raise ErrorProtocolo(f'length {resp.length} imposible')
        pdu = self._recibir(resp.length - 1)
        self._trazar('RX', bytes_cabecera + pdu)

        # Una excepción es el mismo código de función pedido con el bit alto a 1
        # (código + 0x80) seguido de 1 byte con el código de excepción.
        # Se compara con el código de ESTA función y no solo con el bit 0x80: un
        # 0x83 en respuesta a una 0x01 no es una excepción de nuestra petición
        if pdu[0] == funcion.CODIGO | 0x80:
            if len(pdu) != 2:
                raise ErrorProtocolo('respuesta de excepción con longitud incorrecta')
            raise ExcepcionModbus(pdu[1])
        if pdu[0] != funcion.CODIGO:
            raise ErrorProtocolo(f'código de función 0x{pdu[0]:02X}, se esperaba 0x{funcion.CODIGO:02X}')
        return funcion.unpack_respuesta(pdu)

    def leer_holding_registers(self, direccion, cantidad):
        """ Atajo de la función 0x03. """
        return self.ejecutar(LeerHoldingRegisters(direccion, cantidad))

    def leer_input_registers(self, direccion, cantidad):
        """ Atajo de la función 0x04. """
        return self.ejecutar(LeerInputRegisters(direccion, cantidad))

    def leer_coils(self, direccion, cantidad):
        """ Atajo de la función 0x01. """
        return self.ejecutar(LeerCoils(direccion, cantidad))

    def leer_entradas_discretas(self, direccion, cantidad):
        """ Atajo de la función 0x02. """
        return self.ejecutar(LeerEntradasDiscretas(direccion, cantidad))

    def escribir_registro(self, direccion, valor):
        """ Atajo de la función 0x06. """
        return self.ejecutar(EscribirRegistro(direccion, valor))

    def escribir_coil(self, direccion, valor):
        """ Atajo de la función 0x05. """
        return self.ejecutar(EscribirCoil(direccion, valor))

    def escribir_registros(self, direccion, valores):
        """ Atajo de la función 0x10. """
        return self.ejecutar(EscribirRegistros(direccion, valores))

    def escribir_coils(self, direccion, valores):
        """ Atajo de la función 0x0F. """
        return self.ejecutar(EscribirCoils(direccion, valores))

    def leer_escribir_registros(self, direccion_lectura, cantidad_lectura, direccion_escritura, valores_escritura):
        """ Atajo de la función 0x17. """
        return self.ejecutar(LeerEscribirRegistros(direccion_lectura, cantidad_lectura, direccion_escritura, valores_escritura))


# Argumento fuera de rango: se detecta antes de enviar nada (salida 2)
class ArgumentoInvalido(Exception):
    """ Un parámetro de la petición está fuera de rango. """
    CODIGO_SALIDA = 2

    def __init__(self, motivo):
        super().__init__(f'ARGUMENTO INVALIDO: {motivo}')

# Excepción Modbus: el servidor responde con un código de error (salida 3)
#para provocar el error en el simulador leer registros a partir de la direccion 9999, o deshabilitar
#una funcion en Comportamiento. Despues el cliente debe seguir funcionando
class ExcepcionModbus(Exception):
    """ El servidor respondió con una excepción Modbus. """
    CODIGO_SALIDA = 3
    NOMBRES = {
        0x01: 'ILLEGAL FUNCTION',
        0x02: 'ILLEGAL DATA ADDRESS',
        0x03: 'ILLEGAL DATA VALUE',
        0x04: 'SERVER DEVICE FAILURE',
        0x05: 'ACKNOWLEDGE',
        0x06: 'SERVER DEVICE BUSY',
        0x08: 'MEMORY PARITY ERROR',
        0x0A: 'GATEWAY PATH UNAVAILABLE',
        0x0B: 'GATEWAY TARGET DEVICE FAILED TO RESPOND',
    }

    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(f'EXCEPCION 0x{codigo:02X} {self.NOMBRES.get(codigo, "DESCONOCIDA")}')

# Timeout: el servidor no responde a tiempo (salida 4)
#provocar error: en Comportamiento, atender solo a la Unit ID 1 con la política Descartar y hacer una peticion con otro ID
class ErrorTimeout(Exception):
    """ Se agotó el tiempo de espera de la respuesta. """
    CODIGO_SALIDA = 4

    def __init__(self):
        super().__init__('TIMEOUT')

# Error de conexión: no se puede conectar o se pierde la conexión (salida 5)
#conectar a un puerto en el que no escucha nadie.
class ErrorConexion(Exception):
    """ No se pudo establecer la conexión con el servidor. """
    CODIGO_SALIDA = 5

    def __init__(self, motivo):
        super().__init__(f'ERROR DE CONEXION: {motivo}')

# Error de protocolo: llega una respuesta, pero no corresponde a la petición (salida 6):
# transaction ID o código de función distintos, protocol ID o length imposibles,
# byte count incorrecto o eco/confirmación que no coincide
class ErrorProtocolo(Exception):
    """ La respuesta del servidor no es válida para la petición enviada. """
    CODIGO_SALIDA = 6

    def __init__(self, motivo):
        super().__init__(f'ERROR DE PROTOCOLO: {motivo}')
