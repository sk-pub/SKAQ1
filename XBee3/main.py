from ssd1306 import SSD1306_I2C
from scd30 import SCD30
from skaq1 import attr_report
from machine import I2C, Pin
from sys import exit

from xbee import XBee

# 2 seconds is the minimum supported interval.
measurement_interval = 10

blue_led = Pin(Pin.board.D4, Pin.OUT)
blue_led(0)

i2c = I2C(1, freq = 100000)
display = SSD1306_I2C(128, 32, i2c)
scd30 = SCD30(i2c, 0x61)

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

def publish_measurement(measurement):
    co2, temp, rh = measurement
    
    global p_co2
    global p_temp
    global p_rh

    temp_offset = 1.7

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

def continuous_reading():
    while True:
        # If button 5 is pressed, drop to REPL
        if repl_button.value() == 0:
            raise Exception("Drop to REPL")

        if scd30.get_status_ready():
            measurement = scd30.read_measurement()
            if measurement is not None:
                co2, temp, rh = measurement
                publish_measurement(measurement)

            sleep(measurement_interval)
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


display.contrast(0x00) # 0xff is the maximum

scd30.set_measurement_interval(measurement_interval)
scd30.set_automatic_recalibration(enable=True)
scd30.start_continous_measurement()

sleep(measurement_interval)


try:
    continuous_reading()
except Exception as e:
    msg = str(e)

    # print('Exception: {}'.format(msg))
    display_msg(msg)

    print("Stopping periodic measurement...")
    # scd30.stop_continous_measurement()

