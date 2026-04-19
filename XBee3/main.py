from scd30 import SCD30
from sen5x import SEN5x
from skaq1 import attr_report_batch
from machine import I2C, Pin
from sys import exit
from gc import collect
from time import sleep

from xbee import XBee

# 2 seconds is the minimum supported interval.
measurement_interval = 10

scd_temp_offset = -5.7
sen_temp_offset = -3.2

blue_led = Pin(Pin.board.D4, Pin.OUT)
blue_led(0)

i2c = I2C(1, freq = 100000)
scd30 = SCD30(i2c, 0x61)
sen = SEN5x(i2c)

sen.start()

repl_button = Pin(Pin.board.D5, Pin.IN, Pin.PULL_UP)

xbee = XBee()

def scaled(val, factor):
    return val * factor if val is not None else None

def report_if_changed(records):
    # records: iterable of (attr_name, val, prev_val)
    # val is expected in the Zigbee on-wire unit for the attribute.
    # Returns list of new prev values in the same order.
    # Skips None values and values within 0.2% of the previous report.
    # Sends one ZCL Report Attributes frame per cluster for the changed ones.
    new_prev = []
    to_send = []
    for name, val, prev in records:
        if val is None:
            new_prev.append(prev)
            continue
        if val == prev:
            new_prev.append(prev)
            continue
        if prev != 0 and abs(val - prev) / prev < 0.002:
            new_prev.append(prev)
            continue
        to_send.append((name, val))
        new_prev.append(val)
    if to_send:
        attr_report_batch(to_send)
    return new_prev

p_co2 = 0
p_temp = 0
p_rh = 0

p_ppm1_0 = 0
p_ppm2_5 = 0
p_ppm4_0 = 0
p_ppm10_0 = 0
p_voc = 0
p_nox = 0
p_temp_sen = 0

def publish_scd30_measurement(measurement):
    co2, temp, rh = measurement

    global p_co2, p_temp, p_rh
    p_co2, p_temp, p_rh = report_if_changed([
        ('co2', scaled(co2, 1e-6), p_co2),            # ZCL mol fraction
        ('temperature', scaled(temp, 100), p_temp),   # ZCL int16, 0.01 C
        ('humidity', scaled(rh, 100), p_rh),          # ZCL uint16, 0.01 %
    ])

def publish_sen_measurement(measurement):
    ppm1_0, ppm2_5, ppm4_0, ppm10_0, rh, temp_sen, voc, nox = measurement

    global p_ppm1_0, p_ppm2_5, p_ppm4_0, p_ppm10_0, p_voc, p_nox, p_temp_sen
    p_ppm1_0, p_ppm2_5, p_ppm4_0, p_ppm10_0, p_voc, p_nox, p_temp_sen = report_if_changed([
        ('pm1', ppm1_0, p_ppm1_0),                      # ZCL float, ug/m3
        ('pm25', ppm2_5, p_ppm2_5),                     # ZCL float, ug/m3
        ('pm40', ppm4_0, p_ppm4_0),                     # ZCL float, ug/m3
        ('pm10', ppm10_0, p_ppm10_0),                   # ZCL float, ug/m3
        ('voc', voc, p_voc),                            # raw index
        ('nox', nox, p_nox),                            # raw index
        ('t2', scaled(temp_sen, 100), p_temp_sen),      # ZCL int16, 0.01 C
    ])

def log_cycle(scd, sen_m):
    co2, scd_t, scd_rh = scd if scd is not None else (0, 0, 0)
    pm1, pm25, pm4, pm10, sen_rh, sen_t, voc, nox = sen_m
    print('CO2={:.0f} T={:.2f} RH={:.1f} | PM 1/2.5/4/10={}/{}/{}/{} VOC={} NOx={} SEN T={} RH={}'.format(
        co2, scd_t, scd_rh, pm1, pm25, pm4, pm10, voc, nox, sen_t, sen_rh))

def continuous_reading():
    while True:
        # If button 5 is pressed, drop to REPL
        if repl_button.value() == 0:
            raise Exception("Drop to REPL")

        if scd30.get_status_ready() and sen.data_ready:
            measurement = scd30.read_measurement()
            sen_m = sen.measured_values
            if measurement is not None:
                publish_scd30_measurement(measurement)
            publish_sen_measurement(sen_m)
            log_cycle(measurement, sen_m)
            collect() # gc.collect()

        sleep(1)

##########################

retries = 30
print("Probing sensor...")
ready = None
while ready is None and retries:
    try:
        ready = scd30.get_status_ready()
    except OSError:
        # The sensor may need a couple of seconds to boot up after power-on
        # and may not be ready to respond, raising I2C errors during this time.
        pass
    sleep(1)
    retries -= 1
if not retries:
    print("SCD30 wait timeout")
    exit(1)

scd30.set_temperature_offset(-scd_temp_offset)
sen.temperature_compensation_params = (sen_temp_offset, 0.0, 0)

scd30.set_measurement_interval(measurement_interval)
scd30.set_automatic_recalibration(enable=True)
scd30.start_continous_measurement()

# Prime the measurement cache so Read Attributes responses work during interview
print("Priming measurement cache...")
for _ in range(30):
    if scd30.get_status_ready() and sen.data_ready:
        measurement = scd30.read_measurement()
        sen_m = sen.measured_values
        if measurement is not None:
            publish_scd30_measurement(measurement)
        publish_sen_measurement(sen_m)
        log_cycle(measurement, sen_m)
        break
    sleep(1)

try:
    continuous_reading()
except Exception as e:
    msg = str(e)

    print('Exception: {}'.format(msg))
    print("Stopping periodic measurement...")
