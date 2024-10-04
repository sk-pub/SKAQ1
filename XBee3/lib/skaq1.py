import xbee
import struct

zdo_device_annce = 0x0013
zdo_active_ep_rsp = 0x8005
zdo_simple_desc_rsp = 0x8004

ep = b'\x01'

genBasic = {
    b'\x00\x00': { 'type': b'\x20', 'value': b'\x01' }, # zclVersion
    b'\x00\x01': { 'type': b'\x20', 'value': b'\x00' }, # appVersion
    b'\x00\x02': { 'type': b'\x20', 'value': b'\x00' }, # stackVersion
    b'\x00\x03': { 'type': b'\x20', 'value': b'\x00' }, # hwVersion
    b'\x00\x04': { 'type': b'\x42', 'value': b'SK' }, # manufacturerName # emulate https://www.zigbee2mqtt.io/devices/TPZRCO2HT-Z3.html
    b'\x00\x05': { 'type': b'\x42', 'value': b'AQ1' }, # modelId
    b'\x00\x06': { 'type': b'\x42', 'value': b'20220102' }, # dateCode
    b'\x00\x07': { 'type': b'\x30', 'value': b'\x03' }, # powerSource 0x04 - DC, 0x03 - Battery
    b'\x40\x00': { 'type': b'\x42', 'value': b'0.0.0.1' } # swBuildId
}

# Types 0x20 - uint8, 0x29 - int16, 0x21 - uint16, 0x39 - single (4 bytes, based on the IEEE 754 standard for binary floating-point arithmetic)
# Temp: 0 - MeasuredValue (int16) = 100 x temp, 1 - MinMeasuredValue (int16), 2 - MaxMeasuredValue (int16), 3 - Tolerance (uint16)
# Humidity: 0 - MeasuredValue (uint16) = 100 x humidity, 1 - MinMeasuredValue (uint16), 2 - MaxMeasuredValue (uint16), 3 - Tolerance (uint16)
# CO2: 0 - MeasuredValue (single), 1 - MinMeasuredValue (single), 2 - MaxMeasuredValue (single)
zha = {
    'temperature': { 'cluster': 0x0402, 'id': b'\x00\x00', 'type': b'\x29' },
    'humidity': { 'cluster': 0x0405, 'id': b'\x00\x00', 'type': b'\x21' },
    'co2': { 'cluster': 0x040D, 'id': b'\x00\x00', 'type': b'\x39' },
    'battery-voltage': { 'cluster': 0x0001, 'id': b'\x00\x20', 'type': b'\x20' },
    'battery-percentage': { 'cluster': 0x0001, 'id': b'\x00\x21', 'type': b'\x20' }
}

def ieee_addr():
    return xbee.atcmd('SL')[::-1] + xbee.atcmd('SH')[::-1]

def nwk_addr():
    return struct.pack('<H', xbee.atcmd('MY'))

def active_ep_rsp(tx):
    status = b'\x00'
    ep_count = b'\x01'
    msg = bytes([tx]) + status + nwk_addr() + ep_count + ep
    #print(msg)
    xbee.transmit(xbee.ADDR_COORDINATOR, msg, source_ep = 00, dest_ep = 00, cluster = zdo_active_ep_rsp)

def simple_desc_rsp(tx):
    status = b'\x00'

    app_profile = b'\x04\x01'
    device_id = b'\x02\x03'
    version = b'\x01'

    input_clusters_list = [ 0, 3, 65535, 0x0402, 0x0405, 0x040D] # Basic, Indentify, ??, Temperature Measurement, Relative  Humidity Measurement, CO2
    input_clusters = b''.join(map(lambda n: struct.pack('<H', n), input_clusters_list))
    input_cluster_count = len(input_clusters_list)

    output_clusters_list = []
    output_clusters = b''.join(map(lambda n: struct.pack('<H', n), output_clusters_list))
    output_cluster_count = len(output_clusters_list)

    desc = ep + app_profile + device_id + version + bytes([input_cluster_count])
    if input_cluster_count > 0:
        desc += input_clusters
    desc += bytes([output_cluster_count])
    if output_cluster_count > 0:
        desc += output_clusters

    desc_length = len(desc)
    msg = bytes([tx]) + status + nwk_addr() + bytes([desc_length]) + desc
    #print(msg)
    xbee.transmit(xbee.ADDR_COORDINATOR, msg, source_ep = 00, dest_ep = 00, cluster = zdo_simple_desc_rsp)

