# -*- coding: utf-8 -*-
"""bygg.py — bygger välkomstsidan och marknadsversionerna av skattklart.se.

Boss 2026-10-07: "välkomstsida lite anpassad. Neutral. Influencer, streamer etc. …
skattklart.se/twitch etc. för olika marknader" + "Skattklart.se/demo kan vara demo
adressen. och skattklart.se är bara en 'printscreen' på produkten. 'öppnar snart' ish".

    python bygg.py            # skriver index.html, <marknad>/index.html, <källa>/index.html, 404,
                              # ikonerna och sitemap-valkomst.xml

EN mall, en post per marknad. Skattetexterna (de tre raderna per marknad) hämtas
ordagrant ur appens faktagranskade data/profiler.json — ingen skattetext skrivs här.
Guiderna (skatt-for-*/), villkoren och omdirigeringarna (streamers/, youtubers/ …) rörs inte.
Källsidorna (twitch/, kick/, youtube/, tiktok/) skrivs härifrån sedan 2026-10-18 — de var
förut omdirigeringar till streamerguiden.
Ikonerna (skölden) kopieras ur appens static/icons, så välkomstsidorna och appen har samma
favicon. sitemap-valkomst.xml får <lastmod> ur git (kräver git och Pillow).

EN ADRESS (Boss 2026-10-18: "jag ser att det står app.skattklart.se men ska det vara adressen
när vi lanserar? det ska väl bara vara skattklart.se/vadmanharklickatpå etc. ?", valet "Allt
på skattklart.se" och "Flytta nu — kör!"): sidorna här och appen ligger på samma värd. Caddy
på servern serverar en fil härifrån när sökvägen finns som fil eller som katalog med
index.html, och skickar allt annat till appen (skattklart/deploy/Caddyfile.skattklart).
Därför länkar sidorna till appen med sökvägar på samma värd (/kom-igang/..., /waitlist,
/demo, /demo-login?exempel=...), och här får inte finnas någon sökväg som är appens:
demo/, waitlist/, ordlista/, villkoren och robots.txt är borttagna (arkiv i
skattklart/docs/arkiv-2026-10-18-adress/). robots.txt, sitemap.xml (ett index) och llms.txt
ägs av appen; den här filen skriver välkomstsidornas del, sitemap-valkomst.xml.
Utläggning: skattklart/docs/LANSERING.md, "En adress".
"""
import datetime
import html
import io
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HAR = os.path.dirname(os.path.abspath(__file__))
APPROT = os.path.join(HAR, "..", "..", "skattklart")
PROFILER = os.path.join(APPROT, "data", "profiler.json")
IKONER = os.path.join(APPROT, "static", "icons")
BAS = "https://skattklart.se"
# Appens sökvägar på SAMMA värd (En adress, se ovan). Demoknappen: utan exempel appens väljare
# ("Vilket exempel vill du se?"), med ett exempel (från en marknadssida) rakt in i det.
# Ett exempel som inte är en demoversion i appen skickar /demo-login själv till väljaren.
DEMOVAL = "/demo"
DEMO = "/demo-login"
KOM_IGANG = "/kom-igang"
VANTELISTA = "/waitlist"
# Sökvägar som är appens (tests/app/test_en_adress.py i appen prövar mot Flasks rutter).
# En fil eller katalog här med något av namnen skulle skugga appen i Caddy — bygget stoppar.
APPENS = ("demo", "demo-login", "login", "logout", "kom-igang", "waitlist", "dashboard", "api",
          "static", "admin", "l", "ordlista", "intakter", "villkor", "integritet",
          "anvandarvillkor", "integritetspolicy", "plattform", "bankid", "bank", "pay",
          "konto", "declaration", "access", "robots.txt", "sitemap.xml", "llms.txt")
# Samma två länkar som appens bas.html (där under /static/icons/). favicon.ico i roten
# täcker sidorna utan egen <link rel="icon">: guiderna, villkoren och omdirigeringarna,
# som bygg.py inte skriver.
IKONLANKAR = ('<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">\n'
              '<link rel="apple-touch-icon" href="/apple-touch-icon.png">')

