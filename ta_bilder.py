# -*- coding: utf-8 -*-
"""ta_bilder.py — produktbilderna till välkomstsidorna, mörkt (och ljust) läge, dator och telefon.

    python ta_bilder.py            # alla marknader, MÖRKT läge -> bilder/produkt-<slug>.webp (dator)
                                   # och bilder/produkt-<slug>-mobil.webp (telefon)
    python ta_bilder.py --ljus     # även ljust läge (-ljus.webp, visas inte på sidorna)
    python ta_bilder.py --bara-mobil   # bara telefonbilderna (--bara-dator: bara datorbilderna)

Bilderna som visas är MÖRKA, som appen öppnas (Boss 2026-10-20: "Mörk, som appen"). Sidan runt
bilden är ljus (Boss 2026-10-07: inget ljus/mörkt-val på framsidan).

Telefonbilden (2026-10-20): datorbilden skalades ned till 0,22 på 390 px och gick inte att läsa.
Den tas i 390 px bredd med mobil emulering och DPR 2 och beskärs till 390x720 CSS-px (780x1440).
bygg.py visar den med <picture><source media="(max-width: 600px)">.

Appen är mörk som standard (Boss 2026-10-18: "mörktläge ska vara standard."); ljust är ett
sparat val. Valet sätts i localStorage innan sidan laddas — ingen knapp trycks. Temarutan
("Föredrar du ljust läge?") markeras som sedd, så att den inte står i bilden.
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
# Telefonen: fönstret är en vanlig telefon (390x844), bilden beskärs till de översta 720 CSS-px.
MB, MH, MSKALA, MBESKUREN = 390, 844, 2, 720
# Profiler utan egen demoversion i appen (demo_login skickar dem till väljaren /demo): bilden tas
# på närmaste version. E-handel = enskild firma med moms, som konsulten.
BILDPROFIL = {"ehandel": "konsult"}


async def ta(ws_url, url, mork, mobil=False):
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        nr = [0]

        async def be(metod, **p):
            nr[0] += 1
            await ws.send(json.dumps({"id": nr[0], "method": metod, "params": p}))
            while True:
                svar = json.loads(await ws.recv())
                if svar.get("id") == nr[0]:
                    if "error" in svar:
                        raise RuntimeError("%s: %s" % (metod, svar["error"]))
                    return svar.get("result", {})

        await be("Page.enable")
        if mobil:
            await be("Emulation.setDeviceMetricsOverride", width=MB, height=MH, deviceScaleFactor=MSKALA, mobile=True)
            await be("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        else:
            await be("Emulation.setDeviceMetricsOverride", width=B, height=H, deviceScaleFactor=SKALA, mobile=False)
        # Valet skrivs ALLTID ut: profilmappen delas av alla bilder i en körning, så ett sparat
        # 'light' från förra bilden låg annars kvar i den mörka (2026-10-20).
        await be("Page.addScriptToEvaluateOnNewDocument", source=(
            "try{localStorage.setItem('skattklart-tema-tips','1');"
            "localStorage.setItem('skattklart-tema','%s');}catch(e){}" % ("dark" if mork else "light")))
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


def en_bild(slug, profil, mork, mobil=False):
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
        tema, png = asyncio.run(ta(mal["webSocketDebuggerUrl"], DEMO % BILDPROFIL.get(profil, profil), mork, mobil))
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        # Vänta in processen: utan wait() varnar Python "subprocess ... is still running"
        # (ResourceWarning) när Popen-objektet städas bort (2026-10-18).
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("varning: chrome (pid %d) avslutades inte inom 10 s" % p.pid)
        time.sleep(0.5)
    vantat = "dark" if mork else "light"
    if tema != vantat:
        raise RuntimeError("%s: sidan står i %r, väntade %r" % (slug, tema, vantat))
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if mobil:
        assert im.size == (MB * MSKALA, MH * MSKALA), im.size
        im = im.crop((0, 0, MB * MSKALA, MBESKUREN * MSKALA))
    else:
        assert im.size == (int(B * SKALA), int(H * SKALA)), im.size
    ut = os.path.join(HAR, "bilder", "produkt-%s%s.webp" % (slug, varianter(mork, mobil)))
    im.save(ut, "WEBP", quality=82, method=6)
    print("%-28s %s %3d kB" % (os.path.basename(ut), tema, os.path.getsize(ut) // 1024))
    return ut


def varianter(mork, mobil):
    """Filnamnets tillägg: produkt-<slug>[-mobil][-ljus].webp (mörkt = utan tillägg, det som visas)."""
    return ("-mobil" if mobil else "") + ("" if mork else "-ljus")


def main():
    os.makedirs(os.path.join(HAR, "bilder"), exist_ok=True)
    bara = set(a for a in sys.argv[1:] if not a.startswith("--"))   # python ta_bilder.py frilans investerare  (tomt = alla)
    lagen = (True, False) if "--ljus" in sys.argv else (True,)
    if "--bara-mobil" in sys.argv and "--bara-dator" in sys.argv:
        raise SystemExit("ta_bilder.py: --bara-mobil och --bara-dator utesluter varandra")
    skarmar = (True,) if "--bara-mobil" in sys.argv else (False,) if "--bara-dator" in sys.argv else (False, True)
    for m in MARKNADER:
        if bara and m["slug"] not in bara:
            continue
        for mobil in skarmar:
            for mork in lagen:
                ut = en_bild(m["slug"], m["profil"], mork, mobil)
                if m["slug"] == "frilans":      # den neutrala sidans bild
                    with open(ut, "rb") as f, open(os.path.join(HAR, "bilder", "produkt%s.webp" % varianter(mork, mobil)), "wb") as g:
                        g.write(f.read())


if __name__ == "__main__":
    main()
