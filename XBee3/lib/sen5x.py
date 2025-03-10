from micropython import const
from os import remove, rmdir
from time import sleep_ms
from struct import pack, unpack

class SEN5x:
    """
    Tested on:
        Sensirion SEN55
            https://sensirion.com/products/catalog/SEN55
        SparkFun XBee3 / MicroPython 1.12.0
            https://www.sparkfun.com/products/15435

    Based on:
        https://github.com/sugarpines/sensirion-sen5x
    """
    # class NotFoundError(Exception):
    #     pass

    # class CRCError(Exception):
    #     pass

    # class StatusError(Exception):
    #     pass

    # class ReadError(Exception):
    #     pass

    # class InvalidMode(Exception):
    #     pass

    # SEN5x I2C addresses
    DEFAULT_I2C_ADDR = const(0x69)
    START_MEASUREMENT = const(0x0021)
    START_MEASUREMENT_RHTGAS_ONLY = const(0x0037)
    STOP_MEASUREMENT = const(0x0104)
    DATA_READY_FLAG = const(0x0202)
    MEASURED_VALUES = const(0x03C4)
    TEMP_COMPENSATION_PARAMS = const(0x60B2)
    WARM_START_PARAM = const(0x60C6)
    VOC_ALGORITHM_TUNING_PARAMS = const(0x60D0)
    NOX_ALGORITHM_TUNING_PARAMS = const(0x60E1)
    RHT_ACCELERATION_MODE = const(0x60F7)
    VOC_ALGORITHM_STATE = const(0x6181)
    START_FAN_CLEANING = const(0x5607)
    AUTO_CLEANING_INTERVAL = const(0x8004)
    PRODUCT_NAME = const(0xD014)
    SERIAL_NUMBER = const(0xD033)
    FIRMWARE_VERSION = const(0xD100)
    DEVICE_STATUS = const(0xD206)
    CLEAR_DEVICE_STATUS = const(0xD210)
    RESET_DEVICE = const(0xD304)

    # SEN5x Status masks
    # FAN_SPEED_ERROR_MASK = const(1 << 21)
    # FAN_CLEANING_ACTIVE_MASK = const(1 << 19)
    # GAS_SENSOR_ERROR_MASK = const(1 << 7)
    # RHT_ERROR_MASK = const(1 << 6)
    # LASER_ERROR_MASK = const(1 << 5)
    # FAN_FAIL_ERROR_MASK = const(1 << 4)

    I2C_BUFFER_SIZE = const(48)  # bytes, max used by product_line (must be divisible by 3)
    MIN_EXE_TIME = const(20)  # minimum time to execute I2C command in ms per datasheet
    TEMP_COMP_OFFSET_SCALE_FACTOR = const(200)  # for TEMP_COMPENSATION_PARAMS
    TEMP_COMP_SLOPE_SCALE_FACTOR = const(10000)  # for TEMP_COMPENSATION_PARAMS

    CRC_TABLE = [  # see datasheet for checksum calculation
        0, 49, 98, 83, 196, 245, 166, 151, 185, 136, 219, 234, 125, 76, 31, 46,
        67, 114, 33, 16, 135, 182, 229, 212, 250, 203, 152, 169, 62, 15, 92, 109,
        134, 183, 228, 213, 66, 115, 32, 17, 63, 14, 93, 108, 251, 202, 153, 168,
        197, 244, 167, 150, 1, 48, 99, 82, 124, 77, 30, 47, 184, 137, 218, 235,
        61, 12, 95, 110, 249, 200, 155, 170, 132, 181, 230, 215, 64, 113, 34, 19,
        126, 79, 28, 45, 186, 139, 216, 233, 199, 246, 165, 148, 3, 50, 97, 80,
        187, 138, 217, 232, 127, 78, 29, 44, 2, 51, 96, 81, 198, 247, 164, 149,
        248, 201, 154, 171, 60, 13, 94, 111, 65, 112, 35, 18, 133, 180, 231, 214,
        122, 75, 24, 41, 190, 143, 220, 237, 195, 242, 161, 144, 7, 54, 101, 84,
        57, 8, 91, 106, 253, 204, 159, 174, 128, 177, 226, 211, 68, 117, 38, 23,
        252, 205, 158, 175, 56, 9, 90, 107, 69, 116, 39, 22, 129, 176, 227, 210,
        191, 142, 221, 236, 123, 74, 25, 40, 6, 55, 100, 85, 194, 243, 160, 145,
        71, 118, 37, 20, 131, 178, 225, 208, 254, 207, 156, 173, 58, 11, 88, 105,
        4, 53, 102, 87, 192, 241, 162, 147, 189, 140, 223, 238, 121, 72, 27, 42,
        193, 240, 163, 146, 5, 52, 103, 86, 120, 73, 26, 43, 188, 141, 222, 239,
        130, 179, 224, 209, 70, 119, 36, 21, 59, 10, 89, 104, 255, 206, 157, 172
    ]

    def __init__(self, i2c, address: int = DEFAULT_I2C_ADDR):
        self.i2c = i2c
        self.address = address
        # reuse buffers in effort to reduce heap fragmentation
        self._i2c_buffer = bytearray(self.I2C_BUFFER_SIZE)
        self._read_buffer = bytearray(self.I2C_BUFFER_SIZE * 2 // 3)  # no crc

    @property
    def product_name(self) -> str:
        self._cmd_read(self.PRODUCT_NAME, num_words=16)
        return self._words_to_string(self._read_buffer)

    @property
    def serial_number(self) -> str:
        self._cmd_read(self.SERIAL_NUMBER, num_words=16)
        return self._words_to_string(self._read_buffer)

    @property
    def firmware_version(self) -> int:
        self._cmd_read(self.FIRMWARE_VERSION, num_words=1)
        return int(self._read_buffer[0])

    @property
    def data_ready(self) -> bool:
        self._cmd_read(self.DATA_READY_FLAG, num_words=1)
        return bool(self._read_buffer[1])

    @property
    def measured_values(self) -> tuple[float, float, float, float, float, float, float, float]:
        self._cmd_read(self.MEASURED_VALUES, num_words=8)
        ppm1_0, ppm2_5, ppm4_0, ppm10_0, rh, t, voc, nox = unpack('>4H4h', self._read_buffer)
        return (
            self._check_and_scale(ppm1_0, scale_factor=10),
            self._check_and_scale(ppm2_5, scale_factor=10),
            self._check_and_scale(ppm4_0, scale_factor=10),
            self._check_and_scale(ppm10_0, scale_factor=10),
            self._check_and_scale(rh, scale_factor=100),
            self._check_and_scale(t, scale_factor=200),
            self._check_and_scale(voc, scale_factor=10),
            self._check_and_scale(nox, scale_factor=10)
        )

    @property
    def temperature_compensation_params(self) -> tuple[float, float, int]:
        self._cmd_read(self.TEMP_COMPENSATION_PARAMS, num_words=3)
        offset, slope, time_const = unpack('>2hH', self._read_buffer)
        return (
            round(offset / self.TEMP_COMP_OFFSET_SCALE_FACTOR, 2),
            round(slope / self.TEMP_COMP_SLOPE_SCALE_FACTOR, 4),
            time_const
        )

    @temperature_compensation_params.setter
    def temperature_compensation_params(self, params: tuple[float, float, int]) -> None:
        offset, slope, time_const = params
        offset = round(offset * self.TEMP_COMP_OFFSET_SCALE_FACTOR)
        slope = round(slope * self.TEMP_COMP_SLOPE_SCALE_FACTOR)
        # valid ranges are not clear from datasheets, these at least don't overflow buffers
        if not -0x7FFF <= offset <= 0x7FFF:
            raise ValueError('Offset out of range')
        if not (-0x7FFF <= slope <= 0x7FFF):
            raise ValueError('Slope out of range')
        if not 0 <= time_const <= 0xFFFF:
            raise ValueError('Time Const out of range')
        self._cmd_write(self.TEMP_COMPENSATION_PARAMS, pack('>2hH', offset, slope, time_const))

    # @property
    # def status(self) -> int:
    #     self._cmd_read(self.DEVICE_STATUS, num_words=2)
    #     return unpack('>I', self._read_buffer)[0]

    def start(self):
        # self.check_i2c()
        self.reset()  # in case running
        self.start_measurement()
        # self.check_for_errors()

    def stop(self):
        self.stop_measurement()

    def start_measurement(self, num_checks: int = 100) -> bool:
        self._cmd_exe(self.START_MEASUREMENT, cmd_exe_time=50)
        for _ in range(num_checks):  # takes ~800 ms for data to be ready
            if self.data_ready:
                ready = True
                break
            else:
                sleep_ms(100)
        else:
            ready = False

        return ready

    def stop_measurement(self) -> None:
        self._cmd_exe(self.STOP_MEASUREMENT, cmd_exe_time=200)

    # def check_i2c(self) -> None:
    #     try:
    #         if self.address not in self.i2c.scan():
    #             raise self.NotFoundError('I2C address not found')
    #     except Exception as e:
    #         raise self.NotFoundError(e)

    # def check_for_errors(self) -> None:
    #     status = self.status
    #     if status & self.FAN_SPEED_ERROR_MASK:
    #         raise self.StatusError('Fan Speed Error')
    #     if status & self.GAS_SENSOR_ERROR_MASK:
    #         raise self.StatusError('Gas Sensor Error')
    #     if status & self.RHT_ERROR_MASK:
    #         raise self.StatusError('RHT Error')
    #     if status & self.LASER_ERROR_MASK:
    #         raise self.StatusError('Laser Error')
    #     if status & self.FAN_FAIL_ERROR_MASK:
    #         raise self.StatusError('Fan Fail Error')

    def reset(self) -> None:
        self._cmd_exe(self.RESET_DEVICE, cmd_exe_time=100)

    def _cmd_exe(self,
                 cmd: int,
                 cmd_exe_time: int = MIN_EXE_TIME,
                 ) -> None:
        self.i2c.writeto(self.address, pack('>H', cmd))
        sleep_ms(cmd_exe_time)  # time to execute before reading

    def _cmd_read(self,
                  cmd: int,
                  num_words: int,
                  cmd_exe_time: int = MIN_EXE_TIME,
                  ) -> None:
        self._cmd_exe(cmd, cmd_exe_time=cmd_exe_time)
        self.i2c.readfrom_into(self.address, self._i2c_buffer)

        for i in range(num_words):
            msb = self._i2c_buffer[i * 3]
            lsb = self._i2c_buffer[i * 3 + 1]
            crc = self._i2c_buffer[i * 3 + 2]
            # self._validate_crc(msb, lsb, crc)
            self._read_buffer[i * 2] = msb
            self._read_buffer[i * 2 + 1] = lsb

    def _cmd_write(self,
                   cmd: int,
                   words: bytes,  # can't be 0 or odd len()
                   cmd_exe_time: int = MIN_EXE_TIME
                   ) -> None:
        for i in range(len(words) // 2):  # 2 bytes per word
            msb = words[i * 2]
            lsb = words[i * 2 + 1]
            crc = self._lookup_crc(msb, lsb)
            self._i2c_buffer[i * 3] = msb
            self._i2c_buffer[i * 3 + 1] = lsb
            self._i2c_buffer[i * 3 + 2] = crc
        # noinspection PyUnboundLocalVariable
        self.i2c.writeto_mem(self.address, cmd, self._i2c_buffer[:(i + 1) * 3], addrsize=16)
        sleep_ms(cmd_exe_time)

    # @staticmethod
    # def _validate_crc(msb: int, lsb: int, crc: int) -> None:
    #     if SEN5x._lookup_crc(msb, lsb) != crc:
    #         raise SEN5x.CRCError('Checksum error')

    @staticmethod
    def _lookup_crc(msb: int, lsb: int) -> int:
        crc = 0xFF ^ msb
        crc = SEN5x.CRC_TABLE[crc] ^ lsb
        crc = SEN5x.CRC_TABLE[crc]

        return crc

    @staticmethod
    def _words_to_string(words: bytearray) -> str:
        for i in range(len(words)):  # bytearray doesn't support find()
            if words[i] == 0:  # found end
                break
        else:  # didn't find end
            raise ValueError('No terminator')
        return words[:i].decode('ascii')

    @staticmethod
    def _check_and_scale(int16: int, scale_factor: int = 1) -> [float, None]:
        return int16 / scale_factor if int16 not in (0x7FFF, 0xFFFF) else None
