import fdb
import os
from dotenv import load_dotenv


class DATACONNECT:
    def __init__(self):
        self.conn = None 
        load_dotenv()

    # Lädt die Datenbankeinstellungen aus der Konfigurationsdatei
    def lade_datenbankeinstellungen(self):


        try:
            dsn = os.getenv('dsn')
            user = os.getenv('user')
            password = os.getenv('password')
            charset = os.getenv('charset', 'UTF8')

            return dsn, user, password, charset
        
        except fdb.Error as e:
            print(f"Fehler bei der Verbindung zur Datenbank: {e}")
        except Exception as e:
            print(f"Allgemeiner Fehler: {e}")

    # Stellt die Verbindung zur Datenbank her
    def verbindeDatenbank(self):
        try:
            dsn, user, password, charset = self.lade_datenbankeinstellungen()
            print(dsn, user)
            
            if not all([dsn, user, password, charset]):
                print("Datenbankeinstellungen sind unvollständig. Verbindung kann nicht hergestellt werden.")
                return

           
            self.conn = fdb.connect(
                dsn=dsn,
                user=user,
                password=password,
                charset=charset
            )
            print("Erfolgreich mit der Datenbank verbunden.")
        except fdb.Error as e:
            print(f"Fehler bei der Verbindung zur Datenbank: {e}")
            self.schließeDatenbank()

    # Schließt die Verbindung zur Datenbank
    def schließeDatenbank(self):
        if self.conn:
            self.conn.close()
            print("Verbindung zur Datenbank geschlossen.")
            self.conn = None  
