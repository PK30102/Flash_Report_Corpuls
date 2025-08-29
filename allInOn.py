# all_in_one_accessories.py
# -*- coding: utf-8 -*-

import os
import sqlite3
import calendar
from contextlib import closing
from datetime import datetime, date, time
from typing import Iterable, Tuple, Any, List, Dict, Optional, Sequence
from dotenv import load_dotenv

# =========================
# Konfiguration
# =========================
SQLITE_PATH = "export.db"
BATCH_SIZE  = 5000

# PRAGMAs: maximal schnell/schonend; für mehr Robustheit: WAL/NORMAL
SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "OFF",
    "synchronous": "OFF",
    "temp_store": "MEMORY",
    "cache_size": "-20000",   # ~20 MB Cache (negativ = KB)
    "locking_mode": "EXCLUSIVE",
}

# =========================
# Firebird-Verbindung
# =========================
class FirebirdConnect:
    def __init__(self):
        self.conn = None
        load_dotenv()

    def connect(self):
        dsn = os.getenv("dsn")
        user = os.getenv("user")
        password = os.getenv("password")
        charset = os.getenv("charset", "UTF8")
        if not all([dsn, user, password]):
            raise RuntimeError("Umgebungsvariablen dsn/user/password fehlen in .env")

        # Erst firebird-driver, dann fdb
        try:
            import firebird.driver as fbd
            dpb = {}
            if charset: dpb["charset"] = charset
            self.conn = fbd.connect(dsn=dsn, user=user, password=password, **dpb)
            self.driver = "firebird-driver"
        except Exception as e1:
            try:
                import fdb
                self.conn = fdb.connect(dsn=dsn, user=user, password=password, charset=charset)
                self.driver = "fdb"
            except Exception as e2:
                raise RuntimeError(f"Firebird-Connect fehlgeschlagen:\n - firebird-driver: {e1}\n - fdb: {e2}")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

# =========================
# Gemeinsame Helfer
# =========================
def month_bounds(jahr: int, monat: int):
    """liefert (start, end) als Strings – halb-offenes Intervall [start, end)"""
    from datetime import datetime as dt
    start = dt(jahr, monat, 1, 0, 0, 0)
    end = dt(jahr+1, 1, 1, 0, 0, 0) if monat == 12 else dt(jahr, monat+1, 1, 0, 0, 0)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")

def to_iso(v: Any) -> Any:
    if isinstance(v, datetime): return v.isoformat(sep=" ")
    if isinstance(v, date):     return v.isoformat()
    if isinstance(v, time):     return v.isoformat()
    return v

def to_float_safe(v: Any) -> Optional[float]:
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(",", ".")
    try: return float(s)
    except ValueError: return None

def stream_fetch(cur, fetchsize: int) -> Iterable[Tuple[Any, ...]]:
    while True:
        rows = cur.fetchmany(fetchsize)
        if not rows: break
        for r in rows: yield r

