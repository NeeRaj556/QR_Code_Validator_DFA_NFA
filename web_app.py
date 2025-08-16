

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
import re, uuid, datetime, base64, os, tempfile, subprocess

# Backend
app = FastAPI(title="QR Image Validator (DFA vs NFA)")
 
class QRPayloadDFA:
    def validate(self, payload: str):
        path = ['q0']
        parts = payload.split(':')
        if len(parts) != 5:
            return {'valid': False, 'path': path + ['q_reject'], 'error': f"Expected 5 parts, got {len(parts)}"}
        
        type_part, uuid_part, version_part, ts_part, data_part = parts
        path.append('q1')
        
        if type_part not in ['ticket', 'product', 'auth', 'invoice']:
            return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid TYPE: {type_part}'}
        
        path.append('q5')
        uuid_sections = uuid_part.split('-')
        if len(uuid_sections) != 5 or [len(s) for s in uuid_sections] != [8,4,4,4,12]:
            return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid UUID: {uuid_part}'}
        
        path.append('q42')
        v_parts = version_part.split('.')
        if len(v_parts) != 3 or not all(p.isdigit() for p in v_parts):
            return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid VERSION: {version_part}'}
        
        path.append('q50')
        if len(ts_part) != 14 or ts_part[8] != 'T' or ts_part[-1] != 'Z':
            return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid TIMESTAMP: {ts_part}'}
        
        path.append('q64')
        if not data_part or '=' not in data_part:
            return {'valid': False, 'path': path + ['q_reject'], 'error': 'Invalid DATA'}
        
        pairs = data_part.split(',')
        parsed_data = {}
        for pair in pairs:
            if '=' not in pair:
                return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid pair: {pair}'}
            k, v = pair.split('=', 1)
            parsed_data[k] = v
        
        return {
            'valid': True, 'path': path + ['q65', 'q_accept'],
            'extracted_data': {'type': type_part, 'uuid': uuid_part, 'version': version_part, 'timestamp': ts_part, 'data': data_part, 'parsed_data': parsed_data}
        }

class QRPayloadNFA:
    def __init__(self):
        self.pattern = r'^(ticket|product|auth|invoice):([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}):(\d+\.\d+\.\d+):(\d{8}T\d{4}Z):([A-Za-z0-9]+=[A-Za-z0-9]+(?:,[A-Za-z0-9]+=[A-Za-z0-9]+)*)$'
        self.regex = re.compile(self.pattern)

    def validate(self, payload: str):
        m = self.regex.match(payload)
        if not m:
            return {'valid': False, 'path': ['start', 'reject'], 'errors': ['Pattern mismatch']}
        return {
            'valid': True, 'path': ['start', 'TYPE✔', 'UUID✔', 'VERSION✔', 'TIMESTAMP✔', 'DATA✔', 'accept'],
            'extracted_data': {'type': m.group(1), 'uuid': m.group(2), 'version': m.group(3), 'timestamp': m.group(4), 'data': m.group(5)}
        }

class WiFiDFA:
    def validate(self, text: str):
        path = ['q0']
        if not text.startswith('WIFI:'):
            return {'valid': False, 'path': path + ['q_reject'], 'error': 'Missing WIFI: prefix'}
        
        path.append('q_wifi')
        fields = {}
        for seg in text[5:].split(';'):
            if seg and ':' in seg:
                k, v = seg.split(':', 1)
                fields[k] = v
        
        if 'S' not in fields or not fields['S']:
            return {'valid': False, 'path': path + ['q_reject'], 'error': 'Missing SSID'}
        path.append('q_S')
        
        auth = fields.get('T', 'nopass')
        if auth not in {'WEP', 'WPA', 'WPA2', 'WPA3', 'nopass'}:
            return {'valid': False, 'path': path + ['q_reject'], 'error': f'Invalid auth: {auth}'}
        path.append('q_T')
        
        if auth != 'nopass' and not fields.get('P'):
            return {'valid': False, 'path': path + ['q_reject'], 'error': 'Password required'}
        path.append('q_P')
        
        hidden = None
        if 'H' in fields:
            if fields['H'] not in ('true', 'false'):
                return {'valid': False, 'path': path + ['q_reject'], 'error': 'Invalid H value'}
            hidden = (fields['H'] == 'true')
            path.append('q_H')
        
        return {
            'valid': True, 'path': path + ['q_accept'],
            'extracted_data': {'schema': 'wifi', 'auth': auth, 'ssid': fields['S'], 'password': fields.get('P'), 'hidden': hidden}
        }

