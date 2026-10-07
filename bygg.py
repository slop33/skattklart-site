# -*- coding: utf-8 -*-
"""bygg.py — bygger välkomstsidan och marknadsversionerna av skattklart.se.

Boss 2026-10-07: "välkomstsida lite anpassad. Neutral. Influencer, streamer etc. …
skattklart.se/twitch etc. för olika marknader" + "Skattklart.se/demo kan vara demo
adressen. och skattklart.se är bara en 'printscreen' på produkten. 'öppnar snart' ish".

    python bygg.py            # skriver index.html, <marknad>/index.html, demo/, 404, sitemap

EN mall, en post per marknad. Skattetexterna (de tre raderna per marknad) hämtas
ordagrant ur appens faktagranskade data/profiler.json — ingen skattetext skrivs här.
Guiderna (skatt-for-*/), villkoren och omdirigeringarna (streamers/, twitch/ …) rörs inte.
"""
import html
import io
import json
import os

HAR = os.path.dirname(os.path.abspath(__file__))
PROFILER = os.path.join(HAR, "..", "..", "skattklart", "data", "profiler.json")
BAS = "https://skattklart.se"
APP = "https://app.skattklart.se"
DEMO = "https://demo.skattklart.se/demo-login"

# slug = adressen. profil = slug i appens profiler.json (styr demots exempel och tipsen).
MARKNADER = [
    {"slug": "streamer", "profil": "streamer", "etikett": "För streamers",
     "rubrik": "Deklarationen för dig som streamar",
     "tips": ["Donationer är skattepliktiga", "Utrustningen är avdragsgill", "Prenumerationer och mjukvara"],
     "guide": ("/skatt-for-streamers/", "Guiden: skatt för streamers")},
    {"slug": "youtuber", "profil": "creator", "etikett": "För youtubers och tiktokare",
     "rubrik": "Deklarationen för dig som gör video", "tips": None,
     "guide": ("/skatt-for-youtubers/", "Guiden: skatt för youtubers")},
    {"slug": "influencer", "profil": "influencer", "etikett": "För influencers",
     "rubrik": "Deklarationen för dig som gör samarbeten", "tips": None,
     "guide": ("/skatt-for-influencers/", "Guiden: skatt för influencers")},
    {"slug": "e-handel", "profil": "ehandel", "etikett": "För e-handlare",
     "rubrik": "Deklarationen för dig som säljer på nätet", "tips": None, "guide": None},
    {"slug": "frilans", "profil": "konsult", "etikett": "För frilansare och konsulter",
     "rubrik": "Deklarationen för dig som fakturerar", "tips": None, "guide": None},
    {"slug": "uthyrning", "profil": "uthyrare", "etikett": "För dig som hyr ut",
     "rubrik": "Deklarationen för dig som hyr ut", "tips": None, "guide": None},
    {"slug": "investerare", "profil": "investerare", "etikett": "För dig med aktier, fonder eller krypto",
     "rubrik": "Deklarationen för dig som sålt aktier eller krypto", "tips": None, "guide": None},
    {"slug": "extraknack", "profil": "anstalld", "etikett": "För dig med extraknäck",
     "rubrik": "Deklarationen för dig med lön och lite vid sidan av", "tips": None, "guide": None},
]

# Samma tre steg som appens startsida ("Så funkar det") och llms.txt beskriver.
STEG = [
    ("Svara och ladda upp", "Du svarar på frågor om året och fotar eller laddar upp kvitton."),
    ("Skattklart räknar", "Du får rutorna och bilagorna till Inkomstdeklaration 1, med avdragen framräknade."),
    ("Du lämnar in själv", "Du skriver under med BankID hos Skatteverket. Skattklart lämnar aldrig in åt dig."),
]

