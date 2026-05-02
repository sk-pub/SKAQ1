import xbee
import struct

def _tx(msg, source_ep, dest_ep, cluster, label, seq):
    try:
        xbee.transmit(xbee.ADDR_COORDINATOR, msg, source_ep=source_ep, dest_ep=dest_ep, cluster=cluster)
    except Exception as e:
        print('tx FAIL {} cluster=0x{:04x} seq=0x{:02x} err={}'.format(label, cluster, seq, e))

zdo_device_annce = 0x0013
zdo_active_ep_rsp = 0x8005
zdo_simple_desc_rsp = 0x8004

ep = b'\x01'

genBasic = {
    b'\x00\x00': { 'type': b'\x20', 'value': b'\x01' }, # zclVersion
    b'\x00\x01': { 'type': b'\x20', 'value': b'\x01' }, # appVersion
    b'\x00\x02': { 'type': b'\x20', 'value': b'\x00' }, # stackVersion
    b'\x00\x03': { 'type': b'\x20', 'value': b'\x01' }, # hwVersion
    b'\x00\x04': { 'type': b'\x42', 'value': b'SK' }, # manufacturerName # emulate https://www.zigbee2mqtt.io/devices/TPZRCO2HT-Z3.html
    b'\x00\x05': { 'type': b'\x42', 'value': b'SKAQ1' }, # modelId
    b'\x00\x06': { 'type': b'\x42', 'value': b'20250302' }, # dateCode
    b'\x00\x07': { 'type': b'\x30', 'value': b'\x04' }, # powerSource 0x04 - DC, 0x03 - Battery
    b'\x40\x00': { 'type': b'\x42', 'value': b'0.0.0.2' } # swBuildId
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
    'battery-percentage': { 'cluster': 0x0001, 'id': b'\x00\x21', 'type': b'\x20' },
    'pm1': { 'cluster': 0xfc01, 'id': b'\x00\x00', 'type': b'\x39' },
    'pm25': { 'cluster': 0x042A, 'id': b'\x00\x00', 'type': b'\x39' },
    'pm40': { 'cluster': 0xfc01, 'id': b'\x00\x01', 'type': b'\x39' },
    'pm10': { 'cluster': 0xfc01, 'id': b'\x00\x02', 'type': b'\x39' },
    'voc': { 'cluster': 0xfc01, 'id': b'\x00\x03', 'type': b'\x39' },
    'nox': { 'cluster': 0xfc01, 'id': b'\x00\x04', 'type': b'\x39' },
    't2': { 'cluster': 0xfc01, 'id': b'\x00\x05', 'type': b'\x29' },
    'ref_temp': { 'cluster': 0xfc01, 'id': b'\x00\x06', 'type': b'\x29' }
}

def ieee_addr():
    return xbee.atcmd('SL')[::-1] + xbee.atcmd('SH')[::-1]

def nwk_addr():
    return struct.pack('<H', xbee.atcmd('MY'))

def active_ep_rsp(tx):
    status = b'\x00'
    ep_count = b'\x01'
    msg = bytes([tx]) + status + nwk_addr() + ep_count + ep
    _tx(msg, 0, 0, zdo_active_ep_rsp, 'active_ep_rsp', tx)

def simple_desc_rsp(tx):
    status = b'\x00'

    app_profile = b'\x04\x01'
    device_id = b'\x02\x03'
    version = b'\x01'

    input_clusters_list = [ 0, 3, 65535, 0x0402, 0x0405, 0x040D, 0xfc01, 0x042A] # Basic, Indentify, ??, Temperature Measurement, Relative  Humidity Measurement, CO2
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
    _tx(msg, 0, 0, zdo_simple_desc_rsp, 'simple_desc_rsp', tx)

def get_attr_val(attr_id, data_type, data_value):
    if attr_id == b'\x00\x20': # Battery voltage in units of 100 mV
        return struct.pack('<B', round(data_value * 10))

    if attr_id == b'\x00\x21': # Battery percentage as a half integer percentage of the full battery capacity (0x64 = 50%)
        return struct.pack('<B', round(data_value * 2))

    if data_type == b'\x42':
        return bytes([len(data_value)]) + data_value

    # Caller is expected to pass values already in the ZCL on-wire unit.
    # This function only handles byte encoding per ZCL data type.
    if isinstance(data_value, float) and data_type == b'\x21':
        return struct.pack('<H', int(round(data_value)))

    if isinstance(data_value, float) and data_type == b'\x29':
        return struct.pack('<h', int(round(data_value)))

    if isinstance(data_value, float) and data_type == b'\x39':
        return struct.pack('<I', struct.unpack('!I', struct.pack('!f', data_value))[0])

    return data_value

# Cache of last reported measurement values keyed by (cluster, attr_id_BE_bytes) -> (type, value)
last_values = {}

