from datenbank import DATACONNECT
import calendar

class GERAETE(DATACONNECT):
    def __init__(self):
        super().__init__()
        self.verbindeDatenbank()
        self.setZeitraum(7, 2025)
        self.get_C3()
        self.get_C3T()
        self.get_CPR()
        self.get_C1()
        self.get_AED()
        self.get_Servicescheine()
        self.get_C3_C1_Gebraucht()
        self.get_AED_Gebraucht()
        #self.set_Accessoires()
        ##########################################
        self.get_CPR_AU()
        self.get_C1_AU()
        self.get_AED_AU()
        self.get_C3_AU()
        self.get_C3T_AU()
        self.get_C3_C1_Gebraucht_AU()
        self.get_AED_Gebraucht_AU()
        self.getSummen()
        self.schließeDatenbank()

    def setZeitraum(self, monat, jahr):
        self.monat = int(monat)
        self.jahr = int(jahr)

        anzahl_tage = calendar.monthrange(self.jahr, self.monat)[1]

        tage = [
            f"{self.jahr}-{str(self.monat).zfill(2)}-{str(tag).zfill(2)}"
            for tag in range(1, anzahl_tage + 1)
        ]

        self.MonatDaten = {
            "start": f"{self.jahr}-{str(self.monat).zfill(2)}-01 00:00:00",
            "ende": f"{self.jahr}-{str(self.monat).zfill(2)}-{anzahl_tage} 23:59:59",
            "tage": tage
        }

        self.DatumVon = self.MonatDaten["start"]
        self.DatumBis = self.MonatDaten["ende"]
        print(f"Zeitraum: {self.DatumVon} - {self.DatumBis}")