# slug = adressen. profil = slug i appens profiler.json (styr demots exempel och tipsen).
# Ordningen = ordningen bland "Vanliga situationer": de vanligaste först. Boss 2026-10-18:
# "Sidan är inte bara för gamers". Adressen /frilans ligger kvar (länkar finns), men ordet
# används inte i texten: "Alla vet inte vad frilans betyder".
MARKNADER = [
    {"slug": "extraknack", "profil": "anstalld", "etikett": "För dig med extraknäck",
     "rubrik": "Deklarationen för dig med lön och lite vid sidan av", "tips": None, "guide": None},
    {"slug": "investerare", "profil": "investerare", "etikett": "För dig med aktier, fonder eller krypto",
     "rubrik": "Deklarationen för dig som sålt aktier eller krypto", "tips": None, "guide": None},
    {"slug": "uthyrning", "profil": "uthyrare", "etikett": "För dig som hyr ut",
     "rubrik": "Deklarationen för dig som hyr ut", "tips": None, "guide": None},
    {"slug": "e-handel", "profil": "ehandel", "etikett": "För dig som säljer på nätet",
     "rubrik": "Deklarationen för dig som säljer på nätet", "tips": None, "guide": None},
    {"slug": "frilans", "profil": "konsult", "etikett": "För dig som säljer tjänster",
     "rubrik": "Deklarationen för dig som fakturerar kunder", "tips": None, "guide": None},
    {"slug": "streamer", "profil": "streamer", "etikett": "För dig som streamar",
     "rubrik": "Deklarationen för dig som streamar",
     "tips": ["Donationer är skattepliktiga", "Utrustningen är avdragsgill", "Prenumerationer och mjukvara"],
     "guide": ("/skatt-for-streamers/", "Guiden: skatt för streamers")},
    {"slug": "youtuber", "profil": "creator", "etikett": "För dig som gör video",
     "rubrik": "Deklarationen för dig som gör video", "tips": None,
     "guide": ("/skatt-for-youtubers/", "Guiden: skatt för youtubers")},
    {"slug": "influencer", "profil": "influencer", "etikett": "För dig som gör samarbeten",
     "rubrik": "Deklarationen för dig som gör samarbeten", "tips": None,
     "guide": ("/skatt-for-influencers/", "Guiden: skatt för influencers")},
]

# Källsidor: adressen man skriver eller klickar från en stream (skattklart.se/twitch).
# Boss 2026-10-18: "många av dom som klickar från en stream är väl inte streamers. Så
# kanske bra o inte anta att dom är streamers". Sidan hälsar på källan, men erbjuder
# samma två val som startsidan; den som själv skapar får en egen länk längre ned.
KALLOR = [
    {"slug": "twitch", "fraga": "Streamar du själv?", "namn": "Twitch", "gor": "streamar", "egen": "/streamer/"},
    {"slug": "kick", "fraga": "Streamar du själv?", "namn": "Kick", "gor": "streamar", "egen": "/streamer/"},
    {"slug": "youtube", "fraga": "Gör du video själv?", "namn": "YouTube", "gor": "gör video", "egen": "/youtuber/"},
    {"slug": "tiktok", "fraga": "Gör du video själv?", "namn": "TikTok", "gor": "gör video", "egen": "/youtuber/"},
]

# Första frågan — samma två val och samma vardagsord som appens startsida (index.html).
VAL = [
    ("privat", "Privatperson",
     "Lön och något mer: sålt aktier, krypto eller bostad, hyr ut eller har sidoinkomster."),
    ("firma", "Enskild firma",
     "Du har en egen firma, till exempel som hantverkare, konsult eller streamer."),
]

# Samma tre steg som appens startsida ("Så funkar det") och llms.txt beskriver.
STEG = [
    ("Svara och ladda upp", "Du svarar på frågor om året och fotar eller laddar upp kvitton."),
    ("Skattklart räknar", "Du får rutorna och bilagorna till Inkomstdeklaration 1, med avdragen framräknade."),
    ("Du lämnar in själv", "Du skriver under med BankID hos Skatteverket. Skattklart lämnar aldrig in åt dig."),
]

