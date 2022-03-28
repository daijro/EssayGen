from PyQt5 import QtGui, QtCore, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtNetwork import QNetworkProxy
from PyQt5 import uic
import sys
from bs4 import BeautifulSoup
import os
import sys
import json


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


class UI(QMainWindow):
    def setupUi(self):
        self.setObjectName("MainWindow")
        self.resize(800, 600)
        self.setWindowTitle('EssayGen - Cloudflare Challenge')
        self.setWindowIcon(QtGui.QIcon(resource_path('icons\\icon.ico')))
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        
        
        self.web_page = WebViewer()
        self.gridLayout.addWidget(self.web_page, 0, 0, 1, 1)
        self.setCentralWidget(self.centralwidget)

        self.gridLayout.addWidget(self.web_page, 0, 0, 1, 1)
        self.show()
    
    def closeEvent(self, event):
        q.put_nowait(False)
        return super().closeEvent(event)


class WebViewer(QtWebEngineWidgets.QWebEngineView):
    def __init__(self):
        super().__init__()
        
        # Automatically click HCaptcha checkbox
        # TODO: Add automatic hcaptcha solver userscript
        jsStr = """
        function isHidden(el) {
            return (el.offsetParent === null);
        };
        if (window.location.href.includes("checkbox")) {
        var checkboxInterval = setInterval(function() {
            if (!document.querySelector("#checkbox")) {
                //Wait until the checkbox element is visible
            } else if (document.querySelector("#checkbox").getAttribute("aria-checked") == "true") {
                clearInterval(checkboxInterval);
            } else if (!isHidden(document.querySelector("#checkbox")) && document.querySelector("#checkbox").getAttribute("aria-checked") == "false") {
                document.querySelector("#checkbox").click();
            } else {
                return;
            }
        }, 2000);}"""
        captchaSolver = QtWebEngineWidgets.QWebEngineScript()
        captchaSolver.setName("qwebchannel.js"); 
        captchaSolver.setInjectionPoint(QtWebEngineWidgets.QWebEngineScript.DocumentCreation) # important
        captchaSolver.setRunsOnSubFrames(True)
        captchaSolver.setWorldId(QtWebEngineWidgets.QWebEngineScript.MainWorld)
        captchaSolver.setSourceCode(jsStr)  # jsStr is what your want to inject to page;
        
        self.profile = QtWebEngineWidgets.QWebEngineProfile()
        self.page = InstrumentedPage(self.profile, self)
        
        # inject js
        self.profile.scripts().insert(captchaSolver)
        
        self.page.setUrl(QtCore.QUrl("https://shortlyai.com"))
        self.setPage(self.page)
    
    
class InstrumentedPage(QtWebEngineWidgets.QWebEnginePage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loadFinished.connect(self.handleLoadFinished)
    
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        # print("acceptNavigationRequest")
        # print(url)
        url_string = url.toString()
        if url_string.startswith('https://www.shortlyai.com'):
            self.load(QtCore.QUrl('https://httpbin.org/headers'))
            
        return super().acceptNavigationRequest(url, _type, isMainFrame)

    def processCurrentPage(self, html):
        url = self.url().toString()
        if 'httpbin.org' in url and q:
            q.put_nowait(json.loads(BeautifulSoup(html, features='lxml').text))

    def handleLoadFinished(self):
        self.toHtml(self.processCurrentPage)

q = None

def run(queue=None):
    global q
    q = queue
    app = QApplication(sys.argv)
    
    proxy = QNetworkProxy()
    proxy.setType(QNetworkProxy.Socks5Proxy)
    proxy.setHostName('localhost')
    proxy.setPort(9050)
    QNetworkProxy.setApplicationProxy(proxy)
    
    MainWindow = QtWidgets.QMainWindow()
    ui = UI()
    ui.setupUi()
    app.exec_()
    
if __name__ == "__main__":
    # DEBUGGING PURPOSES ONLY
    from torrequest_fix import TorRequest
    print('--starting socks5 tor proxy on port 9050--')
    tr = TorRequest(tor_cmd = resource_path('Tor\\tor.exe'))
    print('--started--')
    run()