class WiFiNFA:
    def __init__(self):
        self.token_pat = re.compile(r'([A-Za-z]):([^;]*);')

    def validate(self, text: str):
        if not text.startswith('WIFI:'):
            return {'valid': False, 'errors': ['Missing WIFI: prefix'], 'path': ['start','reject']}
        
        fields = {m.group(1): m.group(2) for m in self.token_pat.finditer(text[5:])}
        
        if 'S' not in fields or not fields['S']:
            return {'valid': False, 'errors': ['Missing SSID'], 'path': ['start','reject']}
        
        auth = fields.get('T', 'nopass')
        if auth not in {'WEP', 'WPA', 'WPA2', 'WPA3', 'nopass'}:
            return {'valid': False, 'errors': ['Invalid auth'], 'path': ['start','reject']}
        
        if auth != 'nopass' and not fields.get('P'):
            return {'valid': False, 'errors': ['Password required'], 'path': ['start','reject']}
        
        hidden = None
        if 'H' in fields:
            if fields['H'] not in ('true', 'false'):
                return {'valid': False, 'errors': ['Invalid H value'], 'path': ['start','reject']}
            hidden = (fields['H'] == 'true')
        
        return {
            'valid': True, 'path': ['start','AUTH✔','SSID✔','PASS✔','accept'],
            'extracted_data': {'schema': 'wifi', 'auth': auth, 'ssid': fields['S'], 'password': fields.get('P'), 'hidden': hidden}
        }
def _decode_qr_from_bytes(data: bytes):
    try:
        import numpy as np, cv2
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None: return [], None
        detector = cv2.QRCodeDetector()
        retval, decoded_info, _, _ = detector.detectAndDecodeMulti(img)
        return [t for t in (decoded_info or []) if t] or [], None
    except: return None, 'Missing opencv-python/numpy'
 
def _generate_qr_png(text: str) -> bytes:
    try:
        import qrcode, io
        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except: raise RuntimeError('Missing qrcode[pil]')

def _valid_payload() -> str:
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%MZ')
    return f"ticket:{uuid.uuid4()}:1.0.0:{ts}:id=12345,seat=A1"

def _invalid_payload() -> str:
    return "invalid:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:1.0.0:20240101T1200Z:id=12345"

def _generate_dfa_diagram(path: list, schema: str, is_valid: bool) -> str:
    if schema == 'wifi':
        states = "q0 [label=\"START\"] q_wifi [label=\"WIFI:\"] q_S [label=\"SSID✓\"] q_T [label=\"AUTH✓\"] q_P [label=\"PASS✓\"] q_H [label=\"HIDDEN✓\"] q_accept [label=\"ACCEPT\", shape=doublecircle, fillcolor=green] q_reject [label=\"REJECT\", shape=doublecircle, fillcolor=red]"
    else:
        states = "q0 [label=\"START\"] q1 [label=\"TYPE\"] q5 [label=\"UUID\"] q42 [label=\"VERSION\"] q50 [label=\"TIMESTAMP\"] q64 [label=\"DATA\"] q65 [label=\"PROCESS\"] q_accept [label=\"ACCEPT\", shape=doublecircle, fillcolor=green] q_reject [label=\"REJECT\", shape=doublecircle, fillcolor=red]"
    
    dot = f"digraph DFA {{ rankdir=LR; node [shape=circle, style=filled, fillcolor=lightblue]; {states};"
    for i in range(len(path) - 1):
        color = "red" if path[i+1] == "q_reject" else "blue"
        dot += f' {path[i]} -> {path[i+1]} [color={color}, penwidth=3];'
    return dot + " }"

def _generate_nfa_diagram(path: list, schema: str, is_valid: bool) -> str:
    dot = "digraph NFA { rankdir=LR; node [shape=rectangle, style=filled, fillcolor=lightgreen];"
    for i in range(len(path) - 1):
        color = "red" if "reject" in path[i+1].lower() else "blue"
        dot += f' "{path[i]}" -> "{path[i+1]}" [color={color}, penwidth=3];'
    return dot + " }"

def _render_graphviz_to_base64(dot_content: str) -> str:
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
            f.write(dot_content)
            dot_file = f.name
        png_file = dot_file.replace('.dot', '.png')
        result = subprocess.run(['dot', '-Tpng', dot_file, '-o', png_file], capture_output=True)
        if result.returncode == 0:
            with open(png_file, 'rb') as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        return None
    except: return None
    finally:
        for f in [dot_file, png_file]:
            try: os.unlink(f)
            except: pass

# Instances
DFA, NFA, WIFI_DFA, WIFI_NFA = QRPayloadDFA(), QRPayloadNFA(), WiFiDFA(), WiFiNFA()

@app.get('/', response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=INDEX_HTML)

@app.post('/api/scan')
async def api_scan(file: UploadFile = File(...), mode: str = Form('DFA')):
    data = await file.read()
    texts, err = _decode_qr_from_bytes(data)
    if texts is None:
        return JSONResponse({'error': err}, status_code=500)
    
    results = []
    chosen = (mode or 'DFA').upper()
    for t in texts:
        schema = 'wifi' if t.startswith('WIFI:') else 'custom'
        validator = (WIFI_DFA if schema == 'wifi' else DFA) if chosen == 'DFA' else (WIFI_NFA if schema == 'wifi' else NFA)
        res = validator.validate(t)
        
        if 'path' in res and res['path']:
            dot_content = _generate_dfa_diagram(res['path'], schema, res['valid']) if chosen == 'DFA' else _generate_nfa_diagram(res['path'], schema, res['valid'])
            diagram_base64 = _render_graphviz_to_base64(dot_content)
            if diagram_base64:
                res['diagram'] = diagram_base64
        
        results.append({'schema': schema, 'text': t, **res})
    return {'count': len(texts), 'mode': chosen, 'items': results}