CSS = """
:root{--navy:#1a2744;--navy2:#243460;--gold:#f0b429;--gold2:#d99a10;--bg:#f1f3f8;--panel:#fff;
--ink:#1a2744;--dim:#4d5b78;--line:#d8deea;--sidmarg:16px;--bredd:1080px}
/* Sidhuvudet har appens mått: --sidmarg/--bredd = casters.css --sidmarginal/--bredd-max, inpassningen
   = publik.css .pubnav, höjd/märke/ordmärke = casters.css avsnitt 4-5 (V2, 2026-10-20). */
@media (min-width:768px){:root{--sidmarg:24px}}
@media (min-width:1024px){:root{--sidmarg:32px}}
@media (min-width:1280px){:root{--bredd:1200px}}
@media (min-width:1440px){:root{--bredd:1360px}}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--ink);line-height:1.55;overflow-x:hidden}
a{color:inherit}
.topp{background:var(--navy);color:#fff}
.inre{max-width:none;margin:0;padding:0 max(var(--sidmarg),calc((100% - var(--bredd)) / 2))}  /* samma spalt som sidhuvudet och appen: loggan och innehållet linjerar (2026-10-20) */
.topp .inre{display:flex;align-items:center;justify-content:space-between;gap:12px;height:60px;max-width:none;
padding:0 max(var(--sidmarg),calc((100% - var(--bredd)) / 2))}
.logo{display:inline-flex;align-items:center;gap:11px;min-height:44px;text-decoration:none;font-weight:700;font-size:18px;
letter-spacing:-.02em;line-height:1;white-space:nowrap}
.logo-m{width:34px;height:34px;background:var(--gold);border-radius:10px;display:flex;align-items:center;justify-content:center;
flex-shrink:0}
.logo b{color:var(--gold);font-weight:700}
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
/* Tryckytan 44 px som appens --tryckyta; den negativa marginalen håller raden där den var (V8). */
footer a,.kalla a{display:inline-block;padding-block:12px;margin-block:-12px}
/* Sidfoten bryts mellan grupperna, aldrig efter en avgränsare (V7). */
.fotdel{white-space:nowrap}
.val{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.val a{display:block;background:var(--panel);color:var(--ink);border:2px solid var(--line);border-radius:14px;
padding:20px 22px;text-decoration:none}
.hjalte .fraga{font-size:21px;margin:28px 0 12px}
.hjalte .sma{color:rgba(255,255,255,.78)}
.hjalte .sma a{color:#fff}
.val a:hover{border-color:var(--gold2);background:#fff8e6}
.val h3{font-size:21px;margin-bottom:6px}
.val h3::after{content:" →";color:var(--gold2)}
.val p{font-size:15px;color:var(--dim)}
.sma{font-size:15px;color:var(--dim);margin-top:14px}
.sma a{font-weight:600}
:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
@media (max-width:560px){.hjalte{padding-top:30px}.ingress{font-size:16px}.knapp{width:100%;justify-content:center}section{padding:34px 0}}
/* Appens mobilbrytpunkt för sidhuvudet (casters.css @media max-width:600px). */
@media (max-width:600px){.logo{font-size:16px}.logo-m{width:30px;height:30px;border-radius:9px}
.fotskilje{display:none}.fotdel{display:block}}
"""

LOGO = ('<span class="logo-m"><svg viewBox="0 0 46 46" width="72%" height="72%" aria-hidden="true">'
        '<path d="M23 4 L39 10 V23 C39 33 32 40 23 43 C14 40 7 33 7 23 V10 Z" fill="#1a2744"/>'
        '<path d="M15.5 24 l5.5 5.5 L31.5 18" fill="none" stroke="#f0b429" stroke-width="4" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg></span>')


