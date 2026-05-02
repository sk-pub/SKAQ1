const {
  temperature,
  humidity,
  co2,
  pm25,
  numeric,
  deviceAddCustomCluster,
} = require("zigbee-herdsman-converters/lib/modernExtend");

const { Zcl } = require("zigbee-herdsman");

const DEVICE_MODEL = "SKAQ1";

const CUSTOM_CLUSTER = `${DEVICE_MODEL}_airq`;

const definition = {
  zigbeeModel: [DEVICE_MODEL],
  model: DEVICE_MODEL,
  vendor: "SK",
  description: "Air quality, temperature and humidity sensor by SK",
  extend: [
    temperature(),
    humidity(),
    co2(),
    pm25(),

    deviceAddCustomCluster(CUSTOM_CLUSTER, {
      ID: 0xfc01,
      name: CUSTOM_CLUSTER,
      attributes: {
        pm1: { name: "pm1", ID: 0x0000, type: Zcl.DataType.SINGLE_PREC },
        pm4: { name: "pm4", ID: 0x0001, type: Zcl.DataType.SINGLE_PREC },
        pm10: { name: "pm10", ID: 0x0002, type: Zcl.DataType.SINGLE_PREC },
        voc: { name: "voc", ID: 0x0003, type: Zcl.DataType.SINGLE_PREC },
        nox: { name: "nox", ID: 0x0004, type: Zcl.DataType.SINGLE_PREC },
        t2: { name: "t2", ID: 0x0005, type: Zcl.DataType.INT16 },
        ref_temp: { name: "ref_temp", ID: 0x0006, type: Zcl.DataType.INT16, write: true, report: true },
      },
      commands: {},
      commandsResponse: {},
    }),
    numeric({
      name: "PM1",
      cluster: CUSTOM_CLUSTER,
      attribute: "pm1",
      unit: "µg/m³",
      access: "STATE_GET",
      reporting: {
        min: 0,
        max: 1000,
        change: 0.1,
      },
      precision: 1,
      description: "Measured PM1 value",
    }),
    numeric({
      name: "PM4",
      cluster: CUSTOM_CLUSTER,
      attribute: "pm4",
      unit: "µg/m³",
      access: "STATE_GET",
      reporting: {
        min: 0,
        max: 1000,
        change: 0.1,
      },
      precision: 1,
      description: "Measured PM4 value",
    }),
    numeric({
      name: "PM10",
      cluster: CUSTOM_CLUSTER,
      attribute: "pm10",
      unit: "µg/m³",
      access: "STATE_GET",
      reporting: {
        min: 0,
        max: 1000,
        change: 0.1,
      },
      precision: 1,
      description: "Measured PM10 value",
    }),
    numeric({
      name: "VOC",
      cluster: CUSTOM_CLUSTER,
      attribute: "voc",
      unit: "VOC index",
      access: "STATE_GET",
      reporting: {
        min: 0,
        max: 500,
        change: 1,
      },
      precision: 0,
      description: "VOC index. 100 in the average background value",
    }),
    numeric({
      name: "NOx",
      cluster: CUSTOM_CLUSTER,
      attribute: "nox",
      unit: "NOx index",
      access: "STATE_GET",
      reporting: {
        min: 0,
        max: 500,
        change: 1,
      },
      precision: 0,
      description: "NOx index. 1 is no NOx present",
    }),
    numeric({
      name: "SEN55 temperature",
      cluster: CUSTOM_CLUSTER,
      attribute: "t2",
      unit: "°C",
      access: "STATE_GET",
      reporting: { min: "1_SECOND", max: "1_HOUR", change: 100 },
      scale: 100,
      description: "Temperature from the Sensirion SEN55 sensor",
    }),
    numeric({
      name: "reference_temperature",
      cluster: CUSTOM_CLUSTER,
      attribute: "ref_temp",
      unit: "°C",
      access: "STATE_SET",
      reporting: { min: "1_SECOND", max: "1_HOUR", change: 10 },
      scale: 100,
      valueMin: -10,
      valueMax: 50,
      valueStep: 0.1,
      description:
        "Live average of both temperature sensors. Edit to recalibrate: write " +
        "the actual room temperature and the device adjusts both sensors so " +
        "their readings match. Wait for the enclosure air to equilibrate before editing.",
    }),
  ],
  meta: {},
};

module.exports = definition;
