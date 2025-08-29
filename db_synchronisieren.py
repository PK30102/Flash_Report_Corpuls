# synchronizer.py
from datenbank import DATACONNECT
import sqlite3
import os
import calendar
from contextlib import closing
from datetime import datetime, date, time
from typing import Iterable, Tuple, Any, List, Dict

SQLITE_PATH = "export.db"
BATCH_SIZE  = 5000

# Sehr schnelle/IO-sparende PRAGMAs; für mehr Robustheit:
# journal_mode="WAL", synchronous="NORMAL"
SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "OFF",
    "synchronous": "OFF",
    "temp_store": "MEMORY",
    "cache_size": "-20000",       # ~20 MB Cache (negativ = KB)
    "locking_mode": "EXCLUSIVE",
}

class DatabaseSynchronizer(DATACONNECT):
    def __init__(self):
        super().__init__()
        self.conn = None
        self.verbindeDatenbank()   # Firebird öffnen (von DATACONNECT)

        self.DatumVon = None
        self.DatumBis = None
        self.MonatDaten = None

    def __del__(self):
        try:
            self.schließeDatenbank()
        except Exception:
            pass

    # ---------------- Zeitraum setzen ----------------
    def setZeitraum(self, monat: int, jahr: int):
        self.monat = int(monat)
        self.jahr = int(jahr)

        anzahl_tage = calendar.monthrange(self.jahr, self.monat)[1]
        tage = [f"{self.jahr}-{str(self.monat).zfill(2)}-{str(tag).zfill(2)}"
                for tag in range(1, anzahl_tage + 1)]

        self.MonatDaten = {
            "start": f"{self.jahr}-{str(self.monat).zfill(2)}-01 00:00:00",
            "ende":  f"{self.jahr}-{str(self.monat).zfill(2)}-{anzahl_tage} 23:59:59",
            "tage":  tage
        }
        self.DatumVon = self.MonatDaten["start"]
        self.DatumBis = self.MonatDaten["ende"]
        print(f"Zeitraum: {self.DatumVon} - {self.DatumBis}")

    # ------------- Firebird-Selects (parametrisiert) -------------
    SQL_BELEG = """
        SELECT BELEGTYP, BELEGART, BELEGNR, STWERT1, FILIALE, BELEGDAT, VERSNDART, LONR
        FROM BELEG
        WHERE BELEGDAT BETWEEN ? AND ?
    """

    # WICHTIG: createdatum + filiale mit selektieren (passen zum Insert)
   
    SQL_BELEGPOS = """
        SELECT p.BELEGTYP, p.BELEGART, p.BELEGNR, p.GESAMT, p.KZDRUCK, p.ARTIKELNR, p.CREATEDATUM, p.FILIALE
        FROM BELEGPOS p
        JOIN BELEG b ON b.BELEGNR = p.BELEGNR
        WHERE b.BELEGDAT BETWEEN ? AND ?
    """


    # ---------------- SQLite vorbereiten ----------------
    def _prepare_sqlite(self) -> sqlite3.Connection:
        if os.path.exists(SQLITE_PATH):
            os.remove(SQLITE_PATH)   # komplett neu bei jedem Lauf

        con = sqlite3.connect(SQLITE_PATH)
        con.execute("PRAGMA foreign_keys = ON;")
        for k, v in SQLITE_PRAGMAS.items():
            con.execute(f"PRAGMA {k} = {v};")

        # createdatum & filiale direkt im CREATE (kein ALTER TABLE nötig)
        schema = """
        CREATE TABLE IF NOT EXISTS beleg (
            belegtyp   TEXT,
            belegart   TEXT,
            belegnr    TEXT,
            stwert1    REAL,
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
            gesamt      REAL,
            kzdruck     TEXT,
            artikelnr   TEXT,
            createdatum TEXT,
            filiale     TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_belegpos_nr ON belegpos(belegnr);
        CREATE INDEX IF NOT EXISTS ix_belegpos_date ON belegpos(createdatum);
        """
        con.executescript(schema)
        return con

    # --------------- Helfer: Streaming & Typen ---------------
    def _stream_fetch(self, cursor, fetchsize: int) -> Iterable[Tuple[Any, ...]]:
        while True:
            rows = cursor.fetchmany(fetchsize)
            if not rows:
                break
            for r in rows:
                yield r

    def _to_iso(self, v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat(sep=" ")
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, time):
            return v.isoformat()
        return v

    def _normalize_row(self, row: Tuple[Any, ...]) -> Tuple[Any, ...]:
        return tuple(self._to_iso(x) for x in row)
    
    def _normalize_row_pos(row):
        # row: (belegtyp, belegart, belegnr, gesamt, kzdruck, artikelnr, createdatum, filiale)
        belegtyp, belegart, belegnr, gesamt, kzdruck, artikelnr, createdatum, filiale = row
        def to_iso(v): ...
        return (
            str(belegtyp).strip() if belegtyp is not None else None,
            str(belegart).strip() if belegart is not None else None,
            str(belegnr).strip() if belegnr is not None else None,
            float(gesamt) if gesamt is not None else None,
            (str(kzdruck).strip().upper() if kzdruck is not None else None),
            (str(artikelnr).strip().upper() if artikelnr is not None else None),
            to_iso(createdatum),
            (str(filiale).strip() if filiale is not None else None),
        )


    # --------------------- Hauptfunktion ---------------------
    def synchronisiereDaten(self):
        if not self.conn:
            raise RuntimeError("Keine Firebird-Verbindung. (verbindeDatenbank() fehlgeschlagen?)")
        if not (self.DatumVon and self.DatumBis):
            raise ValueError("Zeitraum fehlt. Rufe zuerst setZeitraum(monat, jahr) auf.")

        fb_cur1 = self.conn.cursor()
        fb_cur2 = self.conn.cursor()
        try:
            fb_cur1.arraysize = BATCH_SIZE
            fb_cur2.arraysize = BATCH_SIZE
        except Exception:
            pass

        # SQLite frisch erstellen
        sq = self._prepare_sqlite()
        with closing(sq):
            # -------- BELEG --------
            fb_cur1.execute(self.SQL_BELEG, (self.DatumVon, self.DatumBis))
            insert_beleg = """
                INSERT INTO beleg (belegtyp, belegart, belegnr, stwert1, filiale, belegdat, versndart, lonr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            total_beleg = 0
            with sq:  # eine Transaktion
                batch: List[Tuple[Any, ...]] = []
                for row in self._stream_fetch(fb_cur1, BATCH_SIZE):
                    batch.append(self._normalize_row(tuple(row)))
                    if len(batch) >= BATCH_SIZE:
                        sq.executemany(insert_beleg, batch)
                        total_beleg += len(batch)
                        batch.clear()
                if batch:
                    sq.executemany(insert_beleg, batch)
                    total_beleg += len(batch)

            # -------- BELEGPOS --------
            fb_cur2.execute(self.SQL_BELEGPOS, (self.DatumVon, self.DatumBis))
            insert_belegpos = """
                INSERT INTO belegpos (belegtyp, belegart, belegnr, gesamt, kzdruck, artikelnr, createdatum, filiale)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            total_belegpos = 0
            with sq:
                batch2: List[Tuple[Any, ...]] = []
                for row in self._stream_fetch(fb_cur2, BATCH_SIZE):
                    batch2.append(self._normalize_row(tuple(row)))
                    if len(batch2) >= BATCH_SIZE:
                        sq.executemany(insert_belegpos, batch2)
                        total_belegpos += len(batch2)
                        batch2.clear()
                if batch2:
                    sq.executemany(insert_belegpos, batch2)
                    total_belegpos += len(batch2)

            # Optional: Statistik
            with sq:
                sq.execute("ANALYZE;")

        print(f"[OK] Export fertig: {os.path.abspath(SQLITE_PATH)}")
        print(f"  BELEG:    {total_beleg} Zeilen")
        print(f"  BELEGPOS: {total_belegpos} Zeilen")

if __name__ == "__main__":
    sync = DatabaseSynchronizer()
    sync.setZeitraum(monat=8, jahr=2025)
    sync.synchronisiereDaten()