# Anonym räknare (Boss 2026-10-18): ingen kaka och ingen lagring i webbläsaren — bara
# källa och sida skickas till appens /api/t, som räknar per dag. Källan (?fran= eller
# källsidans egen) läggs på länkarna till demot, Kom igång och väntelistan, så att de
# också räknas för den. __STANDARD__ = källsidans slug, annars tomt.
# En adress (2026-10-18): appen ligger på samma värd — /api/t och appens sökvägar
# (/kom-igang, /waitlist, /demo, /demo-login) på location.hostname, inte app.skattklart.se.
RAKNARE = """<script>
(function () {
  var f = (new URLSearchParams(location.search).get('fran') || '__STANDARD__').toLowerCase();
  if (!/^[a-z0-9-]{1,40}$/.test(f)) f = '';
  try {
    navigator.sendBeacon('/api/t', JSON.stringify({fran: f || 'direkt', sida: location.pathname}));
  } catch (e) {}
  if (!f) return;
  var lankar = document.querySelectorAll('a[href]');
  for (var i = 0; i < lankar.length; i++) {
    var u;
    try { u = new URL(lankar[i].href); } catch (e) { continue; }
    if (u.hostname === location.hostname &&
        /^[/](kom-igang|waitlist|demo|demo-login)([/]|$)/.test(u.pathname)) {
      u.searchParams.set('fran', f);
      lankar[i].href = u.toString();
    }
  }
})();
</script>
"""


def raknare(standard=""):
    return RAKNARE.replace("__STANDARD__", standard)


def e(t):
    return html.escape(str(t), quote=True)


def las_profiler():
    with io.open(PROFILER, encoding="utf-8") as f:
        return {p["slug"]: p for p in json.load(f)["profiler"]}


def valblock(fran=None):
    """De två valen + raderna om bara lön och aktiebolag, i toppen av startsidan så att
    första frågan syns utan att scrolla. Valen leder till appens Kom igång-sidor, som
    förklarar stegen för just det valet."""
    kort = "\n".join('    <a href="%s/%s"><h3>%s</h3><p>%s</p></a>' % (KOM_IGANG, s, e(r), e(t))
                      for s, r, t in VAL)
    return """  <h2 class="fraga">Vad ska du deklarera?</h2>
  <div class="val">
%s
  </div>
  <p class="sma">Bara lön? Då räcker ofta Skatteverkets förifyllda deklaration.</p>
  <p class="sma">Har du aktiebolag? Det kommer senare. Din egen privata deklaration kan du göra redan nu.</p>
%s""" % (kort, ('  <p class="sma">%s <a href="%s">Det här gäller för dig</a></p>\n'
              % (e(fran["fraga"]), fran["egen"])
              if fran else ""))


def sida(m, profiler, fran=None):
    """m = marknadspost eller None (den neutrala välkomstsidan). fran = källpost (twitch …):
    då är det startsidan med en hälsning, och den antar inte att besökaren skapar själv."""
    if m:
        p = profiler[m["profil"]]
        sokvag = "/%s/" % m["slug"]
        titel = "Skattklart %s — öppnar snart" % m["etikett"].lower()
        beskr = ("%s. Skattklart räknar fram avdragen och gör deklarationen klar att lämna in själv. "
                 "Öppnar snart — prova demot redan nu." % m["rubrik"])
        etikett, rubrik = m["etikett"], m["rubrik"]
        demo = "%s?exempel=%s" % (DEMO, m["profil"])
        bild, bildalt = "/bilder/produkt-%s.webp" % m["slug"], "Skattklart i demoläge för %s: nästa steg, skatten hittills och avdragstips." % p["namn"].lower()
        valda = m["tips"] or [t["rubrik"] for t in p["tips"][:3]]
        tips = [t for r in valda for t in p["tips"] if t["rubrik"] == r]
        assert len(tips) == len(valda), (m["slug"], valda)
    else:
        sokvag, titel = "/", "Skattklart — deklarationen klar att lämna in. Öppnar snart"
        beskr = ("Skattklart räknar fram avdragen och gör deklarationen klar att lämna in själv med BankID "
                 "hos Skatteverket. Öppnar snart — prova demot redan nu.")
        etikett, rubrik = "Deklaration för privatpersoner och enskild firma", "Din deklaration klar att lämna in"
        demo, bild = DEMOVAL, "/bilder/produkt.webp"
        bildalt = "Skattklart i demoläge: nästa steg, skatten hittills och kommande datum."
        tips = []
    if fran:
        sokvag = "/%s/" % fran["slug"]
        titel = "Skattklart — deklarationen för alla. Öppnar snart"
        beskr = ("Kom du hit från %s? Skattklart hjälper alla som ska deklarera, inte bara den som %s. "
                 "Öppnar snart — prova demot redan nu." % (fran["namn"], fran["gor"]))
        etikett = "Kom du hit från %s?" % fran["namn"]
        rubrik = "Deklarationen för alla, inte bara den som %s" % fran["gor"]
    ingress = ("De flesta som klickar hit från en stream eller en video ska bara deklarera som vanligt. "
               "Skattklart hjälper alla: du med lön och lite vid sidan av, du som sålt aktier eller hyr ut, "
               "och du med egen firma." if fran else
               "Du svarar på frågor om året och laddar upp kvitton. Skattklart räknar och ger dig rutorna och "
               "bilagorna till deklarationen. Du lämnar in själv med BankID hos Skatteverket.")
    vantelista = "%s%s" % (VANTELISTA, ("?fran=" + fran["slug"]) if fran else "")
    # Telefonens bild (V10, 2026-10-20): samma vy tagen i 390 px bredd, så att texten går att läsa.
    bild_mobil = bild.replace(".webp", "-mobil.webp")
    # Källsidorna är varianter av startsidan: kanonisk adress är startsidan.
    kanon = "/" if fran else sokvag

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
%s
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
  <h1>%s%s</h1>
  <p class="ingress">%s</p>
