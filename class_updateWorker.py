from PySide6.QtCore import QRunnable, Signal, Slot, QObject
import os, shutil, sys, requests, zipfile2, logger, subprocess

basedir = os.path.dirname(__file__)

class WorkerSignals(QObject):
    statusmeldung = Signal(str)
    updateErfolgreich = Signal(int, bool)

class UpdateWorker(QRunnable):

    def __init__(self, gdtTools:dict, programmverzeichnis:str, gdtToolNr:int, latestVersion:str):
        super().__init__()
        self.gdtTools = gdtTools
        self.programmverzeichnis = programmverzeichnis
        self.gdtToolNr = gdtToolNr
        self.latestVersion = latestVersion

        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        gdtTool = list(self.gdtTools)[self.gdtToolNr]
        platform = sys.platform
        if "win32" in platform:
            zipname = self.gdtTools[gdtTool] + ".zip"
            downloadverzeichnis = os.path.expanduser("~\\Downloads")
        if "darwin" in platform:
            zipname = self.gdtTools[gdtTool] + ".app.zip"
            downloadverzeichnis = os.path.expanduser("~/Downloads")
        elif "linux" in platform:
            zipname = self.gdtTools[gdtTool] + ".tar.xz"
            downloadverzeichnis = os.path.expanduser("~/Downloads")
        # Zip-Datei herunterladen
        try:
            self.signals.statusmeldung.emit(str(zipname) + " von GitHub herunterladen...")
            url = "https://github.com/retconx/" + gdtTool + "/releases/download/v" + self.latestVersion + "/" + zipname
            response = requests.get(url)
            # Zip-Datei im Download-Ordner speichern
            zip = open(os.path.join(downloadverzeichnis, zipname), "wb")
            zip.write(response.content)
            zip.close()
            try:
                # Zip-Datei in Downloads/... entpacken
                self.signals.statusmeldung.emit(str(zipname) + " entpacken...")
                zip_ref = zipfile2.ZipFile(os.path.join(downloadverzeichnis, zipname))
                zip_ref.extractall(os.path.join(downloadverzeichnis, self.gdtTools[gdtTool]))
                zip_ref.close()
                try:
                    # Entpackten Ordner in Programmverzeichnis kopieren
                    speicherverzeichnis = self.programmverzeichnis
                    if "win32" in platform:
                        speicherverzeichnis = self.programmverzeichnis.replace("/", "\\")
                    elif "darwin" in platform or "linux" in platform:
                        subprocess.run([os.path.join(basedir, "changeMode.sh"), os.path.join(downloadverzeichnis, self.gdtTools[gdtTool])])
                    self.signals.statusmeldung.emit("Programmdateien nach "  + speicherverzeichnis + " kopieren...")
                    shutil.copytree(os.path.join(downloadverzeichnis, self.gdtTools[gdtTool]), speicherverzeichnis, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__MACOSX"))
                    self.signals.statusmeldung.emit("Downloadverzeichnis bereinigen...")
                    try:
                        # Downloadverzeichnis bereinigen
                        os.unlink(os.path.join(downloadverzeichnis, zipname))
                        shutil.rmtree(os.path.join(downloadverzeichnis, self.gdtTools[gdtTool]))
                        self.signals.statusmeldung.emit("Update erfolgreich beendet")
                        self.signals.updateErfolgreich.emit(self.gdtToolNr, True)
                    except Exception as e:
                        self.signals.statusmeldung.emit("Problem beim Bereinigen des Downloadverzeichnisses")
                        self.signals.updateErfolgreich.emit(self.gdtToolNr, False)
                        logger.logger.error("Problem beim Bereinigen des Downloadverzeichnisses: " + str(e))
                except Exception as e:
                    self.signals.statusmeldung.emit("Problem beim Kopieren der Programmdateien")
                    self.signals.updateErfolgreich.emit(self.gdtToolNr, False)
                    logger.logger.error("Problem beim Kopieren der Programmdateien: " + str(e))
            except Exception as e:
                self.signals.statusmeldung.emit("Problem beim Entpacken von " + zipname)
                self.signals.updateErfolgreich.emit(self.gdtToolNr, False)
                logger.logger.error("Fehler beim Entpacken von " + zipname + ": " + str(e))
        except Exception as e:
            self.signals.statusmeldung.emit("Problem beim Herunterladen von " + zipname)
            self.signals.updateErfolgreich.emit(self.gdtToolNr, False)
            logger.logger.error("Fehler beim Herunterladen von " + zipname + ": " + str(e))