CSS = """
:root{--navy:#1a2744;--navy2:#243460;--gold:#f0b429;--gold2:#d99a10;--bg:#f1f3f8;--panel:#fff;
--ink:#1a2744;--dim:#4d5b78;--line:#d8deea}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--ink);line-height:1.55;overflow-x:hidden}
a{color:inherit}
.topp{background:var(--navy);color:#fff}
.inre{max-width:1120px;margin:0 auto;padding:0 20px}
.topp .inre{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:64px}
.logo{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:800;font-size:21px;letter-spacing:-.3px}
.logo-m{width:36px;height:36px;background:var(--gold);border-radius:9px;display:flex;align-items:center;justify-content:center}
.logo b{color:var(--gold);font-weight:800}
.snart{font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--navy);
background:var(--gold);padding:6px 12px;border-radius:999px;white-space:nowrap}
.hjalte{background:linear-gradient(180deg,var(--navy) 0,var(--navy2) 100%);color:#fff;padding:44px 0 0}
.etikett{font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold)}
h1{font-size:clamp(30px,5.2vw,50px);line-height:1.12;letter-spacing:-.6px;margin:12px 0 14px;max-width:820px;text-wrap:balance}
h1 span{color:var(--gold)}
.ingress{font-size:18px;color:rgba(255,255,255,.82);max-width:640px}
.knappar{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center;margin:26px 0 8px}
.knapp{display:inline-flex;align-items:center;min-height:50px;padding:0 26px;border-radius:10px;background:var(--gold);
color:var(--navy);font-weight:800;font-size:16px;text-decoration:none}
.knapp:hover{background:var(--gold2)}
.lank{color:#fff;font-weight:600;text-decoration:underline;text-decoration-color:rgba(240,180,41,.7);text-underline-offset:4px;
min-height:44px;display:inline-flex;align-items:center}
.not{font-size:14px;color:rgba(255,255,255,.6)}
.bild{margin:36px auto 0;max-width:1000px;border-radius:14px 14px 0 0;overflow:hidden;border:1px solid rgba(255,255,255,.18);
border-bottom:0;box-shadow:0 -2px 40px rgba(0,0,0,.35);background:#fff}
.bild img{display:block;width:100%;height:auto}
.bildtext{font-size:13px;color:var(--dim);text-align:center;padding:10px 20px 0}
section{padding:44px 0}
h2{font-size:24px;letter-spacing:-.2px;margin-bottom:18px}
.rutnat{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.kort{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
.kort h3{font-size:17px;margin-bottom:6px}
.kort p{font-size:15px;color:var(--dim)}
.nr{display:inline-flex;width:28px;height:28px;border-radius:50%;background:var(--navy);color:#fff;font-weight:800;font-size:14px;
align-items:center;justify-content:center;margin-bottom:10px}
.kalla{font-size:13px;color:var(--dim);margin-top:14px}
.chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border-radius:999px;background:var(--panel);
border:1px solid var(--line);font-size:15px;font-weight:600;text-decoration:none}
.chip:hover,.chip[aria-current]{border-color:var(--gold2);background:#fff8e6}
.avslut{background:var(--navy);color:#fff;text-align:center}
.avslut h2{margin-bottom:8px}
.avslut p{color:rgba(255,255,255,.75);margin-bottom:20px}
.avslut .knappar{justify-content:center;margin-top:0}
footer{background:var(--navy);color:rgba(255,255,255,.55);font-size:13px;text-align:center;padding:0 20px 28px}
footer a{color:rgba(255,255,255,.75)}
:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
@media (max-width:560px){.hjalte{padding-top:30px}.ingress{font-size:16px}.knapp{width:100%;justify-content:center}section{padding:34px 0}}
"""

LOGO = ('<span class="logo-m"><svg viewBox="0 0 46 46" width="72%" height="72%" aria-hidden="true">'
        '<path d="M23 4 L39 10 V23 C39 33 32 40 23 43 C14 40 7 33 7 23 V10 Z" fill="#1a2744"/>'
        '<path d="M15.5 24 l5.5 5.5 L31.5 18" fill="none" stroke="#f0b429" stroke-width="4" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg></span>')


def e(t):
    return html.escape(str(t), quote=True)


def las_profiler():
    with io.open(PROFILER, encoding="utf-8") as f:
        return {p["slug"]: p for p in json.load(f)["profiler"]}


