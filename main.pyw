from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5 import uic
import os, sys
from threading import Thread
from queue import Queue, Empty
from random import randint
from torrequest_fix import TorRequest
import json
from tkinter import messagebox
import tkinter as tk

root = tk.Tk()
root.withdraw()

headers = {
    "Accept":           "application/json, text/plain, */*",
    # "Accept-Encoding":  "gzip, deflate, br",
    "Accept-Language":  "en-US,en;q=0.5",
    "Authorization":    None,         # placeholder
    "Connection":       "keep-alive",
    "Content-Length":   None,         # placeholder
    "Content-Type":     "application/json;charset=utf-8",
    "Host":             "api.shortlyai.com",
    "Origin":           "https://shortlyai.com",
    "Referer":          "https://shortlyai.com/",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; rv:78.0) Gecko/20100101 Firefox/78.0",
}

random_str = lambda char_len: ''.join(chr(randint(97, 122)) for _ in range(char_len))

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        uic.loadUi(resource_path("design.ui"), self)
        self.setWindowIcon(QtGui.QIcon(resource_path('icons\\icon.ico')))

        # find the widgets in the xml file
        self.stackedWidget    = self.findChild(QtWidgets.QStackedWidget, "stackedWidget")
        self.generate         = self.findChild(QtWidgets.QPushButton, "pushButton")
        self.generate_once    = self.findChild(QtWidgets.QPushButton, "pushButton_2")
        self.amount_of_runs   = self.findChild(QtWidgets.QSpinBox, "spinBox")
        self.content          = self.findChild(QtWidgets.QPlainTextEdit, "plainTextEdit")
        self.story_background = self.findChild(QtWidgets.QPlainTextEdit, "plainTextEdit_2")
        self.topic            = self.findChild(QtWidgets.QLineEdit, "lineEdit")
        self.status_label     = self.findChild(QtWidgets.QLabel, "label_2")
        self.article_check    = self.findChild(QtWidgets.QRadioButton, "radioButton")
        self.story_check      = self.findChild(QtWidgets.QRadioButton, "radioButton_2")
        self.output_len_slider = self.findChild(QtWidgets.QSlider, "horizontalSlider")
        self.scrollbar        = self.content.verticalScrollBar()

        # dividers
        if dark_mode:
            self.horizonal_l1 = self.findChild(QtWidgets.QFrame, "line")
            self.horizonal_l2 = self.findChild(QtWidgets.QFrame, "line_2")
            brush = QtGui.QBrush(QtGui.QColor(39, 49, 58))
            brush.setStyle(QtCore.Qt.SolidPattern)
            self.set_line_color(brush, [self.horizonal_l1, self.horizonal_l2])
            

        # set connections
        self.generate.clicked.connect(lambda: self.run_thread(self.amount_of_runs.value()))
        self.article_check.toggled.connect(lambda: self.set_essay_background_placeholders())
        self.story_check.toggled.connect(lambda: self.set_essay_background_placeholders())

        self.set_essay_background_placeholders()
        
        self._start_tor_instance_async()
        
        # show ui
        self.show()
        
    
    def toggle_text_boxes(self, toggle):
        self.content.setReadOnly(not toggle)
        self.story_background.setReadOnly(not toggle)
        self.topic.setReadOnly(not toggle)


    status_queue    = Queue()
    content_queue   = Queue()

    def run_thread(self, amount):
        topic = self.topic.text().strip()

        # check inputs for errors
        if not any([topic,
                    self.story_background.toPlainText().strip(),
                    self.content.toPlainText().strip()]):
            messagebox.showerror('EssayGen - Input Error', 'Please enter text in at least one field.')
            return
        elif len(self.story_background.toPlainText().strip()) > 500:
            messagebox.showerror('EssayGen - Input Error', 'The content background field cannot exceed 500 characters. Please try again.')
            return

        # disable editing in text boxes
        self.toggle_text_boxes(False)
        self.stackedWidget.setCurrentIndex(1)
        QtWidgets.QApplication.processEvents()
        
        # start thread
        t = Thread(target=self.run, args=(amount,))
        t.daemon = True
        t.start()

        while t.is_alive() or not self.content_queue.empty():
            try: # check status queue
                status_message = self.status_queue.get(timeout=0.01)
            except Empty:
                pass
            else:
                self.status_label.setText(status_message)
                # show error messages
                if status_message.startswith('Error:'):
                    messagebox.showerror('EssayGen - Run error', status_message+'.')
                self.status_queue.task_done()
            try: # check content_queue
                content = self.content_queue.get(timeout=0.01)
            except Empty:
                pass
            else:
                scrollval = self.scrollbar.value()
                self.content.setPlainText(self.content.toPlainText()+content) # set text

                # not sure why it needs to be ran twice, possibly a PyQt bug
                self.scrollbar.setValue(scrollval)
                self.scrollbar.setValue(scrollval)

                self.content_queue.task_done()
                QtWidgets.QApplication.processEvents() # update text

            QtWidgets.QApplication.processEvents() # update interface
            
            
        # re enable editing in text boxes
        self.toggle_text_boxes(True)
        
        self.stackedWidget.setCurrentIndex(0)
        self.status_label.setText('Preparing...') # Set for next time
        
        if self.runs_left == 0 and self.reset_ident:
            self._start_tor_instance_async() # start new tor instance in background


    def return_error_msgbox(self, msg):
        self.status_queue.put_nowait(msg)
        self.status_queue.join()
        self.runs_left = 0
        self.stackedWidget.setCurrentIndex(0)
        QtWidgets.QApplication.processEvents()

    
    tor_cmd = resource_path('Tor\\tor.exe')
    
    runs_left   = 0
    token       = None
    reset_ident = False    
    starting_tor_instance = Queue()
    
    def _start_tor_instance_async(self):
        t = Thread(target=self.start_tor_instance)
        t.daemon = True
        t.start()
    
    def start_tor_instance(self, set_reset_ident=False):
        self.starting_tor_instance.put('start')
        self.tr = TorRequest(tor_cmd=self.tor_cmd)
        self.reset_ident = set_reset_ident
        self.starting_tor_instance.get()
        self.starting_tor_instance.task_done()
        


    def run(self, amount):
        original_amount = amount

        if not self.starting_tor_instance.empty():
            self.status_queue.put_nowait('Starting TOR instance...')
            self.starting_tor_instance.join()

        while amount > 0:
            # create account
            if self.runs_left == 0:
                if self.reset_ident:
                    self.status_queue.put_nowait('Resetting TOR Identity...')
                    self.start_tor_instance(set_reset_ident=True)
                self.status_queue.put_nowait('Registering new account over TOR...')
                passwrd = random_str(15)
                create_acc = self.tr.post('https://api.shortlyai.com/auth/register/', data={
                    "email":      f"{random_str(randint(8, 12))}{str(randint(0, 999)).rjust(3, '0')}@{random_str(10)}.com",
                    "password1":  passwrd,
                    "password2":  passwrd,
                    "first_name": random_str(randint(8, 15)),
                    "last_name":  random_str(randint(8, 15))
                }).json()
                if create_acc.get('token'):
                    self.runs_left = 4
                    self.token = create_acc['token']
                else:
                    self.return_error_msgbox('Error: Could not register account')
                    return

            # generate
            for _ in range(min(amount, 4)):
                self.status_queue.put_nowait('Generating text...'+ (
                    f' (run {(original_amount - amount) + 1}/{original_amount})'
                    if (original_amount-amount, original_amount) != (0, 1)
                    else ''
                ))
                data = {
                    "ai_instructions": None,
                    "content": self.content.toPlainText(),
                    "document_type": (
                        "article" if self.article_check.isChecked()
                        else (
                            "story" if self.story_check.isChecked()
                            else None
                        )
                    ),
                    "is_command": False,
                    "output_length": self.output_len_slider.value(),
                    "prompt": self.topic.text().strip(),
                    "story_background": self.story_background.toPlainText().strip(),
                    "Authorization": f"JWT {self.token}",
                }
                headers["Authorization"]    = f"JWT {self.token}"
                headers["Content-Length"]   = str(len(json.dumps(data)))
                
                try:
                    resp = self.tr.post('https://api.shortlyai.com/stories/write-for-me/', headers=headers, data=json.dumps(data)).json()
                except:
                    self.return_error_msgbox('Error: Could not generate text')
                    return

                self.runs_left -= 1
                amount -= 1

                # error
                if 'text' not in resp:
                    self.return_error_msgbox('Error: Could not find output')
                    return

                # set text
                if self.content.toPlainText().strip() == '':
                    resp['text'] = resp['text'].lstrip()

                self.content_queue.put_nowait(resp['text'])
                self.content_queue.join()              


    def set_essay_background_placeholders(self):
        if self.article_check.isChecked():
            self.story_background.setPlaceholderText(
                'Article Brief:\n'
                'Provide the AI with a brief of what you are writing about for better output. '
                'Describe it like you are speaking to a friend.'
            )
        elif self.story_check.isChecked():
            self.story_background.setPlaceholderText(
                'Story Background:\n'
                'Tell the AI about the current story setting and characters for better output. '
                'Describe it like you are speaking to a friend.'
            )


    def set_line_color(self, brush, lines: list):
        palette = QtGui.QPalette()
        palette_items = [
            QtGui.QPalette.WindowText,      QtGui.QPalette.Button,      QtGui.QPalette.Light,
            QtGui.QPalette.Midlight,        QtGui.QPalette.Dark,        QtGui.QPalette.Mid,
            QtGui.QPalette.Text,            QtGui.QPalette.BrightText,  QtGui.QPalette.ButtonText,
            QtGui.QPalette.Base,            QtGui.QPalette.Window,      QtGui.QPalette.Shadow,
            QtGui.QPalette.AlternateBase,   QtGui.QPalette.ToolTipBase, QtGui.QPalette.ToolTipText,
            QtGui.QPalette.PlaceholderText,
        ]
        for color_role in [QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled]:
            for palette_item in palette_items:
                palette.setBrush(color_role, palette_item, brush)

        for line in lines:
            line.setPalette(palette)


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
    dark_mode = True
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
else:
    dark_mode = False

# fonts
QtGui.QFontDatabase.addApplicationFont(resource_path('fonts\\Poppins-Medium.ttf'))
QtGui.QFontDatabase.addApplicationFont(resource_path('fonts\\Poppins-Regular.ttf'))


MainWindow = QtWidgets.QMainWindow()

window = UI()
app.exec_()
