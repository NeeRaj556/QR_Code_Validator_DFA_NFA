## Quickstart (Windows)

Follow these steps on Windows 10/11 (64-bit):

1) Install Python 3.12 (64‑bit) from python.org
- During install, check "Add Python to PATH".

2) Create and activate a virtual environment (PowerShell)
- In the project folder:
  - `py -3.12 -m venv .venv`
  - `./.venv/Scripts/Activate.ps1`
- If PowerShell blocks activation, run in CMD instead:
  - `./.venv/Scripts/activate.bat`

3) Install dependencies
- Upgrade pip and install packages:
  - `python -m pip install --upgrade pip`
  - `python -m pip install -r requirements.txt`

4) Run the Web QR Image Validator (recommended)
- Start the server:
  - `python -m uvicorn web_app:app --port 8000`
- Open http://127.0.0.1:8000 and use "Quick Test" to scan built-in valid/invalid QR images, or upload your own.
- If port 8000 is busy, use `--port 8001`.

5) (Optional) Run the Desktop GUI app
- The desktop GUI uses Tkinter (bundled with Python) and pyzbar for scanning.
- Install extra dependency:
  - `python -m pip install pyzbar==0.1.9`
- Install ZBar (required by pyzbar):
  - Chocolatey: `choco install zbar`
  - Or download a Windows 64‑bit ZBar build and ensure its DLL (e.g., `libzbar-64.dll`) is on PATH or next to `python.exe`.
- Run the GUI:
  - `python qr_dfa_nfa_validator.py`

### Windows Notes
- Visual C++ Redistributable (x64) may be required for OpenCV. If OpenCV DLL errors appear, install the latest from Microsoft.
- For webcam scanning, ensure camera permissions are granted and no other app is using the camera.
- If `python-multipart` error appears when uploading images in the web app, reinstall deps: `python -m pip install -r requirements.txt`.

## 📚 Complete Documentation

### Your Wi-Fi QR Codes Work Perfectly! ✅

Both of your Wi-Fi QR examples validate successfully:

**Example 1**: `WIFI:T:WPA;S:aakriti62;P:1234567989;;`
- ✅ **ACCEPT** (DFA): Path: q0→q_wifi→q_S→q_T→q_P→q_accept
- ✅ **ACCEPT** (NFA): Path: start→AUTH✔→SSID✔→PASS✔→HIDDEN?→accept
- **Extracted**: auth=WPA, ssid=aakriti62, password=1234567989

**Example 2**: `WIFI:S:TP-LINK_172E;T:WPA;P:36409853;;`
- ✅ **ACCEPT** (DFA): Path: q0→q_wifi→q_S→q_T→q_P→q_accept
- ✅ **ACCEPT** (NFA): Path: start→AUTH✔→SSID✔→PASS✔→HIDDEN?→accept
- **Extracted**: auth=WPA, ssid=TP-LINK_172E, password=36409853

### 📖 For Complete Understanding

See **[DFA_NFA_DOCUMENTATION.md](./DFA_NFA_DOCUMENTATION.md)** for:
- **🧠 Core Concepts**: What DFA and NFA are in simple terms
- **🎯 Detailed Examples**: Step-by-step validation explanations
- **📊 Output Analysis**: Understanding ACCEPT/REJECT results
- **🔧 Troubleshooting**: Common errors and solutions
- **🚀 Use Cases**: When to use DFA vs NFA
- **⚡ Performance**: Speed and complexity comparisons

## DFA and NFA: Concepts and Outputs Explained

This section explains, in plain language, what DFA and NFA are, how this app uses them, and why you see ACCEPT or REJECT for given QR texts.

### What is a DFA?
- Deterministic Finite Automaton (DFA) is a finite set of states with deterministic transitions based on the next input character.
- At any step there is exactly one next state for a given input and current state.
- A DFA accepts a string if, after consuming all characters, it ends in an accept state.
- Pros: predictable, fast, step-by-step reasoning and clear error locations.

### What is an NFA?
- Nondeterministic Finite Automaton (NFA) allows multiple possible next states, including epsilon (empty) transitions.
- Practical use here: we approximate an NFA using regular expressions (regex). Most regex engines compile patterns to a DFA-like matcher.
- Pros: concise rules, easy to change patterns; Cons: less granular error positions by default.

### Two QR Schemas supported
1) Custom Payload (project grammar)
   - <TYPE>:<UUIDv4>:<VERSION>:<YYYYMMDDThhmmZ>:<DATA>
   - TYPE ∈ {ticket, product, auth, invoice}
   - UUIDv4 = 8-4-4-4-12 hex
   - VERSION = x.y.z (digits only)
   - TIMESTAMP = YYYYMMDDThhmmZ
   - DATA = comma-separated key=value pairs (alphanumeric only)
   - Validators: QRPayloadDFA and QRPayloadNFA

2) Wi‑Fi QR (de facto standard)
   - WIFI:T:<WEP|WPA|WPA2|nopass>;S:<ssid>;P:<password>;H:<true|false>;;
   - S is required. P and H are optional. Ends with one or two trailing semicolons.
   - Validators: WiFiDFA and WiFiNFA

---

## How validation works in this app

1) You upload a QR image.
2) The server decodes the image with OpenCV to extract the embedded text.
3) The app auto-detects the schema:
   - If text starts with "WIFI:", it uses the Wi‑Fi validators.
   - Otherwise, it uses the Custom Payload validators.
