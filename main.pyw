from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5 import uic
import os, sys
from threading import Thread
from random import randint
from torrequest import TorRequest
import json
from tkinter import messagebox
import tkinter as tk

root = tk.Tk()
root.withdraw()

class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        self.folder = os.path.dirname(os.path.abspath(__file__))

        uic.loadUi(os.path.join(self.folder, "design.ui"), self)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.folder, 'icons', 'icon.ico')))

        # find the widgets in the xml file
        self.stackedWidget = self.findChild(QtWidgets.QStackedWidget, "stackedWidget")
        self.generate = self.findChild(QtWidgets.QPushButton, "pushButton")
        self.generate_once = self.findChild(QtWidgets.QPushButton, "pushButton_2")
        self.amount_of_runs = self.findChild(QtWidgets.QSpinBox, "spinBox")
        self.content = self.findChild(QtWidgets.QPlainTextEdit, "plainTextEdit")
        self.topic = self.findChild(QtWidgets.QLineEdit, "lineEdit")
        self.status_label = self.findChild(QtWidgets.QLabel, "label_2")

        # set connections
        self.generate.clicked.connect(lambda: self.run_thread(self.amount_of_runs.value()))
        self.generate_once.clicked.connect(lambda: self.run_thread(1))

        # set some variables needed later on
        self.runs_left = 0
        self.token = None
        self.reset_ident = False
        self.status_message = 'Preparing...'

        # show ui
        self.show()
    

    def run_thread(self, amount):
        if self.topic.text().strip() == '':
            messagebox.showerror('ShortlyAI Scrapper - Input Error', 'Please enter an article title.')
            return
        self.stackedWidget.setCurrentIndex(1)
        QtWidgets.QApplication.processEvents()
        t = Thread(target=self.run, args=(amount,))
        t.daemon = True
        t.start()
        while t.is_alive():
            self.status_label.setText(self.status_message)
            QtWidgets.QApplication.processEvents()

    def random_str(self, char_len):
        word = ''
        for _ in range(char_len):
            word += chr(randint(97, 122))
        return word

    def run(self, amount):
        original_amount = amount
        self.status_message = 'Preparing...'

        self.reset_ident = False

        os.chdir(os.path.join(self.folder, "Tor"))
        tr = TorRequest()
        tr.session.proxies.update({'https': 'socks5h://localhost:9050'})

        while amount > 0:
            # create account
            if self.runs_left == 0:
                if self.reset_ident:
                    self.status_message = 'Resetting TOR Identity...'
                    tr = TorRequest()
                    # tr.reset_identity()       No longer needed because tr = TorRequest() resets IP
                self.reset_ident = True
                self.status_message = 'Registering new account over TOR...'
                passwrd = self.random_str(15)
                create_acc = tr.post('https://api.shortlyai.com/auth/register/', data={
                    "email": f"{self.random_str(10)}@{self.random_str(10)}.com",
                    "password1": passwrd,
                    "password2": passwrd,
                    "first_name": self.random_str(15),
                    "last_name": self.random_str(15)
                }).json()
                self.runs_left = 4
                self.token = create_acc['token']
                print(self.token)

            # generate
            for loops in range(4 if amount > 4 else amount):
                self.status_message = f'Generating text... (part {(original_amount - amount) + 1}/{original_amount})'
                data = {
                    "ai_instructions": None,
                    "content": self.content.toPlainText(),
                    "document_type": "article",
                    "is_command": False,
                    "output_length": 2,
                    "prompt": self.topic.text().strip(),
                    "story_background": "",
                    "Authorization": f"JWT {self.token}",
                }
                headers = {
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Authorization": f"JWT {self.token}",
                    "Connection": "keep-alive",
                    "Content-Length": str(len(json.dumps(data))),
                    "Content-Type": "application/json;charset=utf-8",
                    "Host": "api.shortlyai.com",
                    "Origin": "https://shortlyai.com",
                    "Referer": "https://shortlyai.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:78.0) Gecko/20100101 Firefox/78.0",
                }
                resp = tr.post('https://api.shortlyai.com/stories/write-for-me/', headers=headers, data=json.dumps(data))
                print(resp.text)
                self.runs_left -= 1
                amount -= 1

                # set text
                self.content.setPlainText(self.content.toPlainText()+resp.json()['text'].lstrip())

        self.stackedWidget.setCurrentIndex(0)
        QtWidgets.QApplication.processEvents()




def detect_darkmode_in_windows(): # automatically detect dark mode
    try:
        import winreg
    except ImportError:
        return False
    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    reg_keypath = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize'
    try:
        reg_key = winreg.OpenKey(registry, reg_keypath)
    except FileNotFoundError:
        return False

    for i in range(1024):
        try:
            value_name, value, _ = winreg.EnumValue(reg_key, i)
            if value_name == 'AppsUseLightTheme':
                return value == 0
        except OSError:
            break
    return False



# initialize app
app = QApplication(sys.argv)


# dark mode palette ------------------------------
app.setStyle('Fusion')

light_palette = QtGui.QPalette()

if detect_darkmode_in_windows():
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(25,35,45))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(39, 49, 58))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(25,35,45))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(25,35,45))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.blue)
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(20, 129, 216))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
    app.setPalette(dark_palette)


# fonts
fonts_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
QtGui.QFontDatabase.addApplicationFont(os.path.join(fonts_folder, 'Poppins-Medium.ttf'))
QtGui.QFontDatabase.addApplicationFont(os.path.join(fonts_folder, 'Poppins-Regular.ttf'))


MainWindow = QtWidgets.QMainWindow()

window = UI()
app.exec_()