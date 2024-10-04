const {
  temperature,
  humidity,
  co2,
} = require("zigbee-herdsman-converters/lib/modernExtend");

const definition = {
  zigbeeModel: ["AQ1"],
  model: "AQ1",
  vendor: "SK",
  description: "CO2, Temperature and Humidity sensor by SK",
  extend: [temperature(), humidity(), co2()],
  meta: {},
};

module.exports = definition;
