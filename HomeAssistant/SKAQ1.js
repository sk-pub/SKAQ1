const fz = require('zigbee-herdsman-converters/converters/fromZigbee');
const tz = require('zigbee-herdsman-converters/converters/toZigbee');
const exposes = require('zigbee-herdsman-converters/lib/exposes');
const reporting = require('zigbee-herdsman-converters/lib/reporting');
const extend = require('zigbee-herdsman-converters/lib/extend');
const e = exposes.presets;
const ea = exposes.access;

const definition = {
    zigbeeModel: ['AQ1'], // The model ID from: Device with modelID 'lumi.sens' is not supported.
    model: 'SKAQ1', // Vendor model number, look on the device for a model number
    vendor: 'Sergei Koshel', // Vendor of the device (only used for documentation and startup logging)
    description: 'CO2, Temperature and Humidity sensor by Sergei Koshel', // Description of the device, copy from vendor site. (only used for documentation and startup logging)
    fromZigbee: [fz.battery, fz.humidity, fz.temperature, fz.co2], // We will add this later
    toZigbee: [], // Should be empty, unless device can be controlled (e.g. lights, switches).
    exposes: [e.battery(), e.humidity(), e.temperature(), e.co2()]
};

module.exports = definition;
