import sys, configparser, os, datetime, shutil, logger
import requests, atexit, subprocess, re
import logger, dialogEula, dialogEula, dialogUeberGdtToolsUpdater, class_updateWorker
## Nur mit Lizenz
import kd
## /Nur mit Lizenz
from PySide6.QtCore import Qt, QTranslator, QLibraryInfo, QThreadPool
from PySide6.QtGui import QFont, QAction, QIcon, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QStatusBar,
    QProgressBar,
    QGridLayout,
    QWidget,
    QLabel, 
    QLineEdit,
    QMessageBox,
    QPushButton
)

class GdtToolsUpdaterException(Exception):
    def __init__(self, meldung):
        self.meldung = meldung
    def __str__(self):
        return "GDT-Tools Updater-Fehler: " + self.meldung

basedir = os.path.dirname(__file__)
gth = ""
## #Nur mit Lizenz
gth = kd.dekrypt("10675B00705320474A60682AE0555F60334360344520375940364C20706040572D80783AA0743B80373AA0762F40474D00436AC03448A04341A0712BCE")
## /Nur mit Lizenz

gdtTools = {
    "dosisgdt": "DosisGDT",
    "gerigdt": "GeriGDT",
    "inrgdt": "InrGDT",
    "optigdt": "OptiGDT",
    "scoregdt": "ScoreGDT",
    "signogdt": "SignoGDT"
    }

if len(sys.argv) != 4:
    logger.logger.error("Argumentübergabe fehlerhaft: " + str.join(",", sys.argv))
_gdtToolKlein = str(sys.argv[1])
logger.logger.info("GDT-Tool: " + _gdtToolKlein)
_gdtToolGross = gdtTools[_gdtToolKlein]
_installierteVersion = str(sys.argv[2])
logger.logger.info("Installierte Version: " + _installierteVersion)
_programmverzeichnis = str(sys.argv[3])
logger.logger.info("Programmverzeichnis: " + _programmverzeichnis)
_verfuegbareVersion = "?"

def versionVeraltet(versionAktuell:str, versionVergleich:str):
    """
    Vergleicht zwei Versionen im Format x.x.x
    Parameter:
        versionAktuell:str
        versionVergleich:str
    Rückgabe:
        True, wenn versionAktuell veraltet
    """
    patternVersion = r"^\d+\.\d+\.\d+$"
    versionVeraltet = False
    if re.match(patternVersion, versionAktuell) != None and re.match(patternVersion, versionVergleich) != None:
        hunderterBase = int(versionVergleich.split(".")[0])
        zehnerBase = int(versionVergleich.split(".")[1])
        einserBase = int(versionVergleich.split(".")[2])
        hunderter = int(versionAktuell.split(".")[0])
        zehner = int(versionAktuell.split(".")[1])
        einser = int(versionAktuell.split(".")[2])
        if hunderterBase > hunderter:
            versionVeraltet = True
        elif hunderterBase == hunderter:
            if zehnerBase >zehner:
                versionVeraltet = True
            elif zehnerBase == zehner:
                if einserBase > einser:
                    versionVeraltet = True
    else:
        logger.logger.error("Falsches Format für den Versionsvergleich: " + versionAktuell + ", " + versionVergleich)
        raise GdtToolsUpdaterException("Falsches Format für den Versionsvergleich")
    return versionVeraltet

# Sicherstellen, dass Icon in Windows angezeigt wird
try:
    from ctypes import windll # type: ignore
    mayappid = "gdttools.gdttoolsupdater"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(mayappid)
except ImportError:
    pass

