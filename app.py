from flask import Flask, render_template, request, redirect, url_for, flash
from pysnmp.hlapi import *
import time

app = Flask(__name__)
app.secret_key = 'secret_key' 

# กำหนด IP ของอุปกรณ์
SNMP_HOSTS = {
    'R1': '192.168.84.10',
    'R2': '192.168.84.11',
    'SW1': '192.168.84.12',
    'SW2': '192.168.84.13'
}

SNMP_COMMUNITY = 'private'
SNMP_PORT = 161

# OID สำหรับ Interface Status
OID_IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'  # ifOperStatus
OID_IF_ADMIN_STATUS = '1.3.6.1.2.1.2.2.1.7'  # ifAdminStatus

def get_port_status(host, port_index):
    """อ่านสถานะ Port จาก SNMP โดยใช้ OID"""
    try:
        oid = f'{OID_IF_OPER_STATUS}.{port_index}'
        
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((host, SNMP_PORT), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(f"Error: {errorIndication}")
            return 'unknown'
        
        if errorStatus:
            print(f"Error: {errorStatus.prettyPrint()}")
            return 'unknown'
        
        for varBind in varBinds:
            status = int(varBind[1])
            return 'up' if status == 1 else 'down'
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return 'unknown'

def set_port_status(host, port_index, status):
    """เปลี่ยนสถานะ Port ผ่าน SNMP โดยใช้ OID"""
    try:
        oid = f'{OID_IF_ADMIN_STATUS}.{port_index}'
        admin_status = 1 if status == 'up' else 2
        
        print(f"🔧 Trying to set {host} Port {port_index} to {status} (value={admin_status})")
        print(f"   OID: {oid}")
        print(f"   Community: {SNMP_COMMUNITY}")
        
        iterator = setCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((host, SNMP_PORT), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid), Integer(admin_status))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(f"❌ Error Indication: {errorIndication}")
            return False
        
        if errorStatus:
            error_msg = errorStatus.prettyPrint()
            print(f"❌ Error Status: {error_msg}")
            if 'noAccess' in error_msg or 'notWritable' in error_msg:
                print(f"   ⚠️  SNMP Community '{SNMP_COMMUNITY}' ไม่มีสิทธิ์ Write!")
                print(f"   💡 แก้ไข: ตั้งค่า Community เป็น RW ในอุปกรณ์")
            return False
        
        print(f"✅ Success! Port {port_index} changed to {status}")
        time.sleep(0.5)
        return True
        
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def get_all_ports():
    """ดึงสถานะ Port ทั้งหมด"""
    result = {
        'routers': {},
        'switches': {}
    }
    
    # อ่านสถานะ Router
    for router in ['R1', 'R2']:
        ports = []
        for port_id in range(1, 5):
            status = get_port_status(SNMP_HOSTS[router], port_id)
            connected = 'Net' if port_id == 1 else None
            ports.append({
                'id': port_id,
                'status': status,
                'connected': connected
            })
        result['routers'][router] = {
            'ip': SNMP_HOSTS[router],
            'ports': ports
        }
    
    # อ่านสถานะ Switch
    for switch in ['SW1', 'SW2']:
        ports = []
        for port_id in range(1, 5):
            status = get_port_status(SNMP_HOSTS[switch], port_id)
            connected = 'Net' if port_id == 1 else None
            ports.append({
                'id': port_id,
                'status': status,
                'connected': connected
            })
        result['switches'][switch] = {
            'ip': SNMP_HOSTS[switch],
            'ports': ports
        }
    
    return result

@app.route('/')
def index():
    """หน้าแรก"""
    ports_data = get_all_ports()
    return render_template('index.html', data=ports_data)

@app.route('/toggle', methods=['POST'])
def toggle_port():
    """สลับสถานะ Port"""
    device = request.form.get('device')
    port_id = int(request.form.get('port_id'))
    
    if device not in SNMP_HOSTS:
        flash('ไม่พบอุปกรณ์', 'error')
        return redirect(url_for('index'))
    
    # อ่านสถานะปัจจุบัน
    current_status = get_port_status(SNMP_HOSTS[device], port_id)
    
    if current_status == 'unknown':
        flash(f'ไม่สามารถอ่านสถานะ {device} Port {port_id}', 'error')
        return redirect(url_for('index'))
    
    # สลับสถานะ
    new_status = 'down' if current_status == 'up' else 'up'
    
    # เปลี่ยนสถานะ
    success = set_port_status(SNMP_HOSTS[device], port_id, new_status)
    
    if success:
        flash(f'{device} Port {port_id} เปลี่ยนเป็น {new_status.upper()} แล้ว', 'success')
    else:
        flash(f'ไม่สามารถเปลี่ยนสถานะ {device} Port {port_id}', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("Starting SNMP Port Management Server...")
    print("Available devices:")
    for device, ip in SNMP_HOSTS.items():
        print(f"  {device}: {ip}")
    print("\n✅ Fixed: Using OID instead of IF-MIB")
    print("Server running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)