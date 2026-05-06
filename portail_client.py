"""
L'ÉTUDIANT — PORTAIL CLIENT
Lancement : python portail_client.py
Ouvre     : http://localhost:8889
"""
import os, threading, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 8889
HTML_FILE = Path(__file__).parent / "portail.html"

if not HTML_FILE.exists():
    print(f"\n  ERREUR : portail.html introuvable dans {HTML_FILE.parent}")
    print("  Mets portail.html et portail_client.py dans le meme dossier.\n")
    exit(1)

HTML = HTML_FILE.read_text(encoding="utf-8")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))
    def log_message(self, *a): pass

print("\n" + "="*50)
print("  L'ETUDIANT - PORTAIL CLIENT")
print("="*50)
print(f"\n  portail.html charge OK")
print(f"\n  >>> http://localhost:{PORT} <<<\n")
print("  Ctrl+C pour arreter\n")

threading.Thread(
    target=lambda: (__import__("time").sleep(1.2), webbrowser.open(f"http://localhost:{PORT}")),
    daemon=True
).start()

try:
    HTTPServer(("localhost", PORT), Handler).serve_forever()
except KeyboardInterrupt:
    print("\n  Arrete.")