# =========================
# Exporter: Firebird -> SQLite
# =========================
class DatabaseSynchronizer(FirebirdConnect):
    SQL_BELEG = """
        SELECT b.BELEGTYP, b.BELEGART, b.BELEGNR, b.STWERT1, b.FILIALE, b.BELEGDAT, b.VERSNDART, b.LONR
        FROM BELEG b
        WHERE b.BELEGDAT >= ? AND b.BELEGDAT < ?
    """

    # POS via Beleg verbinden; Export deckt beide Welten ab:
    # - Positionen mit Belegdatum im Monat ODER mit Createdatum im Monat
    SQL_BELEGPOS = """
        SELECT p.BELEGTYP, p.BELEGART, p.BELEGNR, p.GESAMT, p.KZDRUCK, p.ARTIKELNR, p.CREATEDATUM, p.FILIALE
        FROM BELEGPOS p
        JOIN BELEG b ON b.BELEGNR = p.BELEGNR
        WHERE (b.BELEGDAT   >= ? AND b.BELEGDAT   < ?)
           OR (p.CREATEDATUM >= ? AND p.CREATEDATUM < ?)
    """

    def __init__(self):
        super().__init__()
        self.connect()
        self.DatumVon = None
        self.DatumBis = None

    def setZeitraum(self, monat: int, jahr: int):
        self.DatumVon, self.DatumBis = month_bounds(jahr, monat)
        print(f"[SYNC] Zeitraum: {self.DatumVon} bis < {self.DatumBis}")

    def _prepare_sqlite(self) -> sqlite3.Connection:
        if os.path.exists(SQLITE_PATH):
            os.remove(SQLITE_PATH)  # frische DB
        con = sqlite3.connect(SQLITE_PATH)
        con.execute("PRAGMA foreign_keys = ON;")
        for k, v in SQLITE_PRAGMAS.items():
            con.execute(f"PRAGMA {k} = {v};")
        schema = """
        CREATE TABLE IF NOT EXISTS beleg (
            belegtyp   TEXT,
            belegart   TEXT,
            belegnr    TEXT,
            stwert1    REAL,    -- REAL
            filiale    TEXT,
            belegdat   TEXT,
            versndart  TEXT,
            lonr       TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_beleg_datum ON beleg(belegdat);
        CREATE INDEX IF NOT EXISTS ix_beleg_nr    ON beleg(belegnr);

        CREATE TABLE IF NOT EXISTS belegpos (
            belegtyp    TEXT,
            belegart    TEXT,
            belegnr     TEXT,
            gesamt      REAL,   -- REAL
            kzdruck     TEXT,
            artikelnr   TEXT,
            createdatum TEXT,
            filiale     TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_belegpos_nr   ON belegpos(belegnr);
        CREATE INDEX IF NOT EXISTS ix_belegpos_date ON belegpos(createdatum);
        """
        con.executescript(schema)
        return con

    def _normalize_row_beleg(self, row: Tuple[Any, ...]) -> Tuple[Any, ...]:
        (belegtyp, belegart, belegnr, stwert1, filiale, belegdat, versndart, lonr) = row
        return (
            None if belegtyp  is None else str(belegtyp).strip(),
            None if belegart  is None else str(belegart).strip(),
            None if belegnr   is None else str(belegnr).strip(),
            to_float_safe(stwert1),
            None if filiale   is None else str(filiale).strip(),
            to_iso(belegdat),
            None if versndart is None else str(versndart).strip(),
            None if lonr      is None else str(lonr).strip(),
        )

    def _normalize_row_pos(self, row: Tuple[Any, ...]) -> Tuple[Any, ...]:
        (belegtyp, belegart, belegnr, gesamt, kzdruck, artikelnr, createdatum, filiale) = row
        return (
            None if belegtyp  is None else str(belegtyp).strip(),
            None if belegart  is None else str(belegart).strip(),
            None if belegnr   is None else str(belegnr).strip(),
            to_float_safe(gesamt),
            None if kzdruck   is None else str(kzdruck).strip().upper(),
            None if artikelnr is None else str(artikelnr).strip().upper(),
            to_iso(createdatum),
            None if filiale   is None else str(filiale).strip(),
        )

    def run(self):
        if not (self.DatumVon and self.DatumBis):
            raise ValueError("Zeitraum nicht gesetzt. Rufe setZeitraum(monat, jahr) zuerst auf.")

        fb_cur1 = self.conn.cursor()
        fb_cur2 = self.conn.cursor()
        try:
            try:
                fb_cur1.arraysize = BATCH_SIZE
                fb_cur2.arraysize = BATCH_SIZE
            except Exception:
                pass

            sq = self._prepare_sqlite()
            with closing(sq):

                # -------- BELEG --------
                fb_cur1.execute(self.SQL_BELEG, (self.DatumVon, self.DatumBis))
                insert_beleg = """
                    INSERT INTO beleg (belegtyp, belegart, belegnr, stwert1, filiale, belegdat, versndart, lonr)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                total_beleg = 0
                with sq:
                    batch: List[Tuple[Any, ...]] = []
                    for row in stream_fetch(fb_cur1, BATCH_SIZE):
                        batch.append(self._normalize_row_beleg(tuple(row)))
                        if len(batch) >= BATCH_SIZE:
                            sq.executemany(insert_beleg, batch); total_beleg += len(batch); batch.clear()
                    if batch:
                        sq.executemany(insert_beleg, batch); total_beleg += len(batch)

                # -------- BELEGPOS --------
                fb_cur2.execute(self.SQL_BELEGPOS, (self.DatumVon, self.DatumBis, self.DatumVon, self.DatumBis))
                insert_belegpos = """
                    INSERT INTO belegpos (belegtyp, belegart, belegnr, gesamt, kzdruck, artikelnr, createdatum, filiale)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                total_belegpos = 0
                with sq:
                    batch2: List[Tuple[Any, ...]] = []
                    for row in stream_fetch(fb_cur2, BATCH_SIZE):
                        batch2.append(self._normalize_row_pos(tuple(row)))
                        if len(batch2) >= BATCH_SIZE:
                            sq.executemany(insert_belegpos, batch2); total_belegpos += len(batch2); batch2.clear()
                    if batch2:
                        sq.executemany(insert_belegpos, batch2); total_belegpos += len(batch2)

                with sq:
                    sq.execute("PRAGMA case_sensitive_like=ON;")
                    sq.execute("ANALYZE;")

            print(f"[OK] Export fertig → {os.path.abspath(SQLITE_PATH)}")
            print(f"     BELEG:    {total_beleg} Zeilen")
            print(f"     BELEGPOS: {total_belegpos} Zeilen")

        finally:
            self.close()

