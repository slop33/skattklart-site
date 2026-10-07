# -*- coding: utf-8 -*-
"""ta_bilder.py — produktbilderna till välkomstsidorna, ljust och mörkt läge.

    python ta_bilder.py            # alla marknader, ljust läge -> bilder/produkt-<slug>.webp
    python ta_bilder.py --mork     # även mörkt läge (-mork.webp). Välkomstsidorna visar bara den ljusa
                                   # sedan 2026-10-07 (Boss: "två olika ljus o natt på framsidan").

Demot följer enhetens inställning (prefers-color-scheme, static/theme.js i appen), så
mörkt läge tas genom att emulera den inställningen FÖRE sidan laddas — ingen knapp trycks.
Väntar i riktig tid (dashboardens siffror kommer via ett eget anrop)."""
import asyncio
import base64
import io
import json
import os
import subprocess
import sys
import time
import urllib.request

import websockets
from PIL import Image

from bygg import MARKNADER

HAR = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9341
# Demot har ett dygnstak per anslutning (429 "Demot har startats många gånger i dag"). Mot den
# lokala instansen (samma kod och exempeldata) finns inget sådant tak i praktiken:
#     set SKATTKLART_BILDBAS=http://127.0.0.1:5050
DEMO = os.environ.get("SKATTKLART_BILDBAS", "https://demo.skattklart.se").rstrip("/") + "/demo-login?exempel=%s"
B, H, SKALA = 1280, 800, 1.25


async def ta(ws_url, url, mork):
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        nr = [0]

        async def be(metod, **p):
            nr[0] += 1
            await ws.send(json.dumps({"id": nr[0], "method": metod, "params": p}))
            while True:
                svar = json.loads(await ws.recv())
                if svar.get("id") == nr[0]:
                    return svar.get("result", {})

        await be("Page.enable")
        await be("Emulation.setDeviceMetricsOverride", width=B, height=H, deviceScaleFactor=SKALA, mobile=False)
        await be("Emulation.setEmulatedMedia",
                 features=[{"name": "prefers-color-scheme", "value": "dark" if mork else "light"}])
        await be("Page.navigate", url=url)
        await asyncio.sleep(6)
        tema = (await be("Runtime.evaluate", expression="document.documentElement.getAttribute('data-theme')")
                ).get("result", {}).get("value")
        rubrik = (await be("Runtime.evaluate", expression="(document.querySelector('h1')||{}).textContent||''")
                  ).get("result", {}).get("value") or ""
        if not rubrik.strip().startswith("Hej"):      # spärrsidan eller inloggningen — inte produkten
            raise RuntimeError("fel sida i bild: h1=%r (%s)" % (rubrik.strip()[:60], url))
        data = (await be("Page.captureScreenshot", format="png")).get("data")
        return tema, base64.b64decode(data)


def en_bild(slug, profil, mork):
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                          "--user-data-dir=" + os.path.join(os.environ["TEMP"], "skattklart-bildprofil-%d" % os.getpid()),
                          "--remote-debugging-port=%d" % PORT, "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=1) as r:
                    flikar = json.load(r)
                break
            except Exception:
                time.sleep(0.3)
        else:
            raise RuntimeError("chrome svarade inte på felsökningsporten")
        mal = next(t for t in flikar if t.get("type") == "page")
        tema, png = asyncio.run(ta(mal["webSocketDebuggerUrl"], DEMO % profil, mork))
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        time.sleep(0.5)
    vantat = "dark" if mork else "light"
    if tema != vantat:
        raise RuntimeError("%s: sidan står i %r, väntade %r" % (slug, tema, vantat))
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size == (int(B * SKALA), int(H * SKALA)), im.size
    ut = os.path.join(HAR, "bilder", "produkt-%s%s.webp" % (slug, "-mork" if mork else ""))
    im.save(ut, "WEBP", quality=82, method=6)
    print("%-28s %s %3d kB" % (os.path.basename(ut), tema, os.path.getsize(ut) // 1024))
    return ut


def main():
    os.makedirs(os.path.join(HAR, "bilder"), exist_ok=True)
    bara = set(a for a in sys.argv[1:] if not a.startswith("--"))   # python ta_bilder.py frilans investerare  (tomt = alla)
    lagen = (False, True) if "--mork" in sys.argv else (False,)
    for m in MARKNADER:
        if bara and m["slug"] not in bara:
            continue
        for mork in lagen:
            ut = en_bild(m["slug"], m["profil"], mork)
            if m["slug"] == "frilans":      # den neutrala sidans bild
                with open(ut, "rb") as f, open(os.path.join(HAR, "bilder", "produkt%s.webp" % ("-mork" if mork else "")), "wb") as g:
                    g.write(f.read())


if __name__ == "__main__":
    main()