4) Based on the Mode (DFA or NFA) you select, it runs the corresponding validator and returns:
   - valid: true/false
   - path: the state or step path taken (educational)
   - error/errors: reason(s) if rejected
   - extracted_data: parsed fields when accepted (type/uuid/version/ts/data for custom; auth/ssid/password/hidden for Wi‑Fi)

---

## Why is this output? (Worked examples)

### A) Custom payload – VALID
Example text:
```
ticket:03d7c102-d8c4-44dd-957f-7ae333dfa31c:1.0.0:20250816T1122Z:id=12345,seat=A1
```
- DFA path: [q0, q1, q5, q42, q50, q64, q65, q_accept]
  - q0→q1: TYPE checked; "ticket" is allowed
  - q1→q5: TYPE ended at ':'
  - q5→q42: UUID structure verified (8-4-4-4-12 hex with hyphens)
  - q42→q50: VERSION x.y.z verified (digits only)
  - q50→q64: TIMESTAMP format verified (YYYYMMDDThhmmZ)
  - q64→q65: DATA begins after ':'
  - q65→q_accept: DATA key=value pairs valid and non-empty
- NFA: Regex fully matches; named groups capture the fields; ACCEPT.
- extracted_data shows all fields and parsed key/value pairs.

### B) Custom payload – INVALID TYPE
Example text:
```
invalid:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:1.0.0:20240101T1200Z:id=12345
```
- DFA path: [q0, q1, q_reject]
  - TYPE is not one of ticket|product|auth|invoice → REJECT, error: "Invalid TYPE: invalid".
- NFA: Regex fails TYPE alternative → REJECT, errors: ["Invalid TYPE: invalid"].

### C) Wi‑Fi QR – VALID
Example text:
```
WIFI:T:WPA;S:aakriti62;P:1234567989;;
```
- Detected schema: wifi
- DFA-like steps: [q0, q_wifi, q_t, q_s, q_p, q_accept]
  - WIFI: prefix present
  - T:WPA; is valid auth
  - S:aakriti62; is non-empty SSID
  - P:1234567989; password provided (optional but allowed)
  - Trailing ';' satisfied
- NFA: Regex matches; groups: auth=WPA, ssid=aakriti62, password=1234567989, hidden=None → ACCEPT.

### D) Wi‑Fi QR – INVALID (missing SSID)
```
WIFI:T:WPA;P:secret;;
```
- DFA: Missing S:…; segment → REJECT with error "Missing S: (SSID)".
- NFA: Regex fails because S: group is required → REJECT.

---

## API Reference

- POST /api/scan
  - multipart/form-data
    - file: image (PNG/JPG)
    - mode: DFA | NFA
  - Response JSON
    - count: number of QR texts decoded from image
    - mode: DFA or NFA
    - items: array of results
      - schema: "custom" | "wifi"
      - text: decoded string
      - valid: boolean
      - path: array of steps/states
      - error or errors: message(s) when invalid
      - extracted_data: parsed fields when valid

- GET /api/example?kind=valid|invalid
  - Returns a PNG image embedding an example custom payload (valid or invalid) for quick testing.

---

## Use cases
- Ticketing: Event/transport tickets encoded as typed payloads.
- Inventory & products: Label QR with SKU and versioning.
- Auth links/tokens: Short, structured payloads to bootstrap sessions.
- Invoices: Compact, scannable invoice metadata.
- Wi‑Fi sharing: Guest network codes in WIFI:… format.

## When to prefer DFA vs NFA (regex)
- DFA
  - You need step-by-step traces, precise field-by-field error messages, and deterministic flows.
  - Educational settings to show state transitions and acceptance.
- NFA/Regex
  - You want compact rules, fast iteration, and easy maintenance of complex patterns.
  - You don’t need character-level error positions.

## Extending the validator
- Add new schemas by:
  - Detecting a distinct prefix (e.g., URL:, MAILTO:, WIFI:)
  - Writing a small DFA validator (state steps) and a regex validator
  - Routing in /api/scan based on the prefix and returning schema in results

## Troubleshooting outputs
- REJECT with "Invalid TYPE" (custom): TYPE not in allowed set.
- REJECT with "Invalid UUID": wrong length/sections/characters.
- REJECT with "Invalid VERSION": not x.y.z with digits only.
- REJECT with timestamp errors: wrong format or impossible date/time.
- REJECT with data errors: missing '=' or non-alphanumeric key/value.
- Wi‑Fi errors like "Missing S:" or "Invalid auth type": the required segment is absent or value is outside allowed options.

---

## Sample cURL session
Generate example images and scan them (server must be running):
```bash
# Valid example (custom payload)
curl -s -o valid.png "http://127.0.0.1:8000/api/example?kind=valid"
curl -s -F file=@valid.png -F mode=DFA http://127.0.0.1:8000/api/scan | jq .

# Invalid example (custom payload)
curl -s -o invalid.png "http://127.0.0.1:8000/api/example?kind=invalid"
curl -s -F file=@invalid.png -F mode=NFA http://127.0.0.1:8000/api/scan | jq .
```
Interpretation:
- valid=true ⇒ ACCEPT; check path and extracted_data.
- valid=false ⇒ REJECT; check error/errors to see which rule failed and why.

---

## Learning summary
- DFA gives a controllable, inspectable pipeline: each character advances a state; acceptance means all constraints satisfied.
- NFA/Regex provides a compact specification: one pattern encodes the whole grammar; a match means the text satisfies all sub-patterns.
- Seeing both for the same QR text helps understand formal language recognition vs. practical pattern matching.
