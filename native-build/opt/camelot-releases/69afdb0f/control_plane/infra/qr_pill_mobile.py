# SPDX-License-Identifier: MIT

"""
QR Pill Mobile Activation — Web interface for mobile device QR scanning.

Flow:
  1. User receives QR code link via SMS/email
  2. Mobile browser opens activation page
  3. Browser requests camera permission
  4. User points camera at QR code (or uploaded image)
  5. QR decoded → pill_id extracted
  6. Activation request sent to CAMELOT-OS backend
  7. Bifrost returns activation status
  8. Mobile displays activation result

Technologies:
  - jsQR: Lightweight QR decoder (no external API)
  - HTML5 <video> API: Camera access
  - HTTP POST: Send activation to backend
  - WebSocket: Real-time status updates
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class MobileActivationSession:
    """Mobile QR Pill activation session."""
    session_id: str
    pill_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    user_agent: str = ""
    ip_address: str = ""
    qr_scanned: bool = False
    scanned_at: Optional[datetime] = None
    activation_requested: bool = False
    activation_status: str = "pending"  # pending, in_progress, approved, completed, failed
    status_message: str = ""


class MobileQRPillActivation:
    """Mobile web interface for QR Pill activation."""

    def __init__(self):
        """Initialize mobile activation handler."""
        self.active_sessions: dict[str, MobileActivationSession] = {}

    def generate_activation_link(self, pill_id: str) -> str:
        """Generate mobile activation link with pill_id."""
        session_id = secrets.token_urlsafe(16)
        session = MobileActivationSession(
            session_id=session_id,
            pill_id=pill_id,
        )
        self.active_sessions[session_id] = session
        return f"https://camelot-os.local/qr-pill/activate/{session_id}"

    def generate_html_page(self, session_id: str) -> str:
        """Generate HTML page for mobile QR scanning."""
        session = self.active_sessions.get(session_id)
        if not session:
            return "<h1>Invalid session</h1>"

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QR Pill Activation</title>
    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 30px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 8px;
        }}
        .header p {{
            color: #666;
            font-size: 14px;
        }}
        .section {{
            margin-bottom: 24px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}
        #video {{
            width: 100%;
            border-radius: 12px;
            background: #000;
            margin-bottom: 12px;
            display: none;
        }}
        #canvas {{
            display: none;
        }}
        .camera-permissions {{
            background: #f5f5f5;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 12px;
        }}
        .button-group {{
            display: flex;
            gap: 10px;
            flex-direction: column;
        }}
        button {{
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        .btn-primary:hover {{
            background: #5568d3;
            transform: translateY(-2px);
        }}
        .btn-secondary {{
            background: #f0f0f0;
            color: #333;
        }}
        .btn-secondary:hover {{
            background: #e0e0e0;
        }}
        .status {{
            padding: 12px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 12px;
            display: none;
        }}
        .status.info {{
            background: #e3f2fd;
            color: #1976d2;
            border: 1px solid #90caf9;
        }}
        .status.success {{
            background: #e8f5e9;
            color: #388e3c;
            border: 1px solid #81c784;
        }}
        .status.error {{
            background: #ffebee;
            color: #d32f2f;
            border: 1px solid #ef5350;
        }}
        .qr-result {{
            background: #f9f9f9;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            display: none;
        }}
        .qr-result h3 {{
            color: #667eea;
            margin-bottom: 8px;
            font-size: 16px;
        }}
        .qr-result p {{
            color: #666;
            font-size: 13px;
            font-family: monospace;
            word-break: break-all;
        }}
        .upload-area {{
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #fafafa;
        }}
        .upload-area:hover {{
            border-color: #667eea;
            background: #f0f4ff;
        }}
        .upload-area.dragover {{
            border-color: #667eea;
            background: #f0f4ff;
        }}
        #fileInput {{
            display: none;
        }}
        .spinner {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍊 QR Pill Activation</h1>
            <p>Scan QR code to activate CAMELOT-OS pill</p>
        </div>

        <div class="status" id="statusAlert"></div>

        <div class="section">
            <div class="section-title">📱 Option 1: Camera Scan</div>
            <div class="camera-permissions" id="cameraPermission">
                Click "Start Camera" to enable camera access
            </div>
            <video id="video"></video>
            <canvas id="canvas"></canvas>
            <div class="button-group">
                <button class="btn-primary" id="cameraBtn" onclick="startCamera()">
                    Start Camera
                </button>
                <button class="btn-secondary" id="stopCameraBtn" onclick="stopCamera()" style="display:none;">
                    Stop Camera
                </button>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📸 Option 2: Upload QR Image</div>
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
                <p style="font-size: 24px; margin-bottom: 8px;">📷</p>
                <p style="color: #666;">Click to upload QR code image</p>
                <input type="file" id="fileInput" accept="image/*" onchange="handleFileUpload(event)">
            </div>
        </div>

        <div class="qr-result" id="qrResult">
            <h3>QR Code Detected</h3>
            <p id="qrData"></p>
        </div>

        <div class="button-group">
            <button class="btn-primary" id="activateBtn" onclick="activatePill()" style="display:none;">
                <span id="activateBtnText">Confirm Activation</span>
            </button>
        </div>

        <div class="footer">
            <p>Session ID: <code>{session_id}</code></p>
            <p>Expires: {session.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
        </div>
    </div>

    <script>
        const sessionId = "{session_id}";
        const pillId = "{session.pill_id}";
        let cameraActive = false;
        let detectedQR = null;

        async function startCamera() {{
            try {{
                const video = document.getElementById('video');
                const canvas = document.getElementById('canvas');
                const stream = await navigator.mediaDevices.getUserMedia({{
                    video: {{ facingMode: 'environment' }}
                }});

                video.srcObject = stream;
                video.play();
                cameraActive = true;

                document.getElementById('cameraBtn').style.display = 'none';
                document.getElementById('stopCameraBtn').style.display = 'block';
                document.getElementById('cameraPermission').style.display = 'none';
                video.style.display = 'block';

                scanQRCode(video, canvas);
            }} catch (error) {{
                showStatus('Camera access denied. Use image upload instead.', 'error');
            }}
        }}

        function stopCamera() {{
            const video = document.getElementById('video');
            const stream = video.srcObject;
            stream.getTracks().forEach(track => track.stop());
            cameraActive = false;
            video.style.display = 'none';
            document.getElementById('cameraBtn').style.display = 'block';
            document.getElementById('stopCameraBtn').style.display = 'none';
            document.getElementById('cameraPermission').style.display = 'block';
        }}

        function scanQRCode(video, canvas) {{
            const ctx = canvas.getContext('2d');

            function scan() {{
                if (!cameraActive) return;

                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);

                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);

                if (code && !detectedQR) {{
                    detectedQR = code.data;
                    handleQRDetected(code.data);
                    stopCamera();
                }}

                requestAnimationFrame(scan);
            }}
            scan();
        }}

        function handleFileUpload(event) {{
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {{
                const img = new Image();
                img.onload = () => {{
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    canvas.width = img.width;
                    canvas.height = img.height;
                    ctx.drawImage(img, 0, 0);

                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    const code = jsQR(imageData.data, imageData.width, imageData.height);

                    if (code) {{
                        detectedQR = code.data;
                        handleQRDetected(code.data);
                    }} else {{
                        showStatus('No QR code found in image', 'error');
                    }}
                }};
                img.src = e.target.result;
            }};
            reader.readAsDataURL(file);
        }}

        function handleQRDetected(qrData) {{
            document.getElementById('qrData').textContent = qrData;
            document.getElementById('qrResult').style.display = 'block';
            document.getElementById('activateBtn').style.display = 'block';
            showStatus('QR code detected! Ready to activate.', 'info');
        }}

        async function activatePill() {{
            if (!detectedQR) {{
                showStatus('No QR code detected', 'error');
                return;
            }}

            document.getElementById('activateBtn').disabled = true;
            const btnText = document.getElementById('activateBtnText');
            btnText.innerHTML = '<span class="spinner"></span>Activating...';

            try {{
                const response = await fetch('/api/qr-pill/activate', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        session_id: sessionId,
                        pill_id: pillId,
                        qr_data: detectedQR,
                        user_agent: navigator.userAgent
                    }})
                }});

                const result = await response.json();

                if (result.success) {{
                    showStatus('✓ Activation successful! Pill is now LIVE.', 'success');
                    btnText.textContent = 'Activation Complete';

                    // Real-time status updates via WebSocket
                    const ws = new WebSocket(`wss://camelot-os.local/api/qr-pill/status/${{sessionId}}`);
                    ws.onmessage = (event) => {{
                        const status = JSON.parse(event.data);
                        showStatus(status.message, 'info');
                    }};
                }} else {{
                    showStatus('Activation failed: ' + result.error, 'error');
                    document.getElementById('activateBtn').disabled = false;
                    btnText.textContent = 'Confirm Activation';
                }}
            }} catch (error) {{
                showStatus('Network error: ' + error.message, 'error');
                document.getElementById('activateBtn').disabled = false;
                btnText.textContent = 'Confirm Activation';
            }}
        }}

        function showStatus(message, type) {{
            const alert = document.getElementById('statusAlert');
            alert.textContent = message;
            alert.className = 'status ' + type;
            alert.style.display = 'block';

            // Auto-hide info messages
            if (type === 'info') {{
                setTimeout(() => {{
                    alert.style.display = 'none';
                }}, 5000);
            }}
        }}

        // Drag and drop
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.addEventListener('dragover', (e) => {{
            e.preventDefault();
            uploadArea.classList.add('dragover');
        }});
        uploadArea.addEventListener('dragleave', () => {{
            uploadArea.classList.remove('dragover');
        }});
        uploadArea.addEventListener('drop', (e) => {{
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {{
                document.getElementById('fileInput').files = files;
                handleFileUpload({{ target: {{ files: files }} }});
            }}
        }});
    </script>
</body>
</html>
"""

    async def process_activation(
        self,
        session_id: str,
        pill_id: str,
        qr_data: str,
        user_agent: str = "",
        ip_address: str = ""
    ) -> dict:
        """Process QR Pill activation from mobile."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check expiration
        if datetime.utcnow() > session.expires_at:
            return {"success": False, "error": "Session expired"}

        # Parse QR data
        try:
            # QR data format: qr_pill://{pill_id}?token={activation_token}
            if not qr_data.startswith("qr_pill://"):
                return {"success": False, "error": "Invalid QR format"}

            # Extract pill_id from QR
            qr_pill_id = qr_data.split("//")[1].split("?")[0]
            if qr_pill_id != pill_id:
                return {"success": False, "error": "Pill ID mismatch"}

            # Update session
            session.qr_scanned = True
            session.scanned_at = datetime.utcnow()
            session.user_agent = user_agent
            session.ip_address = ip_address
            session.activation_requested = True
            session.activation_status = "in_progress"

            # Send activation to CAMELOT-OS backend
            from control_plane.qr_pill import get_qr_pill

            pill = get_qr_pill(pill_id)
            activation_success = await pill.activate()

            if activation_success:
                session.activation_status = "completed"
                session.status_message = "Pill activated successfully"
                return {
                    "success": True,
                    "message": "Pill activated successfully",
                    "pill_id": pill_id,
                    "session_id": session_id,
                }
            else:
                session.activation_status = "failed"
                session.status_message = "Pill activation failed"
                return {
                    "success": False,
                    "error": "Pill activation failed",
                }

        except Exception as e:
            session.activation_status = "failed"
            session.status_message = str(e)
            return {"success": False, "error": str(e)}

    def get_session_status(self, session_id: str) -> dict:
        """Get session activation status."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session.session_id,
            "pill_id": session.pill_id,
            "qr_scanned": session.qr_scanned,
            "activation_status": session.activation_status,
            "status_message": session.status_message,
            "expires_at": session.expires_at.isoformat(),
        }


# ── Module-level singleton ────────────────────────────────────────────────

_mobile: Optional[MobileQRPillActivation] = None


def get_mobile_activation() -> MobileQRPillActivation:
    """Get or create shared MobileQRPillActivation instance."""
    global _mobile
    if _mobile is None:
        _mobile = MobileQRPillActivation()
    return _mobile
