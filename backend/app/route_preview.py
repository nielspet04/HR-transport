"""Stored route geometry and server-side Mapbox background; no browser access token."""
import json
import math
from urllib.parse import urlencode
from urllib.request import build_opener
from urllib.error import HTTPError, URLError
from app.geocoding import NoRedirect, token_value
from app.routing import validate_geometry
from app.distances import whole_kms


def preview(store, route_id):
    with store.connect() as db:
        row = db.execute('SELECT v.*,d.kms AS original_kms FROM route_visualizations v JOIN route_distances d ON d.id=v.route_id WHERE v.route_id=?', (route_id,)).fetchone()
    if not row:return {'status':'MISSING'}
    result = dict(row)
    for key in ('kms','original_kms'):
        if result.get(key) is not None:result[key]=str(whole_kms(result[key]))
    if row['status'] != 'READY':return result
    geometry = json.loads(row['geometry']);validate_geometry(geometry)
    points = [( (lon+180)/360, (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2 ) for lon,lat in geometry['coordinates']]
    xs,ys = zip(*points);cx,cy = (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
    zoom = round(max(0,min(18,math.log2(800/(512*max(max(xs)-min(xs),1e-9))),math.log2(480/(512*max(max(ys)-min(ys),1e-9))))),2)
    scale = 512*2**zoom
    result.update(points=[[450+(x-cx)*scale,300+(y-cy)*scale] for x,y in points],
                  center=[cx*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*cy))))],zoom=zoom)
    result.pop('geometry')
    return result


def background(store, route_id):
    item = preview(store,route_id)
    if item['status'] != 'READY':raise ValueError('Geen routelijn beschikbaar.')
    lon,lat = item['center']
    url = f'https://api.mapbox.com/styles/v1/mapbox/streets-v12/static/{lon},{lat},{item["zoom"]},0/900x600?'+urlencode({'access_token':token_value()})
    try:
        with build_opener(NoRedirect()).open(url,timeout=20) as response:
            content = response.read(5_000_001)
        if len(content)>5_000_000 or not content.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Ongeldige kaartafbeelding.')
        return content
    except (HTTPError,URLError,TimeoutError,OSError):
        raise ValueError('Kaartachtergrond niet beschikbaar. Controleer Mapbox-token en rechten voor kaartafbeeldingen.') from None