@app.get('/api/example')
async def api_example(kind: str = 'valid'):
    text = _valid_payload() if kind.lower() == 'valid' else _invalid_payload()
    return Response(content=_generate_qr_png(text), media_type='image/png')

@app.get('/healthz')
async def health():
    return {'ok': True}
 

#  Frontend 
INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>QR Validator (DFA vs NFA)</title>
<style>body{font-family:Arial,sans-serif;margin:20px}.card{border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}label{display:block;margin:6px 0 4px;font-weight:600}input[type=file],select{width:100%;padding:8px}.row{display:flex;gap:12px;flex-wrap:wrap}.row>div{flex:1 1 240px}.btn{padding:8px 12px;border:1px solid #999;background:#f7f7f7;border-radius:6px;cursor:pointer}.btn.primary{background:#0d6efd;color:#fff;border-color:#0d6efd}.ok{color:green}.bad{color:#b00020}pre{background:#f7f7f7;padding:8px;border-radius:6px}.diagram-container{text-align:center;margin:15px 0}.diagram-img{max-width:100%;height:auto;border:1px solid #ddd;border-radius:6px;background:white}.path-visualization{background:#f0f8ff;padding:10px;border-radius:6px;margin:10px 0}</style></head>
<body><h1>QR Image Validator</h1><p>Upload QR image; validates via <b>DFA</b> or <b>NFA</b>. Supports custom payloads and Wi‑Fi QR.</p>
<div class="card"><h2>Scan QR Image</h2><div class="row"><div><label>Mode</label><select id="mode"><option>DFA</option><option>NFA</option></select></div><div style="align-self:end;"><input id="qrimg" type="file" accept="image/*"></div></div><div style="margin-top:10px;"><button class="btn primary" onclick="scanImage()">Scan & Validate</button></div><div id="scanOut"></div></div>
<div class="card"><h2>Quick Test</h2><p>Use built-in example QR images:</p><button class="btn" onclick="scanExample('valid')">Scan Example (Valid)</button><button class="btn" onclick="scanExample('invalid')">Scan Example (Invalid)</button><div id="exStatus" style="margin-top:10px;"></div></div>
<script>
async function scanImage(){const f=document.getElementById('qrimg').files[0];if(!f){alert('Choose an image');return}const mode=document.getElementById('mode').value;const fd=new FormData();fd.append('file',f);fd.append('mode',mode);const res=await fetch('/api/scan',{method:'POST',body:fd});const j=await res.json();renderScanResult(j)}
async function scanExample(kind){const mode=document.getElementById('mode').value;const imgRes=await fetch('/api/example?kind='+encodeURIComponent(kind));const blob=await imgRes.blob();const fd=new FormData();fd.append('file',new File([blob],'example.png',{type:'image/png'}));fd.append('mode',mode);const res=await fetch('/api/scan',{method:'POST',body:fd});const j=await res.json();renderScanResult(j)}
function renderScanResult(j){const out=document.getElementById('scanOut');out.innerHTML='';if(j.error){out.textContent=j.error;return}if(!j.items||j.items.length===0){out.textContent='No QR codes found.';return}j.items.forEach((it,idx)=>{const card=document.createElement('div');card.style.border='1px solid #ddd';card.style.borderRadius='6px';card.style.padding='8px';card.style.margin='8px 0';const title=document.createElement('div');title.innerHTML=`<b>QR ${idx+1}</b> [${it.schema}] - ${it.valid?'<span class=ok>ACCEPT</span>':'<span class=bad>REJECT</span>'}`;const pre=document.createElement('pre');pre.textContent=it.text||'';card.appendChild(title);card.appendChild(pre);if(it.diagram){const diagramContainer=document.createElement('div');diagramContainer.className='diagram-container';const diagramImg=document.createElement('img');diagramImg.className='diagram-img';diagramImg.src=it.diagram;diagramImg.alt=`${j.mode} validation path`;diagramContainer.appendChild(diagramImg);card.appendChild(diagramContainer)}if(it.path){const pathDiv=document.createElement('div');pathDiv.className='path-visualization';pathDiv.innerHTML='<b>Path:</b> '+it.path.join(' → ');card.appendChild(pathDiv)}if(it.error){const p=document.createElement('p');p.innerHTML='<b>Error:</b> '+it.error;card.appendChild(p)}if(it.errors){const ul=document.createElement('ul');it.errors.forEach(e=>{const li=document.createElement('li');li.textContent=e;ul.appendChild(li)});card.appendChild(ul)}if(it.extracted_data){const pre2=document.createElement('pre');pre2.textContent=JSON.stringify(it.extracted_data,null,2);card.appendChild(pre2)}out.appendChild(card)})}
</script></body></html>"""