def read_attr_rsp(cluster, req):
    seq_num = bytes([req[1]])
    cmd_id = b'\x01' # Read Attributes Response
    msg = b'\x18' + seq_num + cmd_id

    # Request payload after cmd byte is a list of 2-byte LE attribute IDs
    for i in range(3, len(req) - 1, 2):
        attr_id_le = bytes([req[i], req[i + 1]])
        attr_id_be = bytes([req[i + 1], req[i]])

        attr_type = None
        attr_value = None

        if cluster == 0x0000:
            attr = genBasic.get(attr_id_be)
            if attr is not None:
                attr_type = attr.get('type')
                attr_value = attr.get('value')
        else:
            cached = last_values.get((cluster, attr_id_be))
            if cached is not None:
                attr_type, attr_value = cached

        if attr_type is not None:
            msg += attr_id_le + b'\x00' + attr_type + get_attr_val(attr_id_be, attr_type, attr_value)
        else:
            msg += attr_id_le + b'\x86' # UNSUPPORTED_ATTRIBUTE

    _tx(msg, 1, 1, cluster, 'read_attr_rsp', req[1])

_write_attr_cb = None

def register_write_attr_callback(cb):
    global _write_attr_cb
    _write_attr_cb = cb

def write_attrs_rsp(cluster, req):
    seq_num = bytes([req[1]])
    cmd_id = b'\x04' # Write Attributes Response

    statuses = []
    i = 3
    while i + 3 <= len(req):
        attr_id_le = bytes([req[i], req[i + 1]])
        attr_id_be = bytes([req[i + 1], req[i]])
        data_type = req[i + 2]
        i += 3

        if data_type != 0x29: # only int16 supported for now
            statuses.append((attr_id_le, 0x8d)) # INVALID_DATA_TYPE
            break
        if i + 2 > len(req):
            statuses.append((attr_id_le, 0x80)) # MALFORMED_COMMAND
            break
        raw = bytes(req[i:i + 2])
        i += 2

        status = 0x86 # UNSUPPORTED_ATTRIBUTE
        if _write_attr_cb is not None:
            try:
                if _write_attr_cb(cluster, attr_id_be, data_type, raw):
                    status = 0x00
            except Exception as e:
                print('write cb err: {}'.format(e))
                status = 0x01 # FAILURE
        statuses.append((attr_id_le, status))

    msg = b'\x18' + seq_num + cmd_id
    if statuses and all(s == 0x00 for _, s in statuses):
        msg += b'\x00'
    else:
        for attr_id_le, s in statuses:
            msg += bytes([s]) + attr_id_le
    _tx(msg, 1, 1, cluster, 'write_attrs_rsp', req[1])

def configure_reporting_rsp(cluster, req):
    # ZCL 2.5.8 - single status byte means success for all attribute records
    seq_num = bytes([req[1]])
    cmd_id = b'\x07' # Configure Reporting Response
    status = b'\x00' # SUCCESS
    msg = b'\x18' + seq_num + cmd_id + status
    _tx(msg, 1, 1, cluster, 'configure_reporting_rsp', req[1])


attr_report_seq_num = 0x00

def attr_report_batch(items):
    # items: iterable of (attr_name, value). Groups by cluster and sends one
    # ZCL Report Attributes frame per cluster.
    global attr_report_seq_num

    by_cluster = {}
    for name, val in items:
        zha_attr = zha.get(name)
        cluster = zha_attr.get('cluster')
        attr_id = zha_attr.get('id')
        attr_type = zha_attr.get('type')
        last_values[(cluster, attr_id)] = (attr_type, val)
        by_cluster.setdefault(cluster, []).append((name, val, attr_id, attr_type))

    for cluster, records in by_cluster.items():
        seq = attr_report_seq_num
        msg = b'\x18' + bytes([seq]) + b'\x0A' # frame control + seq + Report Attributes cmd
        names = []
        for name, val, attr_id, attr_type in records:
            msg += attr_id[::-1] + attr_type + get_attr_val(attr_id, attr_type, val)
            names.append(name)
        _tx(msg, 1, 1, cluster, 'report[' + ','.join(names) + ']', seq)
        attr_report_seq_num = (attr_report_seq_num + 1) & 0xff

def attr_report(attr_name, attr_value):
    attr_report_batch([(attr_name, attr_value)])

def rx_callback(req):
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
    elif req.get('dest_ep') == 1 and (payload[0] & 0x03) == 0x00 and payload[2] == 0x00: # ZCL general Read Attributes on any cluster
        read_attr_rsp(cluster, payload)
    elif req.get('dest_ep') == 1 and (payload[0] & 0x03) == 0x00 and payload[2] == 0x02: # ZCL general Write Attributes on any cluster
        write_attrs_rsp(cluster, payload)
    elif req.get('dest_ep') == 1 and (payload[0] & 0x03) == 0x00 and payload[2] == 0x06: # ZCL general Configure Reporting on any cluster
        configure_reporting_rsp(cluster, payload)
    elif cluster == 0x8001 or cluster == 0x8002: # ZDO IEEE_addr_rsp / Node_Desc_rsp - no response needed
        pass
    else:
        print('rx unknown cluster=0x{:04x} payload={}'.format(cluster, bytes(payload)))
  
xbee.receive_callback(rx_callback)