def sida(m, profiler):
    """m = marknadspost eller None (den neutrala välkomstsidan)."""
    if m:
        p = profiler[m["profil"]]
        sokvag = "/%s/" % m["slug"]
        titel = "Skattklart %s — öppnar snart" % m["etikett"].lower()
        beskr = ("%s. Skattklart räknar fram avdragen och gör deklarationen klar att lämna in själv. "
                 "Öppnar snart — prova demot redan nu." % m["rubrik"])
        etikett, rubrik = m["etikett"], m["rubrik"]
        demo = "/demo/?exempel=%s" % m["profil"]
        bild, bildalt = "/bilder/produkt-%s.webp" % m["slug"], "Skattklart i demoläge för %s: nästa steg, skatten hittills och avdragstips." % p["namn"].lower()
        valda = m["tips"] or [t["rubrik"] for t in p["tips"][:3]]
        tips = [t for r in valda for t in p["tips"] if t["rubrik"] == r]
        assert len(tips) == len(valda), (m["slug"], valda)
    else:
        sokvag, titel = "/", "Skattklart — deklarationen klar att lämna in. Öppnar snart"
        beskr = ("Skattklart räknar fram avdragen och gör deklarationen klar att lämna in själv med BankID "
                 "hos Skatteverket. Öppnar snart — prova demot redan nu.")
        etikett, rubrik = "Deklaration för privatpersoner och enskild firma", "Din deklaration klar att lämna in"
        demo, bild = "/demo/", "/bilder/produkt.webp"
        bildalt = "Skattklart i demoläge: nästa steg, skatten hittills och kommande datum."
        tips = []

    delar = []
    delar.append("""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s%s">
<meta property="og:type" content="website">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s%s">
<meta property="og:image" content="%s%s">
<meta name="theme-color" content="#1a2744">
<style>%s</style>
</head>
<body>
<header class="topp"><div class="inre">
  <a class="logo" href="/" aria-label="Skattklart, startsidan">%s<span>Skatt<b>klart</b></span></a>
  <span class="snart">Öppnar snart</span>
</div></header>
<main>
<div class="hjalte"><div class="inre">
  <p class="etikett">%s</p>
  <h1>%s <span>— med avdragen du annars missar.</span></h1>
  <p class="ingress">Du svarar på frågor om året och laddar upp kvitton. Skattklart räknar och ger dig rutorna och bilagorna till deklarationen. Du lämnar in själv med BankID hos Skatteverket.</p>
  <div class="knappar">
    <a class="knapp" href="%s">Prova demot</a>
    <a class="lank" href="%s/waitlist">Få besked när vi öppnar</a>
  </div>
  <p class="not">Demot är gratis och kräver inget konto.</p>
  <div class="bild"><img src="%s" width="1600" height="1000" alt="%s"></div>
</div></div>
<p class="bildtext">Bilden visar demot med exempeldata.</p>
""" % (e(titel), e(beskr), BAS, sokvag, e(titel), e(beskr), BAS, sokvag, BAS, bild, CSS, LOGO,
       e(etikett), e(rubrik), demo, APP, bild, e(bildalt)))

    if tips:
        kort = "\n".join('    <div class="kort"><h3>%s</h3><p>%s</p></div>' % (e(t["rubrik"]), e(t["text"]))
                         for t in tips)
        guide = ('  <p class="kalla"><a href="%s">%s</a></p>\n' % (m["guide"][0], e(m["guide"][1]))) if m["guide"] else ""
        delar.append("""<section><div class="inre">
  <h2>Tre saker som gäller dig</h2>
  <div class="rutnat">
%s
  </div>
%s</div></section>
""" % (kort, guide))

    steg = "\n".join('    <div class="kort"><span class="nr">%d</span><h3>%s</h3><p>%s</p></div>' % (i, e(r), e(t))
                     for i, (r, t) in enumerate(STEG, 1))
    chips = "\n".join('    <a class="chip" href="/%s/"%s>%s</a>' % (
        x["slug"], ' aria-current="page"' if m and x["slug"] == m["slug"] else "", e(x["etikett"]))
        for x in MARKNADER)
    delar.append("""<section%s><div class="inre">
  <h2>Så funkar det</h2>
  <div class="rutnat">
%s
  </div>
</div></section>
<section style="padding-top:0"><div class="inre">
  <h2>%s</h2>
  <div class="chips">
%s
  </div>
</div></section>
<section class="avslut"><div class="inre">
  <h2>Se hur det ser ut</h2>
  <p>Demot har färdiga exempel. Inget sparas kopplat till dig.</p>
  <div class="knappar">
    <a class="knapp" href="%s">Prova demot</a>
    <a class="lank" href="%s/waitlist">Få besked när vi öppnar</a>
  </div>
</div></section>
</main>
<footer>© 2026 Skattklart · hej@skattklart.se ·
  <a href="/integritetspolicy/">Integritetspolicy</a> · <a href="/anvandarvillkor/">Användarvillkor</a></footer>
</body>
</html>
""" % (' style="padding-top:0"' if tips else "", steg,
       "Fler ingångar" if m else "Vem är du?", chips, demo, APP))
    return "".join(delar)


