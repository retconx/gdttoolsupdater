import sys, configparser, os, datetime, shutil, logger
import requests
import logger, dialogEula, dialogEula, dialogUeberGdtToolsUpdater, dialogEinstellungenImportExport, class_updateWorker
from PySide6.QtCore import Qt, QTranslator, QLibraryInfo, QThreadPool
from PySide6.QtGui import QFont, QAction, QIcon, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QFileDialog,
    QStatusBar,
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
gdtTools = {
    "gerigdt": "GeriGDT",
    "optigdt": "OptGDT",
    "dosisgdt": "DosisGDT",
    "inrgdt": "InrGDT",
    "signogdt": "SignoGDT",
    "scoregdt": "ScoreGDT"
    }

def versionVeraltet(versionAktuell:str, versionVergleich:str):
    """
    Vergleicht zwei Versionen im Format x.x.x
    Parameter:
        versionAktuell:str
        versionVergleich:str
    Rückgabe:
        True, wenn versionAktuell veraltet
    """
    versionVeraltet= False
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
                mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Problem beim Kopieren der Konfigurationsdatei. GDT-Tools Updater wird mit Standardeinstellungen gestartet.", QMessageBox.StandardButton.Ok)
                mb.exec()
                self.configPath = basedir
        else:
            logger.logger.critical("config.ini fehlt")
            mb = QMessageBox(QMessageBox.Icon.Critical, "Hinweis von GDT-Tools Updater", "Die Konfigurationsdatei config.ini fehlt. GDT-Tools Updater kann nicht gestartet werden.", QMessageBox.StandardButton.Ok)
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
                mb = QMessageBox(QMessageBox.Icon.Information, "Hinweis von GDT-Tools Updater", "Ohne Zustimmung der Lizenzvereinbarung kann GDT-Tools Updater nicht gestartet werden.", QMessageBox.StandardButton.Ok)
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
                    mb = QMessageBox(QMessageBox.Icon.Information, "Hinweis von GDT-Tools Updater", "Ohne  Zustimmung zur Lizenzvereinbarung kann GDT-Tools Updater nicht gestartet werden.", QMessageBox.StandardButton.Ok)
                    mb.exec()
                    sys.exit()
        except SystemExit:
            sys.exit()
        except:
            logger.logger.error("Problem beim Aktualisieren auf Version " + configIniBase["Allgemein"]["version"])
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Problem beim Aktualisieren auf Version " + configIniBase["Allgemein"]["version"], QMessageBox.StandardButton.Ok)
            mb.exec()
        
        jahr = datetime.datetime.now().year
        copyrightJahre = "2024"
        if jahr > 2024:
            copyrightJahre = "2024-" + str(jahr)
        self.setWindowTitle("GDT-Tools Updater V" + self.version + " (\u00a9 Fabian Treusch - GDT-Tools " + copyrightJahre + ")")
        self.fontNormal = QFont()
        self.fontNormal.setBold(False)
        self.fontBold = QFont()
        self.fontBold.setBold(True)

        # # Updateprüfung auf Github
        # try:
        #     self.updatePruefung(meldungNurWennUpdateVerfuegbar=True)
        # except Exception as e:
        #     mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Updateprüfung nicht möglich.\nBitte überprüfen Sie Ihre Internetverbindung." + str(e), QMessageBox.StandardButton.Ok)
        #     mb.exec()
        #     logger.logger.warning("Updateprüfung nicht möglich: " + str(e))

        # Foromularaufbau
        self.widget = QWidget()
        mainLayoutV = QVBoxLayout()
        gdtToolsTabelleLayoutG = QGridLayout()
        labelGdtTool = QLabel("GDT-Tool")
        labelGdtTool.setFont(self.fontBold)
        labelProgrammverzeichnis = QLabel("Programmverzeichnis")
        labelProgrammverzeichnis.setFont(self.fontBold)
        labelInstallierteVersion = QLabel("Installiert")
        labelInstallierteVersion.setFont(self.fontBold)
        labelAktuelleVersion = QLabel("Aktuell")
        labelAktuelleVersion.setFont(self.fontBold)
        gdtToolsTabelleLayoutG.addWidget(labelGdtTool, 0, 0)
        gdtToolsTabelleLayoutG.addWidget(labelProgrammverzeichnis, 0, 1)
        gdtToolsTabelleLayoutG.addWidget(labelInstallierteVersion, 0, 3)
        gdtToolsTabelleLayoutG.addWidget(labelAktuelleVersion, 0, 4)

        labelInstallierteTools = []
        self.lineEditProgrammverzeichnisse = []
        pushButtonProgrammverzeichnisse = []
        labelInstallierteVersionen = []
        labelAktuelleVersionen = []
        pushButtonAktualisieren = []
        configPfadAllgemein = os.path.expanduser("~\\appdata\\local")
        if not "win32" in sys.platform:
            configPfadAllgemein = os.path.expanduser("~/.config")
        i = 0
        spaltenbreite = 120
        for gdtTool in gdtTools:
            labelInstallierteTools.append(QLabel(gdtTools[gdtTool])) 
            labelInstallierteTools[i].setFixedWidth(spaltenbreite)
            gdtToolsTabelleLayoutG.addWidget(labelInstallierteTools[i], i + 1, 0)
            pv = self.configIni["Programmverzeichnisse"][gdtTool]
            self.lineEditProgrammverzeichnisse.append(QLineEdit(pv))
            self.lineEditProgrammverzeichnisse[i].setFixedWidth(200)
            self.lineEditProgrammverzeichnisse[i].setToolTip(pv)
            gdtToolsTabelleLayoutG.addWidget(self.lineEditProgrammverzeichnisse[i], i + 1, 1)
            pushButtonProgrammverzeichnisse.append(QPushButton("..."))
            pushButtonProgrammverzeichnisse[i].setToolTip("Programmverzeichnis auswählen")
            pushButtonProgrammverzeichnisse[i].clicked.connect(lambda checked = False, gdtToolNr = i: self.pushButtonProgrammverzeichnisClicked(checked, gdtToolNr))
            gdtToolsTabelleLayoutG.addWidget(pushButtonProgrammverzeichnisse[i], i + 1, 2)
            iv = "-" 
            if os.path.exists(os.path.join(configPfadAllgemein, gdtTool)):
                configIniTemp = configparser.ConfigParser()
                configIniTempPfad = os.path.join(configPfadAllgemein, gdtTool)
                configIniTemp.read(os.path.join(configIniTempPfad, "config.ini"), encoding="utf-8")
                iv = configIniTemp["Allgemein"]["version"]
            labelInstallierteVersionen.append(QLabel("V" + iv))
            labelInstallierteVersionen[i].setFixedWidth(spaltenbreite)
            gdtToolsTabelleLayoutG.addWidget(labelInstallierteVersionen[i], i + 1, 3)
            lv = "?"
            try:
                response = requests.get("https://api.github.com/repos/retconx/" + str(gdtTool) + "/releases/latest")
                githubRelaseTag = response.json()["tag_name"]
                lv = githubRelaseTag[1:] # ohne v
            except Exception as e:
                logger.logger.error("Fehler beim GitHub-Abruf der aktuellen Version von " + gdtTools[gdtTool] + ": " + str(e))
            labelAktuelleVersionen.append(QLabel("V" + lv))
            labelAktuelleVersionen[i].setFixedWidth(spaltenbreite)
            gdtToolsTabelleLayoutG.addWidget(labelAktuelleVersionen[i], i + 1, 4)
            pushButtonAktualisieren.append(QPushButton("Aktualisieren"))
            pushButtonAktualisieren[i].clicked.connect(lambda checked = False, gdtToolNr = i, latestVersion = lv: self.pushButtonAktualisierenClicked(checked, gdtToolNr, latestVersion))
            updateVerfuegbar = iv != "-" and lv != "?" and versionVeraltet(iv, lv)
            pushButtonAktualisieren[i].setEnabled(updateVerfuegbar)
            pushButtonAktualisieren[i].setToolTip("Kein Update verfügbar")
            if updateVerfuegbar:
                pushButtonAktualisieren[i].setToolTip("Update verfügbar")
            gdtToolsTabelleLayoutG.addWidget(pushButtonAktualisieren[i], i + 1, 5)
            i += 1

        self.pushButtonSchliessen = QPushButton("Updater schließen")
        self.pushButtonSchliessen.clicked.connect(self.pushButtonSchliessenClicked)
        mainLayoutV.addLayout(gdtToolsTabelleLayoutG)
        mainLayoutV.addWidget(self.pushButtonSchliessen)
        self.status = QStatusBar()
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
        einstellungenMenu = menubar.addMenu("Einstellungen")
        einstellungenImportExportAction = QAction("Im- /Exportieren", self)
        einstellungenImportExportAction.triggered.connect(self.einstellungenImportExport) 
        einstellungenImportExportAction.setMenuRole(QAction.MenuRole.NoRole)
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
        einstellungenMenu.addAction(einstellungenImportExportAction)
        hilfeMenu.addAction(hilfeWikiAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeUpdateAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeUeberAction)
        hilfeMenu.addAction(hilfeEulaAction)
        hilfeMenu.addSeparator()
        hilfeMenu.addAction(hilfeLogExportieren)

        self.checkProgrammverzeichnisErreichbarkeit()

    def checkProgrammverzeichnisErreichbarkeit(self):
        alleErreichbar = True
        for i in range(len(gdtTools)):
            if not os.path.exists(self.lineEditProgrammverzeichnisse[i].text()):
                self.lineEditProgrammverzeichnisse[i].setStyleSheet("background:rgb(255,200,200)")
                alleErreichbar = False
            else:
                self.lineEditProgrammverzeichnisse[i].setStyleSheet("background:rgb(255,255,255)")
        return alleErreichbar

    def pushButtonProgrammverzeichnisClicked(self, checked, gdtToolNr):
        fd = QFileDialog(self)
        fd.setFileMode(QFileDialog.FileMode.Directory)
        fd.setWindowTitle("Programmverzeichnis auswählen")
        fd.setModal(True)
        fd.setLabelText(QFileDialog.DialogLabel.Accept, "Speichern")
        fd.setLabelText(QFileDialog.DialogLabel.Reject, "Abbrechen")
        if fd.exec() == 1:
            self.lineEditProgrammverzeichnisse[gdtToolNr].setText(fd.directory().absolutePath())
            self.checkProgrammverzeichnisErreichbarkeit()
            self.configIni["Programmverzeichnisse"][list(gdtTools)[gdtToolNr]] = fd.directory().absolutePath()
            with open(os.path.join(self.configPath, "config.ini"), "w", encoding="utf-8") as configfile:
                self.configIni.write(configfile)
    
    def pushButtonAktualisierenClicked(self, checked, gdtToolNr, latestVersion):
        programmverzeichnis = self.lineEditProgrammverzeichnisse[gdtToolNr].text()
        if os.path.exists(self.lineEditProgrammverzeichnisse[gdtToolNr].text()):
            worker = class_updateWorker.UpdateWorker(gdtTools, programmverzeichnis, gdtToolNr, latestVersion)
            worker.signals.statusmeldung.connect(self.updateStatusBar)
            self.threadpool.start(worker)
        else:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Das Programmverzeichnis existiert nicht.", QMessageBox.StandardButton.Ok)
            mb.setTextFormat(Qt.TextFormat.RichText)
            mb.exec()
            self.lineEditProgrammverzeichnisse[gdtToolNr].setFocus()
            self.lineEditProgrammverzeichnisse[gdtToolNr].selectAll()

    def updateStatusBar(self, message):
        self.status.showMessage(message)

    def updatePruefung(self, meldungNurWennUpdateVerfuegbar = False):
        response = requests.get("https://api.github.com/repos/retconx/gdttoolsupdater/releases/latest")
        githubRelaseTag = response.json()["tag_name"]
        latestVersion = githubRelaseTag[1:] # ohne v
        if versionVeraltet(self.version, latestVersion):
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Die aktuellere ScoreGDT-Version " + latestVersion + " ist auf <a href='https://github.com/retconx/gdttoolsupdater/releases'>Github</a> verfügbar.", QMessageBox.StandardButton.Ok)
            mb.setTextFormat(Qt.TextFormat.RichText)
            mb.exec()
        elif not meldungNurWennUpdateVerfuegbar:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Sie nutzen die aktuelle GDT-Tools Updater-Version.", QMessageBox.StandardButton.Ok)
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
                    mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Das Log-Verzeichnis wurde in den Ordner " + downloadPath + " kopiert.", QMessageBox.StandardButton.Ok)
                    mb.exec()
            except Exception as e:
                mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Problem beim Download des Log-Verzeichnisses: " + str(e), QMessageBox.StandardButton.Ok)
                mb.exec()
        else:
            mb = QMessageBox(QMessageBox.Icon.Warning, "Hinweis von GDT-Tools Updater", "Das Log-Verzeichnis wurde nicht gefunden.", QMessageBox.StandardButton.Ok)
            mb.exec() 

    def einstellungenImportExport(self):
        de = dialogEinstellungenImportExport.EinstellungenImportExport(self.configPath)
        if de.exec() == 1:
            pass
    
    def gdtToolsUpdaterWiki(self, link):
        QDesktopServices.openUrl("https://github.com/retconx/gdttoolsupdater/wiki")

    def gdtToolsLinkGeklickt(self, link):
        QDesktopServices.openUrl(link)

    def pushButtonSchliessenClicked(self):
        if not self.checkProgrammverzeichnisErreichbarkeit():
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von GDT-Tools Updater", "Nicht alle Programmverzeichnisse sind erreichbar (rot hinterlegt). Soll der GDT-Tools Updater dennoch beendet werden?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            mb.setDefaultButton(QMessageBox.StandardButton.Yes)
            mb.button(QMessageBox.StandardButton.Yes).setText("Ja")
            mb.button(QMessageBox.StandardButton.No).setText("Nein")
            if mb.exec() == QMessageBox.StandardButton.Yes:
                sys.exit()
        else:
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