def get_attr_val(attr_id, data_type, data_value):
    if attr_id == b'\x00\x20': # Battery voltage in units of 100 mV
        return struct.pack('<B', round(data_value * 10))

    if attr_id == b'\x00\x21': # Battery percentage as a half integer percentage of the full battery capacity (0x64 = 50%)
        return struct.pack('<B', round(data_value * 2))

    if data_type == b'\x42':
        return bytes([len(data_value)]) + data_value

    if isinstance(data_value, float) and (data_type == b'\x21' or data_type == b'\x29'):
        # Multiply by 100 and convert to int
        return struct.pack('<H', round(data_value * 100))

    if isinstance(data_value, float) and data_type == b'\x39':
        # Pack into 4 bytes IEEE 754 float
        return struct.pack('<I', struct.unpack('!I', struct.pack('!f', data_value * 1e-6 ))[0])

    return data_value

def read_attr_rsp(req):
    seq_num = bytes([req[1]])
    cmd_id = b'\x01' # Read Attributes Response
    status = b'\x00'
    attr_id = bytes([req[4], req[3]])
    attr = genBasic.get(attr_id)
    attr_type = attr.get('type')
    attr_value = attr.get('value')
    
    # [::-1] to reverse byte order
    msg = b'\x18' + seq_num + cmd_id + attr_id[::-1] + status + attr_type + get_attr_val(attr_id, attr_type, attr_value)
    #print(msg)
    xbee.transmit(xbee.ADDR_COORDINATOR, msg, source_ep = 01, dest_ep = 01, cluster = 0000)


attr_report_seq_num = 0x00

def attr_report(attr_name, attr_value):
    # TODO: check "2.5.7 Configure Reporting Command" to configure periodic or change-based reporting (https://zigbeealliance.org/wp-content/uploads/2019/12/07-5123-06-zigbee-cluster-library-specification.pdf)    
    global attr_report_seq_num
    cmd_id = b'\x0A' # Report attributes
    msg = b'\x18' + bytes([attr_report_seq_num]) + cmd_id
    
    zha_attr = zha.get(attr_name)
    cluster = zha_attr.get('cluster')
    attr_id = zha_attr.get('id')
    attr_type = zha_attr.get('type')
    
    # [::-1] to reverse byte order
    msg += attr_id[::-1] + attr_type + get_attr_val(attr_id, attr_type, attr_value)

    #print(msg)
    xbee.transmit(xbee.ADDR_COORDINATOR, msg, source_ep = 01, dest_ep = 01, cluster = cluster)
    attr_report_seq_num += 1
    if attr_report_seq_num > 0xff:
        attr_report_seq_num = 0x00

def rx_callback(req):
    #print('rx_callback:')
    #print(req)
    
    cluster = req.get('cluster')
    payload = req.get('payload')

    if cluster == 0x0005:
        #print('received 0x0005 - respond with active_ep_rsp')
        tx = req.get('payload')[0]
        active_ep_rsp(tx)
    elif cluster == 0x0004:
        #print('received 0x0004 - respond with simple_desc_rsp')
        tx = req.get('payload')[0]
        simple_desc_rsp(tx)
    elif cluster == 0x0000 and payload[2] == 0x00: # 0x00 - read attributes
        #print('received 0x0000 - respond with read_attr_rsp')
        read_attr_rsp(payload)  
  
xbee.receive_callback(rx_callback)
