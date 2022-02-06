from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5 import uic
import os, sys
from threading import Thread
from queue import Queue, Empty
from random import randint
from torrequest_fix import TorRequest
import json
import re
from tkinter import messagebox
import tkinter as tk

root = tk.Tk()
root.withdraw()

headers = {
    "Accept":           "application/json, text/plain, */*",
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

special_commands = {
    'instruct':  200,
    'rewrite':   160,
    'shorten':   200,
    'expand':    120,
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

        # dividers
        if dark_mode:
            self.horizonal_l1 = self.findChild(QtWidgets.QFrame, "line")
            self.horizonal_l2 = self.findChild(QtWidgets.QFrame, "line_2")
            brush = QtGui.QBrush(QtGui.QColor(39, 49, 58))
            brush.setStyle(QtCore.Qt.SolidPattern)
            self.set_line_color(brush, [self.horizonal_l1, self.horizonal_l2])
            

        # set connections
        self.generate.clicked.connect(lambda: self._command_shortcut())
        
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+Return'), self).activated.connect(lambda: self._command_shortcut())
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+P'), self).activated.connect(lambda: self._command_shortcut('rewrite'))
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+['), self).activated.connect(lambda: self._command_shortcut('shorten'))
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+]'), self).activated.connect(lambda: self._command_shortcut('expand'))
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+Shift+C'), self).activated.connect(lambda: self._show_writing_stats())
        
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
        
    
    def _cut_off_context(self, text, index):
        # use /// to cut off context relative to a given index
        c1, c2 = text[:index].rfind('///'), text[index:].find('///')
        return text[(None if c1 == -1 else c1+3):(None if c2 == -1 else c2+index)]
    
        
    def _get_content_nocommand(self):
        cpos = self.content.textCursor().position()
        content_input = self.content.toPlainText()[:cpos] if cpos else self.content.toPlainText()
        if '///' in content_input: content_input = content_input[content_input.rfind('///')+3:]
        return content_input    
    

    def format_content_data(self, special_command_list):
        content_input = self.content.toPlainText()
        cmd_type, cmd, text = special_command_list
        cmd_index = content_input.find(cmd)
        if '///' in content_input: content_input = self._cut_off_context(content_input, cmd_index)
        return [
            cmd_type, # command type
            text, # command text
            content_input[max(0, cmd_index - 300):cmd_index + len(cmd) + 300].replace(cmd, text), # context w/300 char margin
            content_input.replace(cmd, '') # content (remove command)
        ]


    status_queue    = Queue()
    content_queue   = Queue()

    def _show_writing_stats(self):
        content         = self.content.toPlainText().replace('\u2029', '\n')
        selected_text   = self.content.textCursor().selectedText().replace('\u2029', '\n')
        messagebox.showinfo(
            'EssayGen - Writing Stats',
            (
                "Selected character count:\t  "     + str(len(selected_text)) +
                "\nSelected chars (no spaces):\t  " + str(len(re.sub(r'\s', '', selected_text))) +
                "\nSelected word count:\t  "        + str(len(selected_text.split()))
            ) if selected_text else (
                "Character count:\t   "     + str(len(content)) +
                "\nChars (no spaces):\t   " + str(len(re.sub(r'\s', '', content))) +
                "\nWord count:\t   "        + str(len(content.split()))
            )
        )
        self.activateWindow()
        
    _running = False
    def _command_shortcut(self, key='instruct'):
        if self._running:
            return
        cursor = self.content.textCursor()
        selection = cursor.selectedText()
        stripped = self._multistrip(selection)
        
        if not stripped:
            if key == 'instruct':
                self.run_thread(self.amount_of_runs.value())
            return
        elif re.search(f'/({"|".join(special_commands.keys())})'+'\\ \\[[^\n\u2029]+\\]', stripped, flags=re.IGNORECASE):
            if messagebox.askyesno('EssayGen - Error', 'Commands cannot be nested. Would you like to run the selected commands instead?'):
                nested_commands = self._check_for_commands(stripped, self.content.toPlainText())
                if nested_commands == 1:
                    return
                self.run_thread(self.amount_of_runs.value(), nested_commands)
            self.activateWindow()
            return
        elif '\u2029' in stripped or '\n' in stripped:
            messagebox.showerror('EssayGen - Error', 'Commands can not contain line breaks.')
            self.activateWindow()
            return
        
        cursor.beginEditBlock()
        cmd = f'/{key} [{stripped}]'
        cursor.removeSelectedText()
        cursor.insertText(
            selection.split(stripped)[0]
            + cmd +
            selection.split(stripped)[-1]
        )
        cursor.endEditBlock()
        
        if self._over_charlimit(key, cmd, stripped):
            return
        
        self._running = True
        self.run_thread(self.amount_of_runs.value(), [(key, cmd, selection)])
        self._running = False
        

    def _multistrip(self, string):
        # strip mutliple characters from the start of a string
        nstring = string
        for s in string:
            if s in ' \n\t\r,.;:!?\u2029': nstring = nstring[1:]
            else: break
        for s in string[::-1]:
            if s in ' \n\t\r\u2029': nstring = nstring[:-1]
            else: break
        return nstring
                

    def _over_charlimit(self, cmd_type, cmd, cmd_text):
        if len(cmd_text) > special_commands[cmd_type]:
            excess_chars = len(cmd_text) - special_commands[cmd_type]
            if messagebox.askyesno('EssayGen - Input Error', f'The {cmd_type} command cannot exceed {special_commands[cmd_type]} characters. Would you like to highlight the excess {excess_chars} character{"s" if excess_chars != 1 else ""}?'):
                cmd_pos = self.content.toPlainText().find(cmd) + len(cmd_type) + 3
                cmd_end = cmd_pos + len(cmd_text)
                cursor = self.content.textCursor()
                cursor.setPosition(cmd_pos + special_commands[cmd_type], QtGui.QTextCursor.MoveAnchor)
                cursor.setPosition(cmd_end, QtGui.QTextCursor.KeepAnchor)
                self.content.setTextCursor(cursor)
            self.activateWindow()
            return True
        
        
    def _check_for_commands(self, content, full_content=None):
        _multi_run_warning = True
        special_runs = []
        for cmd_type in special_commands:
            cmds = re.findall('/'+cmd_type+'\\ \\[[^\n\u2029]+\\]', content, flags=re.IGNORECASE)
            for cmd in cmds:
                # remove /command [] using re
                cmd_text = cmd[len(cmd_type)+3:-1]
                if self._over_charlimit(cmd_type, cmd, cmd_text):
                    return 1 # error
                if (
                    full_content
                    and full_content.count(cmd) > 1
                    and _multi_run_warning
                ):
                    warning = messagebox.askokcancel('EssayGen - Error', 'You cannot have multiple instances of the same command. Continuing will ONLY run the first instance in the text.')
                    self.activateWindow()
                    if warning:
                        _multi_run_warning = False # only warn once
                    else:
                        return 1
                special_runs.append((cmd_type, cmd, cmd_text))
        return special_runs


    def run_thread(self, amount, shortcut_command=False):
        topic    = self.topic.text().strip()
        content  = self.content.toPlainText().strip()
        story_bg = self.story_background.toPlainText().strip()

        # check inputs for errors
        if not any([topic, story_bg, content]):
            messagebox.showerror('EssayGen - Input Error', 'Please enter text in at least one field.')
            self.activateWindow()
            return
        elif len(story_bg) > 500:
            messagebox.showerror('EssayGen - Input Error', 'The content background field cannot exceed 500 characters. Please try again.')
            self.activateWindow()
            return

        # check for special commands
        special_runs = shortcut_command or self._check_for_commands(content)
        if special_runs == 1:
            return
        elif special_runs:
            amount = len(special_runs)
        
        # disable editing in text boxes
        self.toggle_text_boxes(False)
        self.stackedWidget.setCurrentIndex(1)
        QtWidgets.QApplication.processEvents()
        
        # start thread
        t = Thread(target=self.run, args=(amount, special_runs))
        t.daemon = True
        t.start()

        while t.is_alive() or not self.content_queue.empty():
            try: # check status queue
                status_message = self.status_queue.get(timeout=0.01)
            except Empty:
                pass
            else:
                # show error messages
                if status_message.startswith('Error:'):
                    messagebox.showerror('EssayGen - Run error', status_message)
                    self.activateWindow()
                    self.status_label.setText(status_message.split('.')[0]) # first sentence
                else:
                    self.status_label.setText(status_message)
                self.status_queue.task_done()
            try: # check content_queue
                content, cmd = self.content_queue.get(timeout=0.01)
            except Empty:
                pass
            else:
                scrollval   = self.content.verticalScrollBar().value()
                old_content = self.content.toPlainText()

                # insert content using cursor
                cursor = self.content.textCursor()
                cursor.beginEditBlock()
                
                if cmd:
                    cmd_pos_start = old_content.find(cmd)
                    cmd_pos_end   = cmd_pos_start + len(cmd)
                    
                    # remove the command
                    cursor.setPosition(cmd_pos_start, QtGui.QTextCursor.MoveAnchor)
                    cursor.setPosition(cmd_pos_end, QtGui.QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.setPosition(cmd_pos_start)
                    
                cursor.insertText(content)
                cursor.endEditBlock()
                # set text cursor
                self.content.setTextCursor(cursor)
                
                # set text scrollbar to same position
                scrollbar = QtWidgets.QScrollBar()
                scrollbar.setValue(scrollval)
                self.content.setVerticalScrollBar(scrollbar)

                self.content_queue.task_done()

            QtWidgets.QApplication.processEvents() # update interface
            
        # re enable editing in text boxes
        self.toggle_text_boxes(True)
        
        self.stackedWidget.setCurrentIndex(0)
        self.status_label.setText('Preparing...') # Set for next time
        
        if not self.runs_left and self.reset_ident:
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
        self.tr = TorRequest(tor_cmd=self.tor_cmd)
        self.reset_ident = set_reset_ident
        self.starting_tor_instance.put('_')
        

    def run(self, amount, special_runs=[]):
        original_amount = amount

        if self.starting_tor_instance.empty():
            self.status_queue.put_nowait('Starting TOR instance...')
            try:
                self.starting_tor_instance.get(timeout=10)
            except Empty:
                self.return_error_msgbox('Error: TOR instance failed to start')
                return
            
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
                    
                # create request
                data = {
                    "ai_instructions": None,
                    "content": self.format_content_data(special_runs[original_amount-amount])
                        if special_runs else self._get_content_nocommand(),
                    "document_type": "article" if self.article_check.isChecked() else "story",
                    "is_command": bool(special_runs),
                    "output_length": self.output_len_slider.value(),
                    "prompt": self.topic.text().strip(),
                    "story_background": self.story_background.toPlainText().strip(),
                    "Authorization": f"JWT {self.token}",
                }
                headers["Authorization"]    = f"JWT {self.token}"
                headers["Content-Length"]   = str(len(json.dumps(data)))
                
                try:
                    resp = self.tr.post('https://api.shortlyai.com/stories/write-for-me/', headers=headers, data=json.dumps(data)).json()
                except Exception as e:
                    self.return_error_msgbox(f'Error: Could not generate text. Error details are provided below\n{e}')
                    return

                # error
                if not resp.get('text'):
                    if 'message' in resp:
                        self.return_error_msgbox(f'Error: {resp["message"]}')
                    else:
                        self.return_error_msgbox('Error: Could not find output')
                    return

                # set text
                if not self.content.toPlainText().strip() or special_runs:
                    resp['text'] = resp['text'].lstrip()
                    
                self.content_queue.put_nowait((
                    resp['text'],
                    special_runs[original_amount-amount][1] if special_runs else ''
                ))
                self.content_queue.join()

                self.runs_left  -= 1
                amount          -= 1


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