############################################################################################
######## Neugeräte Order Entry ###########       

    def get_CPR_AU(self):
        Artikel = ('09100',)
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_CPR_AU = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_C1_AU(self):
        Artikel = ('05100',)
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_C1_AU = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_AED_AU(self):
        artikel_liste = ('06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_AED_AU = self.getData(artikel_liste, ausgeschlossen, Filiale, Belegart)

    def get_C3_AU(self):
        Artikel = ('04100', '04200', '04301', '04300')
        ausgeschlossen = ('04101', '04201', '04302', '06101.10')
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_C3_AU = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_C3T_AU(self):
        Artikel = ('04101', '04201', '04302',)
        ausgeschlossen = ('04100', '04200', '04301', '04300', '06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_C3T_AU = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

############################################################################################
######## Neugeräte Sales ###########

    def get_CPR(self):
        Artikel = ('09100',)
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_CPR = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_C1(self):
        Artikel = ('05100',)
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_C1 = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_AED(self):
        artikel_liste = ('06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        ausgeschlossen = ('04100',)
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_AED = self.getData(artikel_liste, ausgeschlossen, Filiale, Belegart)

    def get_C3(self):
        Artikel = ('04100', '04200', '04301', '04300')
        ausgeschlossen = ('04101', '04201', '04302', '06101.10')
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_C3 = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_C3T(self):
        Artikel = ('04101', '04201', '04302',)
        ausgeschlossen = ('04100', '04200', '04301', '04300')
        Filiale = '7'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_C3T = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def set_Accessoires(self):
        ausgeschlossen = ('04100', '04200', '04300', '04301', '04101', '04201', '04302', '06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        self.Summe_Accessoires = self.get_Accessories(ausgeschlossen)

########################################################################################################
########## Gebrauchtgeräte ###########

    def get_C3_C1_Gebraucht(self):
        Artikel = ('04100', '04200', '04301', '04300','05100')
        ausgeschlossen = ('04101', '04201', '04302', '06101.10')
        Filiale = '8'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'RE'
        self.Summe_C3_C1_refurbed = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_AED_Gebraucht(self):
        artikel_liste = ('06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        ausgeschlossen = ('04100',)
        Filiale = '8'  
        Belegart = 'RE'
        self.Summe_AED_Gebraucht = self.getData(artikel_liste, ausgeschlossen, Filiale, Belegart)

    def get_C3_C1_Gebraucht_AU(self):
        Artikel = ('04100', '04200', '04301', '04300','05100')
        ausgeschlossen = ('04101', '04201', '04302', '06101.10')
        Filiale = '8'  # Beispiel für Filiale, kann angepasst werden
        Belegart = 'AU'
        self.Summe_C3_C1_refurbed_AU = self.getData(Artikel, ausgeschlossen, Filiale, Belegart)

    def get_AED_Gebraucht_AU(self):
        artikel_liste = ('06100', "06100.10", "06100.11", "06100.20", "06100.21", 
                        "06101.10", "06101.11", "06101.20", "06101.21")
        ausgeschlossen = ('04100',)
        Filiale = '8'  
        Belegart = 'AU'
        self.Summe_AED_Gebraucht_AU = self.getData(artikel_liste, ausgeschlossen, Filiale, Belegart)

########################################################################################################
########## Datenlogic ###########

    def getData(self, Artikel, ausgeschlossen, Filiale, Belegart):
        cursor = None

        try:
            cursor = self.conn.cursor()

            # Umwandeln in SQL-kompatibles Format: '06100', '06100.10', ...
            artikel_sql = ', '.join(f"'{a}'" for a in Artikel)

            sql = f"""
                SELECT DISTINCT b.BELEGNR, b.STWERT1
                FROM BELEG b
                JOIN BELEGPOS p ON b.BELEGNR = p.BELEGNR
                WHERE b.BELEGART = '{Belegart}'
                AND b.FILIALE = '{Filiale}'
                AND b.BELEGDAT BETWEEN '{self.DatumVon}' AND '{self.DatumBis}'
                AND p.ARTIKELNR IN ({artikel_sql})
                AND p.KZDRUCK NOT LIKE 'A'
                AND NOT EXISTS (
                    SELECT 1
                    FROM BELEGPOS p2
                    WHERE p2.BELEGNR = b.BELEGNR
                        AND (
                            p2.ARTIKELNR LIKE 'L06%' OR
                            p2.ARTIKELNR LIKE 'L05%' OR
                            p2.ARTIKELNR IN ({', '.join(f"'{a}'" for a in ausgeschlossen)})
                        )
                )
            """


            cursor.execute(sql)
            geraete_info = cursor.fetchall()

            print(f"Gefundene Belege für Artikel {Artikel}:")
            for eintrag in geraete_info:
                print(f"{eintrag}")
                print(50* "-")


            liste_c3 = []

            for eintrag in geraete_info:
                wert = str(eintrag[1])
                liste_c3.append(wert)

            print(f"Liste:", liste_c3)

            # Nur numerische Werte summieren
            gesamt = sum(float(x) for x in liste_c3 if isinstance(x, str) and x.replace('.', '', 1).isdigit())
            print(f"Gesamtwert: {gesamt}")
            print(50*"#")
            return gesamt




        except Exception as e:
            print(f"Fehler beim Abrufen der Geräteinformationen: {e}")
        finally:
            if cursor:
                cursor.close()

    def get_Accessories(self, ausgeschlossen):
        cursor = None
        liste_accessories = []

        try:
            cursor = self.conn.cursor()

            # Dynamische Platzhalter für IN-Klausel
            excluded_placeholders = ', '.join(['?'] * len(ausgeschlossen))

            sql = f"""
                SELECT b.BELEGNR, b.STWERT1
                FROM BELEG b
                WHERE b.BELEGART = 'RE'
                AND b.FILIALE = '0'
                AND b.BELEGDAT BETWEEN ? AND ?
                AND b.VERSNDART = '95'
                AND b.LONR IS NOT NULL
                AND b.LONR <> ''
                AND EXISTS (
                    SELECT 1
                    FROM BELEGPOS p
                    WHERE p.BELEGNR = b.BELEGNR
                        AND p.KZDRUCK <> 'A'
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM BELEGPOS p2
                    WHERE p2.BELEGNR = b.BELEGNR
                        AND (
                            p2.ARTIKELNR STARTING WITH 'L06' OR
                            p2.ARTIKELNR STARTING WITH 'L05' OR
                            p2.ARTIKELNR IN ({excluded_placeholders})
                        )
                )
            """

            params = [self.DatumVon, self.DatumBis] + list(ausgeschlossen)

            cursor.execute(sql, params)
            accessories_info = cursor.fetchall()

            print("Gefundene Zubehör-Belege:")
            for belegnr, stwert1 in accessories_info:
                wert_str = str(stwert1)
                print(f"Beleg: {belegnr}, Wert: {wert_str}")
                liste_accessories.append(wert_str)

            # Summiere gültige Werte
            self.gesamt_accessories = sum(
                float(x.replace(',', '.')) for x in liste_accessories
                if isinstance(x, str) and x.replace(',', '.').replace('.', '', 1).isdigit()
            )

            print(f"Liste Zubehör: {liste_accessories}")
            print(f"Gesamtwert Zubehör: {self.gesamt_accessories}")
            return self.gesamt_accessories

        except Exception as e:
            print(f"Fehler beim Abrufen der Zubehör-Belege: {e}")
            return 0.0

        finally:
            if cursor:
                cursor.close()
                


    def get_Servicescheine(self):
        cursor = None
        liste_mo = []

        try:
            cursor = self.conn.cursor()

            sql = f"""
                SELECT b.BELEGNR, b.STWERT1
                FROM BELEG b
                WHERE b.BELEGART = 'MO'
                AND b.BELEGDAT BETWEEN '{self.DatumVon}' AND '{self.DatumBis}'
            """

            cursor.execute(sql)
            servicescheine = cursor.fetchall()

            
            for eintrag in servicescheine:
                wert = str(eintrag[1])
                
                liste_mo.append(wert)
            self.gesamt = sum(float(x) for x in liste_mo if isinstance(x, str) and x.replace('.', '', 1).isdigit())
            return self.gesamt

        except Exception as e:
            print(f"Fehler beim Abrufen der Servicescheine: {e}")

        finally:
            if cursor:
                cursor.close()
        
    
    def getSummen (self):
        print(50*"#")
        print("Order Entry:")
        print()
        print("AED:", self.Summe_AED_AU)
        print("CPR:", self.Summe_CPR_AU)
        print("C1:", self.Summe_C1_AU)
        print("C3:", self.Summe_C3_AU)
        print("C3T:", self.Summe_C3T_AU)
        print("cosinuss sensor")
        print("Accessories")
        print("Service")
        print("Software")
        print("RF AED:", self.Summe_AED_Gebraucht_AU)
        print("RF c3/c1:", self.Summe_C3_C1_refurbed_AU)
        print()
        print(50 * "-")
        print()
        print("Sales")
        print()
        print("AED:", self.Summe_AED)
        print("CPR:", self.Summe_CPR)
        print("C1:", self.Summe_C1)
        print("C3:", self.Summe_C3)
        print("C3T:", self.Summe_C3T)
        print("cosinuss sensor")
        print("Accessories")
        print("Servicescheine:", self.get_Servicescheine())
        print("RF AED:", self.Summe_AED_Gebraucht)
        print("RF c3/c1:", self.Summe_C3_C1_refurbed)
        
        

if __name__ == "__main__":
    c3 = GERAETE()
