from PyQt5 import QtGui, QtCore, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
import sys
import os


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


class UI(QMainWindow):
    def setupUi(self):
        self.setObjectName("MainWindow")
        self.resize(700, 350)
        self.setWindowTitle('EssayGen - Cloudflare Challenge')
        self.setWindowIcon(QtGui.QIcon(resource_path('icons\\icon.ico')))
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        
        self.web_page = WebViewer(window=self)
        self.gridLayout.addWidget(self.web_page, 0, 0, 1, 1)
        self.setCentralWidget(self.centralwidget)

        self.gridLayout.addWidget(self.web_page, 0, 0, 1, 1)
        self.show()
    
    def closeEvent(self, event):
        if q:
            q.put_nowait(False)
            self.hide()
            try: input() # pause
            except EOFError: exit()
        else:
            super().closeEvent(event)


class WebInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent, _window):
        self.window = _window
        super().__init__(parent)
    
    def interceptRequest(self, info):
        if info.requestUrl().toString().startswith('https://hcaptcha.com/getcaptcha') and not self.window.isMaximized():
            self.window.resize(self.window.width(), max(610, self.window.height())) # expand window
            self.window.raise_()
            self.window.activateWindow()
            

class WebViewer(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, window):
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
                // Wait until the checkbox element is visible
            } else if (document.querySelector("#checkbox").getAttribute("aria-checked") == "true") {
                clearInterval(checkboxInterval);
            } else if (!isHidden(document.querySelector("#checkbox")) && document.querySelector("#checkbox").getAttribute("aria-checked") == "false") {
                document.querySelector("#checkbox").click();
            } else {
                return;
            }
        }, 500);}"""
        hcaptchaClicker = QtWebEngineWidgets.QWebEngineScript()
        hcaptchaClicker.setName("qwebchannel.js"); 
        hcaptchaClicker.setInjectionPoint(QtWebEngineWidgets.QWebEngineScript.DocumentCreation) # important
        hcaptchaClicker.setRunsOnSubFrames(True)
        hcaptchaClicker.setWorldId(QtWebEngineWidgets.QWebEngineScript.MainWorld)
        hcaptchaClicker.setSourceCode(jsStr)
        
        self.profile = QtWebEngineWidgets.QWebEngineProfile()
        self.profile.setUrlRequestInterceptor(WebInterceptor(self, window))
        self.page = InstrumentedPage(self.profile, self)
        
        # inject js
        self.profile.scripts().insert(hcaptchaClicker)
        
        self.page.setUrl(QtCore.QUrl("https://shortlyai.com"))
        self.setPage(self.page)
    
    
class InstrumentedPage(QtWebEngineWidgets.QWebEnginePage):
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if url.toString().startswith('https://www.shortlyai.com'):
            if q:
                q.put_nowait(self.profile().httpUserAgent())
            else:
                self.load(QtCore.QUrl('https://httpbin.org/headers'))
        return super().acceptNavigationRequest(url, _type, isMainFrame)

q = None

def run(queue=None):
    global q
    q = queue
    app = QApplication(sys.argv)
    
    ui = UI()
    ui.setupUi()
    app.exec_()
    
    
if __name__ == "__main__":
    # DEBUGGING PURPOSES ONLY
    run()