# =========================
# Auswertung auf SQLite (inkl. Accessories)
# =========================
class GERAETE_SQLite:
    def __init__(self, sqlite_path: str = SQLITE_PATH):
        self.db_path = sqlite_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()

        # Zeitraum beispielhaft, im main ändern
        self.setZeitraum(8, 2025)

        # Abrufe (wie bei dir)
        self.get_C3(); self.get_C3T(); self.get_CPR(); self.get_C1(); self.get_AED()
        self.get_Cosinuss(); self.get_Software(); self.get_Servicescheine()
        self.get_C3_C1_Gebraucht(); self.get_AED_Gebraucht()
        self.get_CPR_AU(); self.get_C1_AU(); self.get_AED_AU()
        self.get_Cosinuss_AU(); self.get_C3_AU(); self.get_C3T_AU()
        self.get_Software_AU(); self.get_C3_C1_Gebraucht_AU(); self.get_AED_Gebraucht_AU()
        self.set_Accessoires()  # Accessories jetzt aktiv
        self.getSummen()
        self.close()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA case_sensitive_like=ON;")

    def close(self):
        if self.conn:
            self.conn.close(); self.conn = None

    def setZeitraum(self, monat: int, jahr: int):
        self.DatumVon, self.DatumBis = month_bounds(jahr, monat)
        print(f"[SQLITE] Zeitraum: {self.DatumVon} bis < {self.DatumBis}")

    # --- Utils ---
    def _sum_float(self, vals: Sequence[Optional[float]]) -> float:
        return float(sum(v for v in vals if isinstance(v, (int, float))))

    # Kern-Summen: RE/AU nach Artikeln (Beleg-Filter, KZDRUCK/Exclusions wie Firebird)
    def _sum_by_articles(self, artikel: Sequence[str], ausgeschlossen: Sequence[str], filiale: str, belegart: str) -> float:
        artikel = tuple(a.strip().upper() for a in artikel)
        ausgeschlossen = tuple(a.strip().upper() for a in ausgeschlossen)
        artikel_in_q = ",".join("?" for _ in artikel)
        excl_in_q    = ",".join("?" for _ in ausgeschlossen) if ausgeschlossen else None

        sql = f"""
            SELECT SUM(x.val) AS summe
            FROM (
                SELECT DISTINCT b.belegnr, CAST(b.stwert1 AS REAL) AS val
                FROM beleg b
                JOIN belegpos p ON p.belegnr = b.belegnr
                WHERE b.belegart = ?
                  AND b.filiale  = ?
                  AND b.belegdat >= ? AND b.belegdat < ?
                  AND UPPER(TRIM(p.artikelnr)) IN ({artikel_in_q})
                  AND p.kzdruck IS NOT NULL
                  AND UPPER(TRIM(p.kzdruck)) <> 'A'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM belegpos p2
                      WHERE p2.belegnr = b.belegnr
                        AND (
                            UPPER(TRIM(p2.artikelnr)) LIKE 'L06%' OR
                            UPPER(TRIM(p2.artikelnr)) LIKE 'L05%'{" OR UPPER(TRIM(p2.artikelnr)) IN (" + excl_in_q + ")" if excl_in_q else ""}
                        )
                  )
            ) x
        """
        params = [belegart, filiale, self.DatumVon, self.DatumBis, *artikel]
        if ausgeschlossen:
            params += list(ausgeschlossen)
        row = self.conn.execute(sql, params).fetchone()
        return float(row["summe"] or 0.0)

    # Software exakt wie in Firebird: über BELEGPOS.CREATEDATUM/FILIALE/ARTIKELNR
    def _sum_software(self, belegart: str) -> float:
        sql = """
            SELECT SUM(CAST(p.gesamt AS REAL)) AS summe
            FROM belegpos p
            WHERE p.createdatum >= ? AND p.createdatum < ?
              AND UPPER(TRIM(p.belegart)) = UPPER(?)
              AND TRIM(p.filiale) = '0'
              AND UPPER(TRIM(p.artikelnr)) LIKE '970%'
        """
        row = self.conn.execute(sql, [self.DatumVon, self.DatumBis, belegart]).fetchone()
        return float(row["summe"] or 0.0)

    # Accessories: wie dein Original (RE/Filiale 0/Versand 95/LONR gesetzt/EXISTS KZDRUCK<>A/NOT EXISTS L06,L05,Exclusions)
    def _sum_accessories(self, ausgeschlossen: Sequence[str]) -> float:
        ausgeschlossen = tuple(a.strip().upper() for a in ausgeschlossen)
        excl_in_q = ",".join("?" for _ in ausgeschlossen) if ausgeschlossen else None

        sql = f"""
            SELECT SUM(x.val) AS summe
            FROM (
                SELECT DISTINCT b.belegnr, CAST(b.stwert1 AS REAL) AS val
                FROM beleg b
                WHERE UPPER(TRIM(b.belegart)) = 'RE'
                  AND TRIM(b.filiale) = '0'
                  AND b.belegdat >= ? AND b.belegdat < ?
                  AND TRIM(b.versndart) = '95'
                  AND b.lonr IS NOT NULL
                  AND TRIM(b.lonr) <> ''
                  AND EXISTS (
                      SELECT 1
                      FROM belegpos p
                      WHERE p.belegnr = b.belegnr
                        AND p.kzdruck IS NOT NULL
                        AND UPPER(TRIM(p.kzdruck)) <> 'A'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM belegpos p2
                      WHERE p2.belegnr = b.belegnr
                        AND (
                            UPPER(TRIM(p2.artikelnr)) LIKE 'L06%' OR
                            UPPER(TRIM(p2.artikelnr)) LIKE 'L05%'{" OR UPPER(TRIM(p2.artikelnr)) IN (" + excl_in_q + ")" if excl_in_q else ""}
                        )
                  )
            ) x
        """
        params: List[Any] = [self.DatumVon, self.DatumBis]
        if ausgeschlossen:
            params += list(ausgeschlossen)
        row = self.conn.execute(sql, params).fetchone()
        return float(row["summe"] or 0.0)

    # ----- Fachfunktionen -----
    # Order Entry (AU)
    def get_CPR_AU(self): self.Summe_CPR_AU = self._sum_by_articles(('09100',), ('04100','04101'), '7', 'AU')
    def get_C1_AU(self):  self.Summe_C1_AU  = self._sum_by_articles(('05100',), ('04100','04101'), '7', 'AU')

    def get_AED_AU(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_AU = self._sum_by_articles(artikel, ('04100','04101'), '7', 'AU')

    def get_Cosinuss_AU(self):
        artikel = ('15121.101L','15121.101M','15121.101S','15122.101SM','15123.101SM')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_Cosinus_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_C3_AU(self):
        artikel = ('04100','04200','04301','04300')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_C3T_AU(self):
        artikel = ('04101','04201','04302')
        excl = ('04100','04200','04301','04300',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3T_AU = self._sum_by_articles(artikel, excl, '7', 'AU')

    def get_Software_AU(self): self.Summe_Software_AU = self._sum_software('AU')

    # Sales (RE)
    def get_CPR(self): self.Summe_CPR = self._sum_by_articles(('09100',), ('04100','04101'), '7', 'RE')
    def get_C1(self):  self.Summe_C1  = self._sum_by_articles(('05100',), ('04100','04101'), '7', 'RE')

    def get_Cosinuss(self):
        artikel = ('15121.101L','15121.101M','15121.101S','15122.101SM','15123.101SM')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_Cosinus = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_AED(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED = self._sum_by_articles(artikel, ('04100','04101'), '7', 'RE')

    def get_C3(self):
        artikel = ('04100','04200','04301','04300')
        excl = ('04101','04201','04302',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3 = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_C3T(self):
        artikel = ('04101','04201','04302')
        excl = ('04100','04200','04301','04300',"06100","06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_C3T = self._sum_by_articles(artikel, excl, '7', 'RE')

    def get_Software(self): self.Summe_Software = self._sum_software('RE')

    # Gebraucht
    def get_C3_C1_Gebraucht(self):
        artikel = ('04100','04200','04301','04300','05100')
        self.Summe_C3_C1_refurbed = self._sum_by_articles(artikel, ('04101','04201','04302','06101.10'), '8', 'RE')

    def get_AED_Gebraucht(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_Gebraucht = self._sum_by_articles(artikel, ('04100',), '8', 'RE')

    def get_C3_C1_Gebraucht_AU(self):
        artikel = ('04100','04200','04301','04300','05100')
        self.Summe_C3_C1_refurbed_AU = self._sum_by_articles(artikel, ('04101','04201','04302','06101.10'), '8', 'AU')

    def get_AED_Gebraucht_AU(self):
        artikel = ('06100',"06100.10","06100.11","06100.20","06100.21","06101.10","06101.11","06101.20","06101.21")
        self.Summe_AED_Gebraucht_AU = self._sum_by_articles(artikel, ('04100',), '8', 'AU')

    # Accessories-Set (RE/Filiale 0, Versand 95, LONR gesetzt)
    def set_Accessoires(self):
        ausgeschlossen = ('04100','04200','04300','04301','04101','04201','04302',
                          '06100',"06100.10","06100.11","06100.20","06100.21",
                          "06101.10","06101.11","06101.20","06101.21")
        self.Summe_Accessoires = self._sum_accessories(ausgeschlossen)

    # Servicescheine (MO, Summe STWERT1)
    def get_Servicescheine(self):
        sql = """
            SELECT SUM(CAST(b.stwert1 AS REAL)) AS summe
            FROM beleg b
            WHERE b.belegdat >= ? AND b.belegdat < ?
              AND UPPER(TRIM(b.belegart)) = 'MO'
        """
        row = self.conn.execute(sql, [self.DatumVon, self.DatumBis]).fetchone()
        self.gesamt_servicescheine = float(row["summe"] or 0.0)
        return self.gesamt_servicescheine

    # Summen-Ausgabe
    def getSummen(self):
        print(50*"#")
        print("Order Entry (AU)")
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
        print("Sales (RE)")
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
        print("Accessories:", getattr(self, "Summe_Accessoires", 0.0))

# =========================
# Main
# =========================
if __name__ == "__main__":
    # 1) Export (Firebird -> frische SQLite) für gewünschten Monat
    sync = DatabaseSynchronizer()
    sync.setZeitraum(monat=9, jahr=2025)   # <-- hier anpassen
    sync.run()

    # 2) Auswertung in SQLite (inkl. Accessories)
    app = GERAETE_SQLite(sqlite_path=SQLITE_PATH)
