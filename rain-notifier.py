#!/usr/bin/env python3

import cv2
import datetime
import io
import math
import numpy as np
import os
import requests
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

os.chdir(os.path.dirname(__file__))

args = sys.argv
if len(args) != 3: sys.exit(f'invalid args: {args}')
lat = float(args[1])
lon = float(args[2])
if lat <  30 or  50 < lat: sys.exit(f'invalid lat: {lat}')
if lon < 130 or 150 < lon: sys.exit(f'invalid lon: {lon}')

kmrange1 = 5
kmrange2 = 20
ymdhn = str(int(int((datetime.datetime.now() + datetime.timedelta(hours=-9, minutes=-2)).strftime('%Y%m%d%H%M')) / 5) * 5)

print(f'raindetector started for [{lat}, {lon}], {ymdhn}')

deg2rad = math.pi / 180
rearth = 6378137
hearth = math.pi * rearth
tilepixel = 256
z = 8
latrange = kmrange2 * 1000 / (rearth * math.pi / 2) * 90
lonrange = latrange / math.cos(lat * deg2rad)


def tile2xy(xt, yt, z):
    tilemeter = hearth / (2 ** (z - 1))
    x = xt * tilemeter - hearth
    y = yt * tilemeter - hearth
    return (x, y)


def xy2ll(x, y):
    lon = x * 180 / hearth
    lat = 90 - math.atan(math.exp(y * math.pi / hearth)) * 360 / math.pi
    return (lat, lon)


def tile2ll(xt, yt, z):
    x, y = tile2xy(xt, yt, z)
    return xy2ll(x, y)


def ll2xy(lat, lon):
    x = lon * hearth / 180
    y = -1 * math.log(math.tan((lat + 90) * math.pi / 360)) / (math.pi / 180) * hearth / 180
    return (x, y)


def xyz2tile(x, y, z):
    tilemeter = hearth / (2 ** (z - 1))
    xt = (x + hearth) / tilemeter
    yt = (y + hearth) / tilemeter
    xi = int(xt)
    yi = int(yt)
    xf = int(tilepixel * (xt - xi))
    yf = int(tilepixel * (yt - yi))
    return (xi, yi, xf, yf)


def llz2tile(lat, lon, z):
    x, y = ll2xy(lat, lon)
    return xyz2tile(x, y, z)


def distance(lat1, lon1, lat2, lon2):
    c = lambda x: math.cos(x * deg2rad)
    s = lambda x: math.sin(x * deg2rad)
    d = rearth * math.acos(s(lat1) * s(lat2) + c(lat1) * c(lat2) * c(lon1 - lon2))
    return d


ximin, yimin, _, _ = llz2tile(lat + latrange, lon - lonrange, z)
ximax, yimax, _, _ = llz2tile(lat - latrange, lon + lonrange, z)

cols = np.array([
    [  0,   0,   0],
    [255, 255, 255],
    [255, 242, 242],
    [255, 210, 160],
    [255, 140,  33],
    [255,  65,   0],
    [  0, 246, 255],
    [  0, 154, 255],
    [  0,  40, 255],
    [104,   0, 180],
])

pxcount1 = [0 for x in range(len(cols))]
pxcount2 = [0 for x in range(len(cols))]

for xi in range(ximin, ximax+1):
    for yi in range(yimin, yimax+1):
        ipath = f'{ymdhn}_{z}_{xi}_{yi}.png'
        iurl = f'https://www.jma.go.jp/bosai/jmatile/data/nowc/{ymdhn}00/none/{ymdhn}00/surf/hrpns/{z}/{xi}/{yi}.png'
        print(iurl)
        r = requests.get(iurl, stream=True)
        if r.status_code != 200: sys.exit(f'{iurl} returned {r.status_code}')
        with open(ipath, 'wb') as f: f.write(r.content)

        i = cv2.imread(ipath)
        for xp in range(256):
            for yp in range(256):
                lat2, lon2 = tile2ll(xi+xp/256, yi+yp/256, z)
                d = distance(lat, lon, lat2, lon2) / 1000
                if d < kmrange1:
                    for c, col in enumerate(cols):
                        if (i[yp, xp] != col).any(): continue
                        pxcount1[c] += 1
                        break
                if d < kmrange2:
                    for c, col in enumerate(cols):
                        if (i[yp, xp] != col).any(): continue
                        pxcount2[c] += 1
                        break

        os.remove(ipath)

pxsum1 = sum(pxcount1)
pxsum2 = sum(pxcount2)

if pxsum1 < 10 * (kmrange1 ** 2): sys.exit('insufficient pixel number')
if pxsum2 < 10 * (kmrange2 ** 2): sys.exit('insufficient pixel number')

pxrain1 = sum(pxcount1[2:])
pxrain2 = sum(pxcount2[2:])

lpath = f'latest_{lat}_{lon}.txt'

if os.path.exists(lpath):
    with open(lpath, 'r') as f: lraw = f.read()
    print(f'latest = {lraw}')
    latest = datetime.datetime.strptime(lraw, '%Y%m%d%H%M')
    ymdhn2 = datetime.datetime.strptime(ymdhn, '%Y%m%d%H%M')
    dymdhn = ymdhn2 - latest
else:
    dymdhn = datetime.timedelta(days=99)

message = f'''rain pixels:
    r = {kmrange1:2d} km: {100 * pxrain1 / pxsum1:6.2f} % ({pxrain1} / {pxsum1} px)
    r = {kmrange2:2d} km: {100 * pxrain2 / pxsum2:6.2f} % ({pxrain2} / {pxsum2} px)
latlon: [{lat}, {lon}], datetime: {ymdhn}
https://www.jma.go.jp/bosai/nowc/#zoom:10/lat:{lat}/lon:{lon}/colordepth:normal/elements:hrpns&liden&slmcs'''

print(message)

subject2 = ''

if pxrain1 / pxsum1 >= 0.1:
    if not os.path.exists(lpath):
        subject2 = 'rain approaching'
    elif ymdhn[8:12] == '0000':
        subject2 = 'rain continues'
    with open(lpath, 'w') as f: f.write(ymdhn)
elif pxrain2 / pxsum2 < 0.01 and os.path.exists(lpath):
    os.remove(lpath)
    subject2 = 'rain stopped'
elif ymdhn[8:12] == '0000':
    subject2 = 'no rain'

if subject2 == '': sys.exit('mail has not been sent')

subject = f'{subject2} at {ymdhn}'

msg = MIMEMultipart()
msg['Subject'] = subject
msg['From'] = 'from@example.com'
msg['To'] = 'to@example.com'
msg.attach(MIMEText(message, 'plain', 'utf-8'))

server = SMTP('example.com', 25)
server.send_message(msg)
server.quit()

print('mail has been sent')
