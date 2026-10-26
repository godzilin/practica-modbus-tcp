#El programa de línea de órdenes (el cliente)
#Este programa Ejecuta una sola petición con la biblioteca propia:
#python3 modbus_cli.py [--ip IP] [--puerto P] [--unidad U] [--timeout S] [--traza] ORDEN ARGUMENTOS .
#Las órdenes son leer-coils , leer-entradas , leer-holding y leer-input (dirección y cantidad),
#escribir-coil y escribir-registro (dirección y valor), escribir-coils y escribir-registros (dirección y
#valores) y leer-escribir (dirección de lectura, cantidad, dirección de escritura y valores).
#
#La salida es exacta (la comprueba el corrector):
#  lectura de bits ........ una línea por bit: direccion valor
#  lectura de registros ... una línea por registro: direccion sin_signo con_signo 0xHHHH
#  escritura correcta ..... OK
#  error .................. el mensaje del error, y sale con su código (2 a 6)

import argparse
import sys

import modbus_tcp as mb
class Parser(argparse.ArgumentParser):
    """ ArgumentParser que informa de los errores.

    argparse ya sale con código 2 cuando un argumento está mal escrito (p. ej.
    'leer-holding abc 3'), pero imprime su propio mensaje de uso. Aquí solo se
    cambia el mensaje a 'ARGUMENTO INVALIDO: <motivo>'. Los subcomandos se crean
    con la misma clase que el parser principal, así que también lo usan.
    """
    def error(self, message):
        print(f'ARGUMENTO INVALIDO: {message}')
        sys.exit(mb.ArgumentoInvalido.CODIGO_SALIDA)


def imprimir_bits(direccion, bits):
    """ Una línea por bit: direccion valor. 
    Esto es lo que devuelve la biblioteca, que es lo que viaja: 0 o 1."""
    for i, bit in enumerate(bits):
        print(direccion + i, bit)


def imprimir_registros(direccion, registros):
    """ Una línea por registro: direccion sin_signo con_signo 0xHHHH.

    La biblioteca devuelve los registros sin signo (0..65535), que es lo que viaja.
    El valor con signo se obtiene deshaciendo el complemento a 2: si el bit más
    alto (0x8000) está a 1, el número es negativo y vale valor - 0x10000
    (0xFFFB = 65531 -> 65531 - 65536 = -5).
    """
    for i, valor in enumerate(registros):
        con_signo = valor - 0x10000 if valor & 0x8000 else valor
        print(f'{direccion + i} {valor} {con_signo} 0x{valor:04X}')


def main():
    parser = Parser(description='Cliente Modbus TCP')
    parser.add_argument('--ip', default='127.0.0.1')
    parser.add_argument('--puerto', type=int, default=5020)
    parser.add_argument('--unidad', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--traza', action='store_true', help='muestra las tramas enviadas (TX) y recibidas (RX) en hexadecimal')

    # Cada orden es un subcomando con sus propios argumentos
    ordenes = parser.add_subparsers(dest='orden', required=True)
    orden = ordenes.add_parser('leer-holding', help='0x03 Read Holding Registers')
    orden.add_argument('direccion', type=int)
    orden.add_argument('cantidad', type=int)

    orden = ordenes.add_parser('leer-input', help='0x04 Read Input Registers')
    orden.add_argument('direccion', type=int)
    orden.add_argument('cantidad', type=int)

    orden = ordenes.add_parser('leer-coils', help='0x01 Read Coils')
    orden.add_argument('direccion', type=int)
    orden.add_argument('cantidad', type=int)

    orden = ordenes.add_parser('leer-entradas', help='0x02 Read Discrete Inputs')
    orden.add_argument('direccion', type=int)
    orden.add_argument('cantidad', type=int)

    orden = ordenes.add_parser('escribir-coil', help='0x05 Write Single Coil')
    orden.add_argument('direccion', type=int)
    orden.add_argument('valor', type=int)

    orden = ordenes.add_parser('escribir-registro', help='0x06 Write Single Register')
    orden.add_argument('direccion', type=int)
    orden.add_argument('valor', type=int)

    orden = ordenes.add_parser('escribir-coils', help='0x0F Write Multiple Coils')
    orden.add_argument('direccion', type=int)
    orden.add_argument('valores', type=int, nargs='+')

    orden = ordenes.add_parser('escribir-registros', help='0x10 Write Multiple Registers')
    orden.add_argument('direccion', type=int)
    orden.add_argument('valores', type=int, nargs='+')

    orden = ordenes.add_parser('leer-escribir', help='0x17 Read/Write Multiple Registers')
    orden.add_argument('direccion_lectura', type=int)
    orden.add_argument('cantidad', type=int)
    orden.add_argument('direccion_escritura', type=int)
    orden.add_argument('valores', type=int, nargs='+')

    args = parser.parse_args()

    try:
        with mb.ClienteModbusTCP(args.ip, args.puerto, args.unidad, args.timeout, args.traza) as cliente:
            if args.orden == 'leer-holding':
                imprimir_registros(args.direccion, cliente.leer_holding_registers(args.direccion, args.cantidad))
            elif args.orden == 'leer-input':
                imprimir_registros(args.direccion, cliente.leer_input_registers(args.direccion, args.cantidad))
            elif args.orden == 'leer-coils':
                imprimir_bits(args.direccion, cliente.leer_coils(args.direccion, args.cantidad))
            elif args.orden == 'leer-entradas':
                imprimir_bits(args.direccion, cliente.leer_entradas_discretas(args.direccion, args.cantidad))
            elif args.orden == 'leer-escribir':
                imprimir_registros(args.direccion_lectura, cliente.leer_escribir_registros(
                    args.direccion_lectura, args.cantidad, args.direccion_escritura, args.valores))
            else:
                # Escrituras: si no ha saltado ningún error, el servidor confirmó la escritura
                if args.orden == 'escribir-coil':
                    cliente.escribir_coil(args.direccion, args.valor)
                elif args.orden == 'escribir-registro':
                    cliente.escribir_registro(args.direccion, args.valor)
                elif args.orden == 'escribir-coils':
                    cliente.escribir_coils(args.direccion, args.valores)
                elif args.orden == 'escribir-registros':
                    cliente.escribir_registros(args.direccion, args.valores)
                print('OK')
    except (mb.ArgumentoInvalido, mb.ExcepcionModbus, mb.ErrorTimeout, mb.ErrorConexion, mb.ErrorProtocolo) as e:
        print(e)
        sys.exit(e.CODIGO_SALIDA)


if __name__ == '__main__':
    main()