class MainWindow(QMainWindow):

    # Mainwindow zentrieren
    def resizeEvent(self, e):
        mainwindowBreite = e.size().width()
        mainwindowHoehe = e.size().height()
        ag = self.screen().availableGeometry()
        screenBreite = ag.size().width()
        screenHoehe = ag.size().height()
        left = screenBreite / 2 - mainwindowBreite / 2
        top = screenHoehe / 2 - mainwindowHoehe / 2
        self.setGeometry(left, top, mainwindowBreite, mainwindowHoehe)

    def __init__(self):
        super().__init__()

        self.threadpool = QThreadPool()

        # config.ini lesen
        updateSafePath = ""
        if sys.platform == "win32":
            logger.logger.info("Plattform: win32")
            updateSafePath = os.path.expanduser("~\\appdata\\local\\gdttoolsupdater")
        else:
            logger.logger.info("Plattform: nicht win32")
            updateSafePath = os.path.expanduser("~/.config/gdttoolsupdater")
        self.configPath = updateSafePath
        self.configIni = configparser.ConfigParser()
        if os.path.exists(os.path.join(updateSafePath, "config.ini")):
            logger.logger.info("config.ini in " + updateSafePath + " exisitert")
            self.configPath = updateSafePath
        elif os.path.exists(os.path.join(basedir, "config.ini")):
            logger.logger.info("config.ini in " + updateSafePath + " exisitert nicht")
            try:
                if (not os.path.exists(updateSafePath)):
                    logger.logger.info(updateSafePath + " exisitert nicht")
                    os.makedirs(updateSafePath, 0o777)
                    logger.logger.info(updateSafePath + "erzeugt")
                shutil.copy(os.path.join(basedir, "config.ini"), updateSafePath)
                logger.logger.info("config.ini von " + basedir + " nach " + updateSafePath + " kopiert")
                self.configPath = updateSafePath
            except:
                logger.logger.error("Problem beim Kopieren der config.ini von " + basedir + " nach " + updateSafePath)
                mb = QMessageBox(QMessageBox.Icon.Warning, "HHinweis von " + _gdtToolGross + "-Updater", "Problem beim Kopieren der Konfigurationsdatei. GDT-Tools Updater wird mit Standardeinstellungen gestartet.", QMessageBox.StandardButton.Ok)
                mb.exec()
                self.configPath = basedir
        else:
            logger.logger.critical("config.ini fehlt")
            mb = QMessageBox(QMessageBox.Icon.Critical, "Hinweis von " + _gdtToolGross + "-Updater", "Die Konfigurationsdatei config.ini fehlt. GDT-Tools Updater kann nicht gestartet werden.", QMessageBox.StandardButton.Ok)
            mb.exec()
            sys.exit()
        self.configIni.read(os.path.join(self.configPath, "config.ini"), encoding="utf-8")
        self.version = self.configIni["Allgemein"]["version"]
        self.eulagelesen = self.configIni["Allgemein"]["eulagelesen"] == "True"
        ## Nachträglich hinzufefügte Options
        # 1.0.1
        ## /Nachträglich hinzufefügte Options

        # Prüfen, ob EULA gelesen
        if not self.eulagelesen:
            de = dialogEula.Eula()
            de.exec()
            if de.checkBoxZustimmung.isChecked():
                self.eulagelesen = True
                self.configIni["Allgemein"]["eulagelesen"] = "True"
                with open(os.path.join(self.configPath, "config.ini"), "w", encoding="utf-8") as configfile:
                    self.configIni.write(configfile)
                logger.logger.info("EULA zugestimmt")
            else:
                mb = QMessageBox(QMessageBox.Icon.Information, "Hinweis von " + _gdtToolGross + "-Updater", "Ohne Zustimmung der Lizenzvereinbarung kann GDT-Tools Updater nicht gestartet werden.", QMessageBox.StandardButton.Ok)
                mb.exec()
                sys.exit()

        # Version vergleichen und gegebenenfalls aktualisieren
        configIniBase = configparser.ConfigParser()
        try:
            configIniBase.read(os.path.join(basedir, "config.ini"), encoding="utf-8")
            if versionVeraltet(self.version, configIniBase["Allgemein"]["version"]):
                # Version aktualisieren
                self.configIni["Allgemein"]["version"] = configIniBase["Allgemein"]["version"]
                self.configIni["Allgemein"]["releasedatum"] = configIniBase["Allgemein"]["releasedatum"] 
                ## config.ini aktualisieren

                ## /config.ini aktualisieren

                with open(os.path.join(self.configPath, "config.ini"), "w", encoding="utf-8") as configfile:
                    self.configIni.write(configfile)
                self.version = self.configIni["Allgemein"]["version"]
                logger.logger.info("Version auf " + self.version + " aktualisiert")
                # Prüfen, ob EULA gelesen
                de = dialogEula.Eula(self.version)
                de.exec()
                self.eulagelesen = de.checkBoxZustimmung.isChecked()
                self.configIni["Allgemein"]["eulagelesen"] = str(self.eulagelesen)
                with open(os.path.join(self.configPath, "config.ini"), "w", encoding="utf-8") as configfile:
                    self.configIni.write(configfile)
                if self.eulagelesen:
                    logger.logger.info("EULA zugestimmt")
                else:
                    logger.logger.info("EULA nicht zugestimmt")
                    mb = QMessageBox(QMessageBox.Icon.Information, "Hinweis von " + _gdtToolGross + "-Updater", "Ohne  Zustimmung zur Lizenzvereinbarung kann GDT-Tools Updater nicht gestartet werden.", QMessageBox.StandardButton.Ok)
                    mb.exec()
                    sys.exit()
        except SystemExit:
            sys.exit()
        except:
            logger.logger.error("Problem beim Aktualisieren auf Version " + configIniBase["Allgemein"]["version"])
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Problem beim Aktualisieren auf Version " + configIniBase["Allgemein"]["version"], QMessageBox.StandardButton.Ok)
            mb.exec()
        
        jahr = datetime.datetime.now().year
        copyrightJahre = "2024"
        if jahr > 2024:
            copyrightJahre = "2024-" + str(jahr)
        self.setWindowTitle(_gdtToolGross + "-Updater V" + self.version + " (\u00a9 Fabian Treusch - GDT-Tools " + copyrightJahre + ")")
        self.setFixedWidth(600)
        self.fontNormal = QFont()
        self.fontNormal.setBold(False)
        self.fontBold = QFont()
        self.fontBold.setBold(True)

        # Updateprüfung auf Github
        try:
            self.updatePruefung(meldungNurWennUpdateVerfuegbar=True)
        except Exception as e:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Updateprüfung nicht möglich.\nBitte überprüfen Sie Ihre Internetverbindung." + str(e), QMessageBox.StandardButton.Ok)
            mb.exec()
            logger.logger.warning("Updateprüfung nicht möglich: " + str(e))

        # Verfügbare Version abrufen
        try:
            response = requests.get("https://api.github.com/repos/retconx/" + _gdtToolKlein + "/releases/latest", headers={"Authorization" : "Bearer " + gth})
            githubRelaseTag = response.json()["tag_name"]
            global _verfuegbareVersion
            _verfuegbareVersion = githubRelaseTag[1:] # ohne v
        except Exception as e:
            logger.logger.error("Fehler beim GitHub-Abruf der aktuellen Version von " + _gdtToolGross + ": " + str(e))
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Problem beim GitHub-Abruf der verfügbaren Version: " + str(e), QMessageBox.StandardButton.Ok)
            mb.exec()

        # Foromularaufbau
        self.widget = QWidget()
        mainLayoutV = QVBoxLayout()
        gdtToolsTabelleLayoutG = QGridLayout()
        buttonsLayoutH = QHBoxLayout()
        labelInstallierteVersion = QLabel("Installierte Version:")
        self.lineEditInstallierteVersion = QLineEdit(_installierteVersion)
        self.lineEditInstallierteVersion.setReadOnly(True)
        labelVerfuegbareVersion = QLabel("Verfügbare Version:")
        self.lineEditVerfuegbareVersion = QLineEdit(_verfuegbareVersion)
        self.lineEditVerfuegbareVersion.setReadOnly(True)
        labelProgrammverzeichnis = QLabel("Programmverzeichnis:")
        self.lineEditProgrammverzeichnis = QLineEdit(_programmverzeichnis)
        self.pushButtonProgrammverzeichnisAuswaehlen = QPushButton("...")
        self.pushButtonProgrammverzeichnisAuswaehlen.clicked.connect(self.pushButtonProgrammverzeichnisAuswaehlenClicked)
        self.pushButtonUpdate = QPushButton("Update")
        self.pushButtonUpdate.clicked.connect(self.pushButtonUpdateClicked)
        self.pushButtonSchliessen= QPushButton("Schließen")
        self.pushButtonSchliessen.clicked.connect(self.pushButtonSchliessenClicked)

        gdtToolsTabelleLayoutG.addWidget(labelInstallierteVersion, 0, 0)
        gdtToolsTabelleLayoutG.addWidget(self.lineEditInstallierteVersion, 0, 1)
        gdtToolsTabelleLayoutG.addWidget(labelVerfuegbareVersion, 1, 0)
        gdtToolsTabelleLayoutG.addWidget(self.lineEditVerfuegbareVersion, 1, 1)
        gdtToolsTabelleLayoutG.addWidget(labelProgrammverzeichnis, 2, 0)
        gdtToolsTabelleLayoutG.addWidget(self.lineEditProgrammverzeichnis, 2, 1)
        gdtToolsTabelleLayoutG.addWidget(self.pushButtonProgrammverzeichnisAuswaehlen, 2, 2)

        buttonsLayoutH.addWidget(self.pushButtonUpdate)
        buttonsLayoutH.addWidget(self.pushButtonSchliessen)

        mainLayoutV.addLayout(gdtToolsTabelleLayoutG)
        mainLayoutV.addLayout(buttonsLayoutH)

        self.status = QStatusBar()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status.addPermanentWidget(self.progress)
        self.setStatusBar(self.status)
        self.widget.setLayout(mainLayoutV)
        self.setCentralWidget(self.widget)

        # Menü
        menubar = self.menuBar()
        anwendungMenu = menubar.addMenu("")
        aboutAction = QAction(self)
        aboutAction.setMenuRole(QAction.MenuRole.AboutRole)
        aboutAction.triggered.connect(self.ueberGdtToolsUpdater) 
        updateAction = QAction("Auf Update prüfen", self)
        updateAction.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        updateAction.triggered.connect(self.updatePruefung) 
        hilfeMenu = menubar.addMenu("Hilfe")
        hilfeWikiAction = QAction("GDT-Tools Updater Wiki", self)
        hilfeWikiAction.triggered.connect(self.gdtToolsUpdaterWiki)
        hilfeUpdateAction = QAction("Auf Update prüfen", self)
        hilfeUpdateAction.triggered.connect(self.updatePruefung)
        hilfeUeberAction = QAction("Über GDT-Tools Updater", self)
        hilfeUeberAction.setMenuRole(QAction.MenuRole.NoRole)
        hilfeUeberAction.triggered.connect(self.ueberGdtToolsUpdater)
        hilfeEulaAction = QAction("Lizenzvereinbarung (EULA)", self)
        hilfeEulaAction.triggered.connect(self.eula) 
        hilfeLogExportieren = QAction("Log-Verzeichnis exportieren", self)
        hilfeLogExportieren.triggered.connect(self.logExportieren) 
        
        anwendungMenu.addAction(aboutAction)
        anwendungMenu.addAction(updateAction)
        hilfeMenu.addAction(hilfeWikiAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeUpdateAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeUeberAction)
        hilfeMenu.addAction(hilfeEulaAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeLogExportieren)

        if not versionVeraltet(_installierteVersion, _verfuegbareVersion):
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von " + _gdtToolGross + "-Updater", "Es ist keine neuere " + _gdtToolGross + "-Version als die bereits installierte verfügbar.\n" + _gdtToolGross + "-Updater wird beendet.", QMessageBox.StandardButton.Ok)
            mb.exec()
            sys.exit()

        if not self.checkProgrammverzeichnisErreichbarkeit():
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von " + _gdtToolGross + "-Updater", "Im ausgewählten Verzeichnis befindet sich keine Programmdatei von " + _gdtToolGross + ".", QMessageBox.StandardButton.Ok)
            mb.exec()
            self.pushButtonUpdate.setEnabled(False)
            self.lineEditProgrammverzeichnis.setFocus()
            self.lineEditProgrammverzeichnis.selectAll()

    def checkProgrammverzeichnisErreichbarkeit(self):
        """
        Prüft, ob das Programmverzeichnis existiert und ob dieses die Programmdatei des entsprechenden GDT-Tools enthält
        Parameter:
            gdtToolNr:int, -1, wenn für alle Tools geprüft werden soll
        Rückgabe:
            True oder False
        """
        ok = False
        programmverzeichnisExistiert = os.path.exists(self.lineEditProgrammverzeichnis.text())
        if programmverzeichnisExistiert and "win32" in sys.platform:
            ok = _gdtToolKlein + ".exe" in os.listdir(self.lineEditProgrammverzeichnis.text())
        elif programmverzeichnisExistiert and "darwin" in sys.platform:
            ok = _gdtToolGross + ".app" in os.listdir(self.lineEditProgrammverzeichnis.text())
        elif programmverzeichnisExistiert and "linux" in sys.platform:
            ok = _gdtToolKlein in os.listdir(self.lineEditProgrammverzeichnis.text())
        if not ok:
            self.lineEditProgrammverzeichnis.setStyleSheet("background:rgb(255,200,200)")
        else:
            self.lineEditProgrammverzeichnis.setStyleSheet("background:rgb(255,255,255)") 
        return ok

    def pushButtonProgrammverzeichnisAuswaehlenClicked(self):
        fd = QFileDialog(self)
        fd.setFileMode(QFileDialog.FileMode.Directory)
        fd.setWindowTitle("Programmverzeichnis auswählen")
        fd.setModal(True)
        fd.setLabelText(QFileDialog.DialogLabel.Accept, "Speichern")
        fd.setLabelText(QFileDialog.DialogLabel.Reject, "Abbrechen")
        if fd.exec() == 1:
            logger.logger.info("Programmverzeichnis " + fd.directory().absolutePath() + " ausgewählt")
            self.lineEditProgrammverzeichnis.setText(fd.directory().absolutePath())
            if not self.checkProgrammverzeichnisErreichbarkeit():
                mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von " + _gdtToolGross + "-Updater", "Im ausgewählten Verzeichnis befindet sich keine Programmdatei von " + _gdtToolGross + ".", QMessageBox.StandardButton.Ok)
                mb.exec()
                self.pushButtonUpdate.setEnabled(False)
            elif versionVeraltet(self.lineEditInstallierteVersion.text(), self.lineEditVerfuegbareVersion.text()):
                self.pushButtonUpdate.setEnabled(True)
                global _programmverzeichnis
                _programmverzeichnis = self.lineEditProgrammverzeichnis.text()
    
    def pushButtonUpdateClicked(self):
        if os.path.exists(self.lineEditProgrammverzeichnis.text()):
            self.progress.setValue(1)
            self.pushButtonProgrammverzeichnisAuswaehlen.setEnabled(False)
            self.pushButtonUpdate.setEnabled(False)
            self.pushButtonSchliessen.setEnabled(False)
            worker = class_updateWorker.UpdateWorker(_gdtToolKlein, _gdtToolGross, _programmverzeichnis, _verfuegbareVersion)
            worker.signals.statusmeldung.connect(self.updateStatusBar)
            worker.signals.updateErfolgreich.connect(self.updateErfolgreich)
            worker.signals.progressProzent.connect(self.updateProgressBar)
            logger.logger.info("Update wird gestartet: " + _gdtToolKlein + ", " + _programmverzeichnis + ", " + _verfuegbareVersion)
            self.threadpool.start(worker)
        else:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Das Programmverzeichnis existiert nicht.", QMessageBox.StandardButton.Ok)
            mb.exec()
            self.lineEditProgrammverzeichnis.setFocus()
            self.lineEditProgrammverzeichnis.selectAll()

    def updateStatusBar(self, message):
        self.status.showMessage(message)

    def updateProgressBar(self, prozent):
        self.progress.setValue(prozent)

    def updateErfolgreich(self, erfolgreich):
        if erfolgreich:
            logger.logger.info("Update erfolgreich")
            self.pushButtonUpdate.setEnabled(False)
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von " + _gdtToolGross + "-Updater", "Das " + _gdtToolGross + "-Update war erfolgreich. Für die Aktualisierung der Konfiguration muss " + _gdtToolGross + " einmalig gestartet werden.\nSoll GDT-Tools Updater nun beendet und " + _gdtToolGross + " gestartet werden?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            mb.setDefaultButton(QMessageBox.StandardButton.Yes)
            mb.button(QMessageBox.StandardButton.Yes).setText("Ja")
            mb.button(QMessageBox.StandardButton.No).setText("Nein")
            if mb.exec() == QMessageBox.StandardButton.Yes:
                logger.logger.info(_gdtToolGross + " soll gestartet werden")
                atexit.register(self.gdtToolStarten)
                logger.logger.info("GDT-Updater schließen")
                sys.exit()
        else:
            logger.logger.error("Update nicht erfolgreich")
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Das " + _gdtToolGross + "-Update konnte nicht durchgeführt werden.", QMessageBox.StandardButton.Ok)
            mb.exec()
            self.pushButtonUpdate.setEnabled(True)
        self.pushButtonSchliessen.setEnabled(True)
        
    def gdtToolStarten(self):
        if "win32" in sys.platform:
            pfad = [os.path.join(self.lineEditProgrammverzeichnis.text(), _gdtToolKlein + ".exe")]
            logger.logger.info(_gdtToolGross + " starten: " + str.join(" ", pfad))
            subprocess.Popen(pfad) # type: ignore
        elif "darwin" in sys.platform:
            pfad = ["open", "-a", os.path.join(self.lineEditProgrammverzeichnis.text(), _gdtToolGross + ".app")]
            logger.logger.info(_gdtToolGross + " starten: " + str.join(" ", pfad))
            subprocess.Popen(pfad)
        elif "linux" in sys.platform:
            pfad = [os.path.join(self.lineEditProgrammverzeichnis.text(), _gdtToolKlein)]
            logger.logger.info(_gdtToolGross + " starten: " + str.join(" ", pfad))
            subprocess.Popen(pfad)

    def updatePruefung(self, meldungNurWennUpdateVerfuegbar = False):
        response = requests.get("https://api.github.com/repos/retconx/gdttoolsupdater/releases/latest", headers={"Authorization" : "Bearer " + gth})
        githubRelaseTag = response.json()["tag_name"]
        latestVersion = githubRelaseTag[1:] # ohne v
        if versionVeraltet(self.version, latestVersion):
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Die aktuellere GDT-Tools Updater-Version " + latestVersion + " ist auf <a href='https://github.com/retconx/gdttoolsupdater/releases'>Github</a> verfügbar.", QMessageBox.StandardButton.Ok)
            mb.setTextFormat(Qt.TextFormat.RichText)
            mb.exec()
        elif not meldungNurWennUpdateVerfuegbar:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Sie nutzen die aktuelle GDT-Tools Updater-Version.", QMessageBox.StandardButton.Ok)
            mb.exec()
            
    def ueberGdtToolsUpdater(self):
        de = dialogUeberGdtToolsUpdater.UeberGdtToolsUpdater()
        de.exec()

    def eula(self):
        QDesktopServices.openUrl("https://gdttools.de/Lizenzvereinbarung_GdtToolsUpdater.pdf")

    def logExportieren(self):
        if (os.path.exists(os.path.join(basedir, "log"))):
            downloadPath = ""
            if sys.platform == "win32":
                downloadPath = os.path.expanduser("~\\Downloads")
            else:
                downloadPath = os.path.expanduser("~/Downloads")
            try:
                if shutil.copytree(os.path.join(basedir, "log"), os.path.join(downloadPath, "Log_GdtToolsUpdater"), dirs_exist_ok=True):
                    shutil.make_archive(os.path.join(downloadPath, "Log_GdtToolsUpdater"), "zip", root_dir=os.path.join(downloadPath, "Log_GdtToolsUpdater"))
                    shutil.rmtree(os.path.join(downloadPath, "Log_GdtToolsUpdater"))
                    mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Das Log-Verzeichnis wurde in den Ordner " + downloadPath + " kopiert.", QMessageBox.StandardButton.Ok)
                    mb.exec()
            except Exception as e:
                mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Problem beim Download des Log-Verzeichnisses: " + str(e), QMessageBox.StandardButton.Ok)
                mb.exec()
        else:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von " + _gdtToolGross + "-Updater", "Das Log-Verzeichnis wurde nicht gefunden.", QMessageBox.StandardButton.Ok)
            mb.exec() 
    
    def gdtToolsUpdaterWiki(self, link):
        QDesktopServices.openUrl("https://github.com/retconx/gdttoolsupdater/wiki")

    def gdtToolsLinkGeklickt(self, link):
        QDesktopServices.openUrl(link)

    def pushButtonSchliessenClicked(self):
        sys.exit()
    
app = QApplication(sys.argv)
qt = QTranslator()
filename = "qtbase_de"
directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
qt.load(filename, directory)
app.installTranslator(qt)
app.setWindowIcon(QIcon(os.path.join(basedir, "icons", "program.png")))
window = MainWindow()
window.show()
app.exec()