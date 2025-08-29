import sqlite3
import calendar
from typing import Iterable, Sequence, Tuple, Optional

class GERAETE_SQLite:
    def __init__(self, sqlite_path: str = "export.db"):
        self.db_path = sqlite_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self.setZeitraum(8, 2025)  # Beispiel; kannst du natürlich ändern

        # Abrufe (Reihenfolge wie bei dir)
        self.get_C3()
        self.get_C3T()
        self.get_CPR()
        self.get_C1()
        self.get_AED()
        self.get_Cosinuss()
        self.get_Software()
        self.get_Servicescheine()
        self.get_C3_C1_Gebraucht()
        self.get_AED_Gebraucht()

        self.get_CPR_AU()
        self.get_C1_AU()
        self.get_AED_AU()
        self.get_Cosinuss_AU()
        self.get_C3_AU()
        self.get_C3T_AU()
        self.get_Software_AU()
        self.get_C3_C1_Gebraucht_AU()
        self.get_AED_Gebraucht_AU()

        self.getSummen()
        self.close()

    # ---------------- Basis ----------------
    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def setZeitraum(self, monat: int, jahr: int):
        self.monat = int(monat); self.jahr = int(jahr)
        anzahl_tage = calendar.monthrange(self.jahr, self.monat)[1]
        self.DatumVon = f"{self.jahr}-{str(self.monat).zfill(2)}-01 00:00:00"
        self.DatumBis = f"{self.jahr}-{str(self.monat).zfill(2)}-{anzahl_tage} 23:59:59"
        print(f"Zeitraum: {self.DatumVon} - {self.DatumBis}")

    # ---------------- Utils ----------------
    def _col_exists(self, table: str, col: str) -> bool:
        cur = self.conn.execute(f"PRAGMA table_info({table})")
        return any(r["name"].lower() == col.lower() for r in cur.fetchall())

    def _sum_float_strings(self, values: Sequence[object]) -> float:
        total = 0.0
        for v in values:
            if v is None: 
                continue
            s = str(v).replace(",", ".")
            try:
                total += float(s)
            except ValueError:
                pass
        return total

    # Kern-Abfrage: RE/AU Summen mit Artikel-Whitelist & Ausschlüssen
    def _sum_by_articles(
        self, artikel: Sequence[str], ausgeschlossen: Sequence[str], filiale: str, belegart: str
    ) -> float:
        """
        Sucht in beleg/belegpos:
          - beleg.belegart = ?
          - filiale (bevorzugt aus belegpos.filiale, sonst beleg.filiale)
          - Datumsfilter: bevorzugt belegpos.createdatum, sonst beleg.belegdat
          - p.artikelnr IN (…)
          - p.kzdruck <> 'A'
          - NOT EXISTS: p2.artikelnr LIKE 'L06%'/'L05%' oder IN (ausgeschlossen)
        Gibt Summe von beleg.stwert1 als float zurück (STWERT1 sind Beträge in BELEG).
        """
        has_createdatum = self._col_exists("belegpos", "createdatum")
        has_filiale_pos = self._col_exists("belegpos", "filiale")

        # Dynamische WHERE-Bausteine
        date_col = "p.createdatum" if has_createdatum else "b.belegdat"
        fil_col  = "p.filiale"     if has_filiale_pos else "b.filiale"

        artikel_in_q = ",".join("?" for _ in artikel)
        excl_in_q    = ",".join("?" for _ in ausgeschlossen) if ausgeschlossen else None

        sql = f"""
            SELECT DISTINCT b.belegnr, b.stwert1
            FROM beleg b
            JOIN belegpos p ON p.belegnr = b.belegnr
            WHERE b.belegart = ?
              AND {fil_col} = ?
              AND {date_col} BETWEEN ? AND ?
              AND p.artikelnr IN ({artikel_in_q})
              AND (p.kzdruck IS NULL OR p.kzdruck <> 'A')
              AND NOT EXISTS (
                  SELECT 1
                  FROM belegpos p2
                  WHERE p2.belegnr = b.belegnr
                    AND (
                        p2.artikelnr LIKE 'L06%' OR
                        p2.artikelnr LIKE 'L05%'{" OR p2.artikelnr IN (" + excl_in_q + ")" if excl_in_q else ""}
                    )
              )
        """

        params = [belegart, filiale, self.DatumVon, self.DatumBis, *artikel]
        if ausgeschlossen:
            params += list(ausgeschlossen)

        rows = self.conn.execute(sql, params).fetchall()
        return self._sum_float_strings([r["stwert1"] for r in rows])

    # Software-Summen (Artikel 970%)
    def _sum_software(self, belegart: str) -> float:
        has_createdatum = self._col_exists("belegpos", "createdatum")
        has_filiale_pos = self._col_exists("belegpos", "filiale")

        date_col = "p.createdatum" if has_createdatum else "b.belegdat"
        fil_filter = f"p.filiale = '0'" if has_filiale_pos else "b.filiale = '0'"

        sql = f"""
            SELECT p.belegnr, p.gesamt
            FROM belegpos p
            JOIN beleg b ON b.belegnr = p.belegnr
            WHERE {date_col} BETWEEN ? AND ?
              AND b.belegart = ?
              AND {fil_filter}
              AND p.artikelnr LIKE '970%'
        """
        rows = self.conn.execute(sql, [self.DatumVon, self.DatumBis, belegart]).fetchall()
        return self._sum_float_strings([r["gesamt"] for r in rows])

    # Servicescheine (MO) – Summe STWERT1 aus BELEG
    def _sum_servicescheine(self) -> float:
        sql = """
            SELECT b.stwert1
            FROM beleg b
            WHERE b.belegart = 'MO'
              AND b.belegdat BETWEEN ? AND ?
        """
        rows = self.conn.execute(sql, [self.DatumVon, self.DatumBis]).fetchall()
        return self._sum_float_strings([r["stwert1"] for r in rows])

    # ---------------- Fachfunktionen (wie bei dir) ----------------
    # Order Entry (AU)
    def get_CPR_AU(self):
        self.Summe_CPR_AU = self._sum_by_articles(('09100',), ('04100','04101'), '7', 'AU')

    def get_C1_AU(self):
        self.Summe_C1_AU = self._sum_by_articles(('05100',), ('04100','04101'), '7', 'AU')

    def get_AED_AU(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21",
                   "06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_AU = self._sum_by_articles(artikel, ('04100','04101'), '7', 'AU')

    def get_Cosinuss_AU(self):
        artikel = ('15121.101L','15121.101M','15121.101S','15122.101SM','15123.101SM')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_Cosinus_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_C3_AU(self):
        artikel = ('04100','04200','04301','04300')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_C3T_AU(self):
        artikel = ('04101','04201','04302')
        excl = ('04100','04200','04301','04300',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3T_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_Software_AU(self):
        self.Summe_Software_AU = self._sum_software('AU')

    # Sales (RE)
    def get_CPR(self):
        self.Summe_CPR = self._sum_by_articles(('09100',), ('04100','04101'), '7', 'RE')

    def get_C1(self):
        self.Summe_C1 = self._sum_by_articles(('05100',), ('04100','04101'), '7', 'RE')

    def get_Cosinuss(self):
        artikel = ('15121.101L','15121.101M','15121.101S','15122.101SM','15123.101SM')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_Cosinus = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_AED(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21",
                   "06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED = self._sum_by_articles(artikel, ('04100','04101'), '7', 'RE')

    def get_C3(self):
        artikel = ('04100','04200','04301','04300')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3 = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_C3T(self):
        artikel = ('04101','04201','04302')
        excl = ('04100','04200','04301','04300',"06100","06100.10","06100.11","06100.20","06100.21",
                "06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3T = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_Software(self):
        self.Summe_Software = self._sum_software('RE')

    # Gebrauchtgeräte (RE/AU)
    def get_C3_C1_Gebraucht(self):
        artikel = ('04100','04200','04301','04300','05100')
        self.Summe_C3_C1_refurbed = self._sum_by_articles(artikel, ('04101','04201','04302','06101.10'), '8', 'RE')

    def get_AED_Gebraucht(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21",
                   "06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_Gebraucht = self._sum_by_articles(artikel, ('04100',), '8', 'RE')

    def get_C3_C1_Gebraucht_AU(self):
        artikel = ('04100','04200','04301','04300','05100')
        self.Summe_C3_C1_refurbed_AU = self._sum_by_articles(artikel, ('04101','04201','04302','06101.10'), '8', 'AU')

    def get_AED_Gebraucht_AU(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21",
                   "06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_Gebraucht_AU = self._sum_by_articles(artikel, ('04100',), '8', 'AU')

    # Servicescheine (MO)
    def get_Servicescheine(self):
        self.gesamt_servicescheine = self._sum_servicescheine()
        return self.gesamt_servicescheine

    # Summenausgabe
    def getSummen(self):
        print(50*"#")
        print("Order Entry:")
        print("AED:", getattr(self, "Summe_AED_AU", 0.0))
        print("CPR:", getattr(self, "Summe_CPR_AU", 0.0))
        print("C1:", getattr(self, "Summe_C1_AU", 0.0))
        print("C3:", getattr(self, "Summe_C3_AU", 0.0))
        print("C3T:", getattr(self, "Summe_C3T_AU", 0.0))
        print("cosinuss sensor:", getattr(self, "Summe_Cosinus_AU", 0.0))
        print("Software:", getattr(self, "Summe_Software_AU", 0.0))
        print("RF AED:", getattr(self, "Summe_AED_Gebraucht_AU", 0.0))
        print("RF c3/c1:", getattr(self, "Summe_C3_C1_refurbed_AU", 0.0))
        print(50*"-")
        print("Sales")
        print("AED:", getattr(self, "Summe_AED", 0.0))
        print("CPR:", getattr(self, "Summe_CPR", 0.0))
        print("C1:", getattr(self, "Summe_C1", 0.0))
        print("C3:", getattr(self, "Summe_C3", 0.0))
        print("C3T:", getattr(self, "Summe_C3T", 0.0))
        print("cosinuss sensor:", getattr(self, "Summe_Cosinus", 0.0))
        print("Servicescheine:", getattr(self, "gesamt_servicescheine", 0.0))
        print("Software:", getattr(self, "Summe_Software", 0.0))
        print("RF AED:", getattr(self, "Summe_AED_Gebraucht", 0.0))
        print("RF c3/c1:", getattr(self, "Summe_C3_C1_refurbed", 0.0))


if __name__ == "__main__":
    app = GERAETE_SQLite()  # nutzt export.db