DEMOSIDA = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Skattklart — demo</title>
<meta name="description" content="Prova Skattklart med färdiga exempel. Gratis, inget konto.">
<link rel="canonical" href="%s/demo/">
<style>%s
body{background:var(--navy);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:24px;text-align:center}
p{color:rgba(255,255,255,.75);margin:20px 0 24px;max-width:360px}
.liten{font-size:13px;color:rgba(255,255,255,.5)}
</style>
</head>
<body>
  <a class="logo" href="/" aria-label="Skattklart, startsidan">%s<span>Skatt<b>klart</b></span></a>
  <p>Demot öppnas automatiskt — annars tryck på knappen.</p>
  <a class="knapp" id="go" href="%s">Öppna demot</a>
  <p class="liten">Du får ett eget testkonto med färdiga exempel. Inget att registrera, ingenting sparas kopplat till dig.</p>
  <script>
    // ?exempel=<profil> (från en marknadssida) följer med till demot. Bara kända värden släpps igenom.
    (function () {
      var ok = %s, a = document.getElementById('go');
      var ex = new URLSearchParams(location.search).get('exempel');
      if (ex && ok.indexOf(ex) !== -1) a.href += '?exempel=' + encodeURIComponent(ex);
      setTimeout(function () { location.href = a.href; }, 1000);
    })();
  </script>
</body>
</html>
"""

SIDA404 = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sidan finns inte — Skattklart</title>
<meta name="robots" content="noindex">
<style>%s
body{background:var(--navy);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:24px;text-align:center}
p{color:rgba(255,255,255,.75);margin:20px 0 24px}
</style>
</head>
<body>
  <a class="logo" href="/" aria-label="Skattklart, startsidan">%s<span>Skatt<b>klart</b></span></a>
  <p>Den här sidan finns inte.</p>
  <a class="knapp" href="/">Till startsidan</a>
</body>
</html>
"""


def skriv(rel, text):
    p = os.path.join(HAR, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("skrev", rel, len(text.encode("utf-8")), "B")


def main():
    profiler = las_profiler()
    skriv("index.html", sida(None, profiler))
    for m in MARKNADER:
        skriv("%s/index.html" % m["slug"], sida(m, profiler))
    skriv("demo/index.html", DEMOSIDA % (BAS, CSS, LOGO, DEMO, json.dumps(sorted(profiler))))
    skriv("404.html", SIDA404 % (CSS, LOGO))
    sokvagar = ["/"] + ["/%s/" % m["slug"] for m in MARKNADER] + [
        "/skatt-for-streamers/", "/skatt-for-youtubers/", "/skatt-for-influencers/",
        "/integritetspolicy/", "/anvandarvillkor/"]
    skriv("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join("  <url><loc>%s%s</loc></url>\n" % (BAS, s) for s in sokvagar) + "</urlset>\n")


if __name__ == "__main__":
    main()