%s  <div class="knappar">
    <a class="knapp" href="%s">Prova demot</a>
    <a class="lank" href="%s">Få besked när vi öppnar</a>
  </div>
  <p class="not">Demot är gratis och kräver inget konto.</p>
  <div class="bild"><picture><source media="(max-width: 600px)" srcset="%s" width="780" height="1440"><img src="%s" width="1600" height="1000" alt="%s"></picture></div>
</div></div>
<p class="bildtext">Bilden visar demot med exempeldata.</p>
""" % (e(titel), e(beskr), BAS, kanon, e(titel), e(beskr), BAS, sokvag, BAS, bild, IKONLANKAR, CSS, LOGO,
       e(etikett), e(rubrik), "" if fran else " <span>— med avdragen du annars missar.</span>", e(ingress),
       "" if m else valblock(fran), demo, vantelista, bild_mobil, bild, e(bildalt)))

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
    <a class="lank" href="%s">Få besked när vi öppnar</a>
  </div>
</div></section>
</main>
<footer><span class="fotdel">© 2026 Skattklart · hej@skattklart.se</span><span class="fotskilje"> · </span><span class="fotdel"><a href="/integritet">Integritetspolicy</a> · <a href="/villkor">Användarvillkor</a></span></footer>
__RAKNARE__</body>
</html>
""" % (' style="padding-top:0"' if tips else "", steg,
       "Fler ingångar" if m else "Vanliga situationer", chips, demo, vantelista))
    return "".join(delar).replace("__RAKNARE__", raknare(fran["slug"] if fran else ""))


# Den egna demosidan (demo/) är borttagen sedan En adress (2026-10-18): /demo är appens
# väljare på samma värd, och en fil här skulle skugga den.

SIDA404 = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sidan finns inte — Skattklart</title>
<meta name="robots" content="noindex">
%s
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


