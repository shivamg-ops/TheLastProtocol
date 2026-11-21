from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def backend_home(request):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JANSAHAYAK AI — Backend Core & API Gateway</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background-color: #17191D;
                color: #F7F7F5;
                font-family: 'Plus Jakarta Sans', sans-serif;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 24px;
            }
            .card {
                background: #1f2329;
                border: 1px solid #2d333b;
                border-radius: 20px;
                max-width: 680px;
                width: 100%;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.4);
                text-align: center;
            }
            .badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(37, 132, 91, 0.15);
                color: #25845B;
                border: 1px solid rgba(37, 132, 91, 0.3);
                padding: 6px 14px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                margin-bottom: 20px;
            }
            .badge-dot {
                width: 8px;
                height: 8px;
                background: #25845B;
                border-radius: 50%;
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.4; transform: scale(0.85); }
            }
            h1 {
                font-size: 32px;
                font-weight: 800;
                letter-spacing: -0.5px;
                margin-bottom: 8px;
            }
            h1 span { color: #A94D37; }
            p.sub {
                color: #9ca3af;
                font-size: 14px;
                margin-bottom: 32px;
            }
            .btn-group {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                justify-content: center;
                margin-bottom: 32px;
            }
            .btn {
                padding: 12px 22px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                text-decoration: none;
                transition: all 0.2s ease;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }
            .btn-primary {
                background: #A94D37;
                color: #ffffff;
                box-shadow: 0 4px 14px rgba(169, 77, 55, 0.35);
            }
            .btn-primary:hover {
                background: #8e3e2b;
                transform: translateY(-1px);
            }
            .btn-secondary {
                background: #282d35;
                color: #e5e7eb;
                border: 1px solid #373e48;
            }
            .btn-secondary:hover {
                background: #323842;
                transform: translateY(-1px);
            }
            .grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                text-align: left;
                margin-top: 10px;
                border-top: 1px solid #2d333b;
                padding-top: 24px;
            }
            .stat-box {
                background: #191c21;
                border: 1px solid #2a3038;
                padding: 14px 16px;
                border-radius: 12px;
            }
            .stat-label {
                font-size: 11px;
                color: #6b7280;
                text-transform: uppercase;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            .stat-value {
                font-family: 'JetBrains Mono', monospace;
                font-size: 13px;
                font-weight: 600;
                color: #f3f4f6;
                margin-top: 4px;
            }
            .footer {
                margin-top: 24px;
                font-size: 11px;
                color: #6b7280;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">
                <div class="badge-dot"></div>
                API Engine Online & Healthy
            </div>
            <h1>JANSAHAYAK <span>AI</span></h1>
            <p class="sub">From Voice to Resolution — Autonomous Backend & API Service</p>

            <div class="btn-group">
                <a href="http://localhost:3000" target="_blank" class="btn btn-primary">
                    🌐 Open Citizen Portal (Port 3000)
                </a>
                <a href="/admin/" class="btn btn-secondary">
                    ⚙️ Django Admin Dashboard
                </a>
                <a href="/api/" class="btn btn-secondary">
                    ⚡ REST API Root
                </a>
            </div>

            <div class="grid">
                <div class="stat-box">
                    <div class="stat-label">Core Version</div>
                    <div class="stat-value">v1.0.0 (Production Ready)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">AI Engine</div>
                    <div class="stat-value">Gemini Multilingual + Rule Fallback</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Supported Languages</div>
                    <div class="stat-value">EN, HI, MR, Hinglish</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Civic Categories</div>
                    <div class="stat-value">6 Municipal Verticals</div>
                </div>
            </div>

            <div class="footer">
                JanSahayak AI © 2026. For citizen UI, visit <strong>http://localhost:3000</strong>.
            </div>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)

urlpatterns = [
    path('', backend_home, name='backend_home'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
