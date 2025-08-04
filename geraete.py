from datenbank import DATACONNECT

class GERAETE(DATACONNECT):
    def __init__(self):
        super().__init__()
        self.verbindeDatenbank()
        self.get_C3()
        self.schließeDatenbank()

    def setZeitraum(self, Monat, Jahr):
        self.monat = Monat
        self.jahr = Jahr

    def get_C3(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM SERIEN WHERE ARTIKELNR = '04100'")
            geraete_info = cursor.fetchone()
            print(geraete_info)
        except Exception as e:
            print(f"Fehler beim Abrufen der Geräteinformationen: {e}")
        finally:
            cursor.close() if cursor else None

if __name__ == "__main__":
    c3 = GERAETE()
