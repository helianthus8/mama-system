import time
import ntptime
from hcsr04 import HCSR04
from lcd_i2c import LCD
from machine import I2C, Pin, PWM
from umqtt.simple import MQTTClient
import network
import machine
import utime

sensor = HCSR04(trigger_pin=12, echo_pin=14)

red = PWM(Pin(5), freq=500)
green = PWM(Pin(17), freq=500)
blue = PWM(Pin(16), freq=500)


def set_rgb_color(r, g, b):
    red.duty_u16(65535 - r)
    green.duty_u16(65535 - g)
    blue.duty_u16(65535 - b)


color_descanso = (5000, 2000, 0)
color_estudio = (0, 5000, 5000)
color_ambiente = (2500, 1200, 200)
color_alerta = (5000, 0, 0)
color_apagado = (0, 0, 0)

I2C_ADDR = 0x27
i2c = I2C(0, scl=Pin(18), sda=Pin(19), freq=800000)
lcd = LCD(addr=I2C_ADDR, cols=16, rows=2, i2c=i2c)

lcd.begin()
lcd.print("Hola!")

ssid = "Wokwi-GUEST"
wifipassword = ""

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect(ssid, wifipassword)
print("Conectando al WiFi...")
while not sta_if.isconnected():
    print(".", end="")
    time.sleep(0.1)

print("\nConectado al WiFi!")
print(sta_if.ifconfig())

try:
    print("Sincronizando hora con NTP...")
    ntptime.settime()
    print("Hora sincronizada")
except Exception as e:
    print(f"Error al sincronizar la hora con NTP: {e}")

mqtt_server = "io.adafruit.com"
port = 1883
user = "TU_USUARIO_ADAFRUIT_IO"
password = "TU_CLAVE_ADAFRUIT_IO"
client_id = "esp32_dispositivo_1"
topic_1 = f"{user}/feeds/mumsystem"


def funcion_callback(topic, msg):
    dato = msg.decode("utf-8")
    topicrec = topic.decode("utf-8")
    print(f"Mensaje recibido en {topicrec}: {dato}")


def conectar_mqtt():
    try:
        conexionMQTT = MQTTClient(
            client_id, mqtt_server, user=user, password=password, port=int(port)
        )
        conexionMQTT.set_callback(funcion_callback)
        conexionMQTT.connect()
        conexionMQTT.subscribe(topic_1)
        print("Conectado al Broker MQTT")
        return conexionMQTT
    except Exception as e:
        print(f"Error al conectar al Broker MQTT: {e}")
        return None


conexionMQTT = None
while conexionMQTT is None:
    print("Intentando conectar al broker MQTT...")
    conexionMQTT = conectar_mqtt()
    time.sleep(5)


def obtener_hora_actual():
    current_time = utime.localtime()
    hora_local = (current_time[3] - 3) % 24
    return hora_local, current_time[4]


BLOQUES_DIURNOS = [
    (7.0, 12.0, "Estudio_Manana", "Hora de Estudio", "Estado: Estudio", color_estudio),
    (12.0, 13.5, "Comer_Descanso", "Hora de Comer", "Estado: Comida/Descanso", color_descanso),
    (13.5, 18.0, "Estudio_Tarde", "Hora de Estudio", "Estado: Estudio", color_estudio),
    (18.0, 23.0, "Libre_Tarde", "Tiempo Libre", "Estado: Tiempo Libre", color_ambiente),
]

ESTADO_DORMIR = ("Dormir", "Hora de Dormir", "Estado: Dormir (Luces Off)", color_apagado)

UMBRAL_DISTANCIA_CM = 80
TIEMPO_SIN_PRESENCIA_S = 900
INTERVALO_CHEQUEO_S = 15

last_presence_time = time.time()
no_presence_alert_sent = False
last_estado = None
last_check = 0


def obtener_bloque_horario(hora_decimal):
    if hora_decimal >= 23.0 or hora_decimal < 7.0:
        return ESTADO_DORMIR

    for inicio, fin, estado, texto_lcd, msg_mqtt, color in BLOQUES_DIURNOS:
        if inicio <= hora_decimal < fin:
            return estado, texto_lcd, msg_mqtt, color

    return ESTADO_DORMIR


def evaluar_presencia():
    global last_presence_time, no_presence_alert_sent

    try:
        distance = sensor.distance_cm()
    except OSError as e:
        print(f"Error de lectura en sensor ultrasónico: {e}")
        return False

    print(f"Distancia detectada: {distance:.1f} cm")

    if distance <= UMBRAL_DISTANCIA_CM:
        last_presence_time = time.time()
        no_presence_alert_sent = False
        return False

    if (time.time() - last_presence_time) >= TIEMPO_SIN_PRESENCIA_S:
        if not no_presence_alert_sent:
            print("Ausencia prolongada detectada")
            lcd.backlight()
            lcd.clear()
            lcd.print("Volve a estudiar")
            set_rgb_color(*color_alerta)
            if conexionMQTT is not None:
                try:
                    conexionMQTT.publish(topic_1, "Alerta: Ausencia prolongada")
                except Exception as e:
                    print(f"Error al publicar alerta MQTT: {e}")
            no_presence_alert_sent = True
        return True

    return False


while True:
    try:
        try:
            conexionMQTT.check_msg()
        except Exception as e:
            print(f"Error en MQTT, reintentando conexión: {e}")
            conexionMQTT = conectar_mqtt()
            time.sleep(2)
            continue

        ahora = time.time()
        if (ahora - last_check) >= INTERVALO_CHEQUEO_S:
            last_check = ahora

            hora, minuto = obtener_hora_actual()
            hora_decimal = hora + (minuto / 60.0)
            print(f"Hora local: {hora:02d}:{minuto:02d}")

            estado, texto_lcd, msg_mqtt, color = obtener_bloque_horario(hora_decimal)

            if estado == "Dormir":
                last_presence_time = time.time()
                no_presence_alert_sent = False
                if estado != last_estado:
                    print(msg_mqtt)
                    set_rgb_color(*color_apagado)
                    lcd.clear()
                    lcd.print(texto_lcd)
                    lcd.no_backlight()
                    if conexionMQTT is not None:
                        try:
                            conexionMQTT.publish(topic_1, msg_mqtt)
                        except Exception as e:
                            print(f"Error al publicar estado MQTT: {e}")
                    last_estado = estado
                time.sleep(0.2)
                continue

            ausente = evaluar_presencia()
            if ausente:
                time.sleep(0.2)
                continue

            if estado != last_estado:
                print(msg_mqtt)
                lcd.backlight()
                set_rgb_color(*color)
                lcd.clear()
                lcd.print(texto_lcd)
                if conexionMQTT is not None:
                    try:
                        conexionMQTT.publish(topic_1, msg_mqtt)
                    except Exception as e:
                        print(f"Error al publicar estado MQTT: {e}")
                last_estado = estado

        time.sleep(0.5)

    except OSError as e:
        print("Error crítico en bucle principal:", e)
        time.sleep(5)
        machine.reset()