def skriv_ikoner():
    """favicon-32.png och apple-touch-icon.png kopieras ur appen. favicon.ico (16/32/48 px)
    byggs ur appens icon-512.png, för sidor utan <link rel="icon"> och för verktyg som
    bara frågar efter /favicon.ico."""
    for namn in ("favicon-32.png", "apple-touch-icon.png"):
        shutil.copyfile(os.path.join(IKONER, namn), os.path.join(HAR, namn))
        print("kopierade", namn)
    from PIL import Image  # bara här: ta_bilder.py importerar MARKNADER ur den här filen
    with Image.open(os.path.join(IKONER, "icon-512.png")) as bild:
        bild.convert("RGBA").save(os.path.join(HAR, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("skrev favicon.ico")


def git(*arg):
    try:
        r = subprocess.run(["git", "-C", HAR] + list(arg), capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit("bygg.py: git finns inte i PATH — sitemapens lastmod kan inte sättas")
    if r.returncode != 0:
        raise SystemExit("bygg.py: git %s misslyckades: %s" % (" ".join(arg), r.stderr.strip()))
    return r.stdout.strip()


def lastmod(rel):
    """Dagen då filens innehåll senast ändrades. Skiljer den sig från senaste commit (eller är
    ny) är det i dag, annars commitdatumet. Körs efter att sidorna skrivits.
    Bygg och committa samma dag: committas sidorna en senare dag flyttar nästa bygge
    datumen i sitemap.xml till commitdagen (bara sitemapen ändras då)."""
    if not os.path.isfile(os.path.join(HAR, rel)):
        raise SystemExit("bygg.py: %s finns inte men står i sitemapen" % rel)
    if git("status", "--porcelain", "--", rel):
        return datetime.date.today().isoformat()
    datum = git("log", "-1", "--format=%cs", "--", rel)
    if not datum:
        raise SystemExit("bygg.py: git har ingen historik för %s" % rel)
    return datum


def main():
    # Mobilbilderna (<picture>, V10) måste finnas — annars får telefonen en trasig bild.
    saknas = [b for b in ["produkt-mobil.webp"] + ["produkt-%s-mobil.webp" % x["slug"] for x in MARKNADER]
              if not os.path.isfile(os.path.join(HAR, "bilder", b))]
    if saknas:
        raise SystemExit("bygg.py: mobilbilder saknas i bilder/: %s — kör ta_bilder.py" % saknas)
    profiler = las_profiler()
    skriv("index.html", sida(None, profiler))
    for m in MARKNADER:
        skriv("%s/index.html" % m["slug"], sida(m, profiler))
    for k in KALLOR:
        skriv("%s/index.html" % k["slug"], sida(None, profiler, fran=k))
    skriv("404.html", SIDA404 % (IKONLANKAR, CSS, LOGO))
    skriv_ikoner()
    # Välkomstsidornas del av sitemapen. Appens sitemap.xml är ett index som pekar hit och på
    # appens egen del; villkoren (/villkor, /integritet) står där. Startsidan står alltid här.
    sokvagar = ["/"] + ["/%s/" % m["slug"] for m in MARKNADER] + [
        "/skatt-for-streamers/", "/skatt-for-youtubers/", "/skatt-for-influencers/"]
    skriv("sitemap-valkomst.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join("  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>\n"
                    % (BAS, s, lastmod(s.lstrip("/") + "index.html")) for s in sokvagar)
          + "</urlset>\n")
    # Självkontroll: giltig XML, en rad per sökväg och ett datum på varje rad.
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    rader = ET.parse(os.path.join(HAR, "sitemap-valkomst.xml")).getroot().findall("s:url", ns)
    datum = [r.findtext("s:lastmod", namespaces=ns) or "" for r in rader]
    if len(rader) != len(sokvagar) or not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in datum):
        raise SystemExit("bygg.py: sitemap-valkomst.xml blev fel: %d rader, lastmod %s" % (len(rader), datum))
    # En adress: ingen fil eller katalog här får ha en av appens sökvägar (Caddy skuggar då appen).
    krockar = [n for n in APPENS if os.path.exists(os.path.join(HAR, n))]
    if krockar:
        raise SystemExit("bygg.py: %s finns här men är appens sökväg (En adress) — flytta bort" % krockar)
    # Inga länkar till de gamla värdarna (app./demo.skattklart.se 301:ar till skattklart.se).
    for rel in ["index.html", "404.html"] + ["%s/index.html" % x["slug"] for x in MARKNADER + KALLOR]:
        with io.open(os.path.join(HAR, rel), encoding="utf-8") as f:
            if re.search(r"(app|demo)\.skattklart\.se", f.read()):
                raise SystemExit("bygg.py: %s länkar till app./demo.skattklart.se" % rel)


if __name__ == "__main__":
    main()
