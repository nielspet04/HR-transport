"""Loopback-only, single-user local management UI; not a public HR service."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlsplit,parse_qs


def make_server(store,port=8765):
    if hasattr(store,'get_route_plan'):
        from app.automatic_routes import trigger
        trigger(store)
    token=secrets.token_urlsafe(32)
    static=Path(__file__).with_name('web')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Never log names, body, source paths or configuration values.

        def reply(self,status,body,content_type='application/json',filename=None):
            encoded=body if isinstance(body,bytes) else body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type if isinstance(body,bytes) else content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(encoded)))
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers(); self.wfile.write(encoded)

        def host_ok(self):
            port=self.server.server_port
            hosts=(f'127.0.0.1:{port}',f'localhost:{port}')
            origin=self.headers.get('Origin')
            return self.headers.get('Host') in hosts and (origin is None or origin in tuple('http://'+h for h in hosts))

        def do_GET(self):
            if not self.host_ok():return self.reply(403,'{}')
            if self.path=='/api/state':
                return self.reply(200,json.dumps({**store.snapshot(),'csrf':token},ensure_ascii=False))
            if urlsplit(self.path).path=='/api/routing/export':
                query=parse_qs(urlsplit(self.path).query)
                if not secrets.compare_digest(query.get('csrf',[''])[0],token):return self.reply(403,'{}')
                try:
                    from app.distance_export import workbook_bytes
                    run=int(query.get('run_id',[''])[0])
                    return self.reply(200,workbook_bytes(store,run),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','werknemersafstanden-controle.xlsx')
                except ValueError as error:return self.reply(400,json.dumps({'error':str(error)}))
            if urlsplit(self.path).path in ('/api/routing/preview','/api/routing/map-background'):
                from app.route_preview import preview,background
                query=parse_qs(urlsplit(self.path).query)
                if not secrets.compare_digest(query.get('csrf',[''])[0],token):return self.reply(403,'{}')
                try:
                    rid=int(query.get('id',[''])[0])
                    if urlsplit(self.path).path.endswith('map-background'):
                        return self.reply(200,background(store,rid),'image/png')
                    return self.reply(200,json.dumps(preview(store,rid)))
                except ValueError as error:return self.reply(400,json.dumps({'error':str(error)}))
            if urlsplit(self.path).path=='/api/routing/plan' and hasattr(store,'get_route_plan'):
                try:
                    run=int(parse_qs(urlsplit(self.path).query).get('run_id',[''])[0])
                    return self.reply(200,json.dumps(store.get_route_plan(run),ensure_ascii=False))
                except ValueError as error:return self.reply(400,json.dumps({'error':str(error)},ensure_ascii=False))
            if urlsplit(self.path).path=='/api/matching/run' and hasattr(store,'get_matching'):
                try:
                    run=int(parse_qs(urlsplit(self.path).query).get('id',[''])[0])
                    return self.reply(200,json.dumps(store.get_matching(run),ensure_ascii=False))
                except ValueError:return self.reply(400,'{"error":"Onbekende maandverwerking."}')
            files={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if store.snapshot().get('view')=='routes':
                files['/']=('routes.html','text/html')
                files['/routes.js']=('routes.js','text/javascript')
            if self.path not in files:return self.reply(404,'{}')
            name,mime=files[self.path]
            self.reply(200,(static/name).read_text(encoding='utf-8'),mime)

        def do_POST(self):
            if not self.host_ok() or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),token):
                return self.reply(403,'{}')
            if self.headers.get('Content-Type')!='application/json':return self.reply(415,'{}')
            try:
                size=int(self.headers.get('Content-Length','0'))
                limit=7_100_000 if self.path=='/api/action/planet_upload' else 1_000_000
                if size<=0 or size>limit:return self.reply(413,'{"error":"Bestand of verzoek te groot."}')
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise ValueError('Ongeldig verzoek.')
                if self.path=='/api/payroll/export':
                    from app.payroll_export import workbook_bytes
                    result,month=workbook_bytes(store,payload.get('run_id'))
                    return self.reply(200,result,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',f'VERVOER-AFWIJKENDE-LONEN-{month}.xlsx')
                if not self.path.startswith('/api/action/'):return self.reply(404,'{}')
                action=self.path.removeprefix('/api/action/')
                if not isinstance(payload.get('data'),dict):raise ValueError('Ongeldige invoer.')
                store.apply(action,payload['data'],payload.get('revision'))
                self.reply(200,'{"ok":true}')
            except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as error:
                message=str(error) if isinstance(error,ValueError) else 'Ongeldige of conflicterende invoer.'
                self.reply(400,json.dumps({'error':message},ensure_ascii=False))
            except Exception:
                self.reply(500,'{"error":"Opslaan mislukt; geen volledige wijziging bevestigd."}')

    return HTTPServer(('127.0.0.1',port),Handler)
