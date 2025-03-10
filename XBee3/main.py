from ssd1306 import SSD1306_I2C
from scd30 import SCD30
from sen5x import SEN5x
from skaq1 import attr_report
from machine import I2C, Pin
from sys import exit
from gc import collect

from xbee import XBee

# 2 seconds is the minimum supported interval.
measurement_interval = 10

temp_offset = 0.9

blue_led = Pin(Pin.board.D4, Pin.OUT)
blue_led(0)

i2c = I2C(1, freq = 100000)
display = SSD1306_I2C(128, 32, i2c)
scd30 = SCD30(i2c, 0x61)
sen = SEN5x(i2c)

sen.start()

repl_button = Pin(Pin.board.D5, Pin.IN, Pin.PULL_UP)

xbee = XBee()

def sleep(t):
    xbee.sleep_now(t * 1000, False)

def display_msg(msg):
    display.fill(0)
    display.text(msg, 0, 24, 1)
    display.show()   

def report_if_changed(attr_name, val, p_val):
    if p_val != 0 and abs(val - p_val) / p_val < 0.002:
        # Change is less than tolerance
        return p_val
    
    attr_report(attr_name, val)
    return val

p_co2 = 0
p_temp = 0
p_rh = 0

def publish_scd30_measurement(measurement):
    co2, temp, rh = measurement
    
    global p_co2
    global p_temp
    global p_rh

    try:
        p_co2 = report_if_changed('co2', co2, p_co2)
        p_temp = report_if_changed('temperature', temp, p_temp)
        p_rh = report_if_changed('humidity', rh, p_rh)
    except:
        pass
    
    line1 = 'CO2: {:.2f} ppm'.format(co2)
    line2 = "T: {:.1f} 'C -{:.1f}".format(temp, scd30.get_temperature_offset())
    line3 = 'RH: {:.2f} %'.format(rh)
    
    display.fill(0)
    display.text(line1, 0, 0, 1)
    display.text(line2, 0, 8, 1)
    display.text(line3, 0, 16, 1)
    display.show()

def publish_sen_measurement(measurement):
    ppm1_0, ppm2_5, ppm4_0, ppm10_0, rh, t, voc, nox = measurement
    print('PPM 1.0:', ppm1_0, 'PPM 2.5:', ppm2_5, 'PPM 4.0:', ppm4_0, 'PPM 10.0:', ppm10_0)
    print('Humidity:', rh, 'Temp:', t, 'VOC:', voc, 'NOx:', nox)
    
    try:
        p_ppm1_0 = attr_report('pm1', ppm1_0 * 1000000)
        p_ppm2_5 = attr_report('pm25', ppm2_5 * 1000000)
        p_ppm2_5 = attr_report('pm40', ppm4_0 * 1000000)
        p_ppm10_0 = attr_report('pm10', ppm10_0 * 1000000)
        p_voc = attr_report('voc', voc * 1000000)
        p_nox = attr_report('nox', nox * 1000000)
    except Exception as e:
        print(e)
        pass
    
    line4 = "VOC: {:.1f} 'NOx {:.1f}".format(voc, nox)
    
    display.text(line4, 0, 24, 1)
    display.show()

def continuous_reading():
    while True:
        # If button 5 is pressed, drop to REPL
        if repl_button.value() == 0:
            raise Exception("Drop to REPL")

        if scd30.get_status_ready() and sen.data_ready:
            measurement = scd30.read_measurement()
            if measurement is not None:
                co2, temp, rh = measurement
                publish_scd30_measurement(measurement)

            publish_sen_measurement(sen.measured_values)

            sleep(measurement_interval)
            collect() # gc.collect()
        else:
            sleep(1)

##########################

display_msg('Loading...')


retries = 30
# print("Probing sensor...")
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


scd30.set_temperature_offset(temp_offset)
display.contrast(0x00) # 0xff is the maximum

scd30.set_measurement_interval(measurement_interval)
scd30.set_automatic_recalibration(enable=True)
scd30.start_continous_measurement()

sleep(measurement_interval)


try:
    continuous_reading()
except Exception as e:
    msg = str(e)

    print('Exception: {}'.format(msg))
    display_msg(msg)

    print("Stopping periodic measurement...")
    # scd30.stop_continous_measurement()

