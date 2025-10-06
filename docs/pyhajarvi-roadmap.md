# Lake Pyhäjärvi Scenario Roadmap

Tämä etenemissuunnitelma perustuu nykyiseen stubbaavaan toteutukseen, jossa `ScenarioIO.load_initial_conditions` palauttaa kovakoodatun ympäristön ja yhden tilamuuttujan. Tavoitteena on ajaa Lake Pyhäjärvi -skenaario siten, että kaikki tarvittava data luetaan skenaariotiedostosta.

## 1. Lähtötilanteen kartoitus
- **Inventaario skenaariotiedostosta**: selvitä, mitä muuttujia ja aikasarjoja Lake Pyhäjärvi -paketti sisältää (hydrologia, ravinteet, meteorologia jne.). Dokumentoi tiedostomuoto (esim. CSV/Excel/Access) sekä sarakkeiden yksiköt.
- **Mallin minimitarpeet**: kirjaa, mitä tietoja nykyinen `Environment` ja `StateVariable`-rajapinta edellyttää (tilavuus, pinta-ala, syvyys, in-/outflow, alkukonsentraatiot). Tämä auttaa tunnistamaan puuttuvat kentät.
- **Testidata**: eristä pieni testijoukko (esim. 2–3 päivän otos) Pyhäjärvi-aineistosta automatisoituja testejä varten.

## 2. Tietorakenteiden laajennus
- **Ympäristön kuvaus**: laajenna `Environment`-dataclassia tukemaan Pyhäjärven tarvitsemia kenttiä (esim. lämpötila, tuuli, säteily, fraktiot eri syvyyskerroksille). Tarvittaessa lisää uusia dataluokkia erittelemään hydrologian ja meteorologian aikasarjat.
- **Tilamuuttujien määrittely**: toteuta oikeat `StateVariable`-aliluokat (esim. fosfori, typpi, kasviplankton). Määrittele niiden `rate`-funktiot hyödyntämään ympäristön ja forcing-aineiston tietoja.
- **Pakollisten riippuvuuksien abstrahointi**: lisää `typing_ext`-moduuliin tyyppiliitännät (esim. `TimeSeries = Dict[datetime, float]`) selkeyden parantamiseksi.

## 3. Skenaariotiedoston parseri
- **Parsimisrajapinta**: suunnittele `ScenarioIO.load_initial_conditions` ja uusi `ScenarioIO.load_forcing` siten, että ne vastaanottavat polun Pyhäjärven skenaariotiedostoon ja palauttavat 
  - alustavat olosuhteet (`Environment`, lista `StateVariable`-olioita)
  - forcing-aineiston (esim. valon, lämpötilan, sisään tulevien ravinteiden aikasarjat)
- **Modulaarinen parseri**: rakenna alakohtaiset funktiot (esim. `parse_hydrology`, `parse_meteorology`, `parse_chemistry`) joiden yksikkökonversiot ja validoinnit ovat selkeästi eriytetty.
- **Validointi ja virheilmoitukset**: lisää tarkistuksia (puuttuvat sarakkeet, väärät yksiköt) ja nosta informatiiviset poikkeukset, jotta dataongelmat löytyvät nopeasti.

## 4. Simulaatiosilmukan päivitys
- **Aikasarjojen interpolointi**: korvaa nykyinen "täsmällinen osuma"-logiikka `Environment.get_inflow/outflow` -metodeissa ja `Utils.interpolate_series` -apufunktiossa sopivalla interpoloinnilla (esim. lineaarinen) tai aikavälin keskiarvolla.
- **Veden tasapainotus**: varmista, että simulaatio käyttää Pyhäjärven datasta johdettuja virtaamia sekä mahdollisia ulkoisia kuormituksia (esim. point-source-virtaamat).
- **Tilamuuttujien integraatio**: varmista, että solver päivittää kaikki biologiset ja kemialliset tilat käyttäen forcing-aikasarjoja ja mahdollisesti useampia kerroksia (epilimnion/metalimnion/hypolimnion).

## 5. Testaus ja validointi
- **Yksikkötestit**: kirjoita testit `ScenarioIO`-parserille, jotka vertaavat parserin tuloksia tunnettuun referenssiin (esim. stub-dataan). Käytä `pytest`-rakennetta.
- **Integraatiotesti**: lisää testi, joka ajaa lyhyen (esim. viikon mittaisen) Pyhäjärvi-simulaation ja tarkistaa tunnusluvut (tilavuus, ravinnepitoisuudet) referenssiarvoihin.
- **Regressiotestaus**: lisää mahdollisuus tallentaa simulaation tulos (esim. CSV) ja verrata sitä referenssidataan toleranssilla.

## 6. Käyttöliittymä ja dokumentaatio
- **Komentorivityökalu**: laajenna `main.py` ottamaan skenaariotiedoston polku argumenttina ja tarjoamaan parametreja (simulaation kesto, askelpituus).
- **README-päivitykset**: dokumentoi, miten Pyhäjärvi-skenaario ajetaan, mitä riippuvuuksia tarvitaan (esim. pandas, numpy) ja miten testit suoritetaan.
- **Tuotetut tiedostot**: määrittele oletuspolut tulosteille (esim. `outputs/pyhajarvi.csv`) ja varmista, ettei ne päädy versionhallintaan.

## 7. Jatkokehitys
- **Suorituskyky**: harkitse vektorointia (numpy/pandas) tai tehokkaampaa ODE-ratkaisijaa, jos skenaariot ovat pitkiä.
- **Parametrien kalibrointi**: lisää mahdollisuus lukea kalibrointiparametrit erillisestä konfiguraatiosta.
- **GUI tai web-käyttöliittymä**: projektin myöhemmässä vaiheessa voidaan rakentaa käyttöliittymä tulosten visualisoimiseksi.

Tämä etenemissuunnitelma antaa konkreettiset työpaketit, joiden avulla stubbaus voidaan korvata tuotantokelpoisella Pyhäjärvi-skenaarion lukemiseen ja ajamiseen kykenevällä toteutuksella.
