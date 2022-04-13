from PyQt5.QtWidgets import QMainWindow, QApplication
from multiprocessing import Process, Queue as MPQueue
from PyQt5.QtGui import QSyntaxHighlighter
from PyQt5.QtCore import pyqtSignal
from queue import Queue, Empty
import os, sys

version = 'v1.4.1'

if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5 import uic
    from threading import Thread
    from random import randint
    from requests import Session
    import darkdetect
    import json
    import re
    
    headers = {
        "Host": "api.shortlyai.com",
        "Content-Length": None,
        "Sec-Ch-Ua": "\"(Not(A:Brand\";v=\"8\", \"Chromium\";v=\"99\"",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Sec-Ch-Ua-Mobile": "?0",
        "User-Agent": None,
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Origin": "https://www.shortlyai.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.shortlyai.com/",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9"
    }


import cloudflare_solver

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
        self._window_icon = QtGui.QIcon(resource_path('icons\\icon.ico'))
        self.setWindowIcon(self._window_icon)

        # find the widgets in the xml file
        self.stackedWidget    = self.findChild(QtWidgets.QStackedWidget, "stackedWidget")
        self.generate         = self.findChild(QtWidgets.QPushButton, "pushButton")
        self.generate_once    = self.findChild(QtWidgets.QPushButton, "pushButton_2")
        self.amount_of_runs   = self.findChild(QtWidgets.QSpinBox, "spinBox")
        self.content          = self.findChild(QtWidgets.QTextEdit, "content_field")
        self.story_background = self.findChild(QtWidgets.QTextEdit, "bg_field")
        self.topic            = self.findChild(QtWidgets.QLineEdit, "lineEdit")
        self.status_label     = self.findChild(QtWidgets.QLabel, "label_2")
        self.article_check    = self.findChild(QtWidgets.QRadioButton, "radioButton")
        self.story_check      = self.findChild(QtWidgets.QRadioButton, "radioButton_2")
        self.output_len_slider = self.findChild(QtWidgets.QSlider, "horizontalSlider")


        # syntax highlighter
        self.highlighter = Highlighter(self.content.document())

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
        
        self.set_essay_background_placeholders()
        self.article_check.toggled.connect(lambda: self.set_essay_background_placeholders())
        self.story_check.toggled.connect(lambda: self.set_essay_background_placeholders())
        
        self.setWindowTitle_signal.connect(lambda x: self.setWindowTitle(f'EssayGen {version} - {x}'))
        self.cc_error_msg.connect(lambda: self.cloudflare_error())
 
        self.status_signal.connect(lambda x: self._update_status(x))
        self.err_signal.connect(lambda x: self._error_message(x))
        self.content_signal.connect(lambda x, y: self._set_content(x, y))
        self.done_signal.connect(lambda: self._on_done())
        
        
        self._start_instance_async()
        
        # show ui
        self.show()
        
    
    setWindowTitle_signal   = pyqtSignal(str)
    cc_error_msg            = pyqtSignal()
    cc_error_queue          = Queue()
    
    def cloudflare_error(self):
        self.cc_error_queue.put_nowait(
            QtWidgets.QMessageBox.question(
                self, 'EssayGen - Error', 'Cloudflare challenge window closed. Would you like to retry?', QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Close
            ) == QtWidgets.QMessageBox.Retry
        )
           
    
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


    status_signal   = pyqtSignal(str)
    err_signal      = pyqtSignal(str)
    content_signal  = pyqtSignal(str, str)
    done_signal     = pyqtSignal()

    def _show_writing_stats(self):
        content         = self.content.toPlainText().replace('\u2029', '\n')
        selected_text   = self.content.textCursor().selectedText().replace('\u2029', '\n')
        QtWidgets.QMessageBox.information(self,
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
            if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.question(self, 'EssayGen - Error', 'Commands cannot be nested. Would you like to run the selected commands instead?'):
                nested_commands = self._check_for_commands(stripped, self.content.toPlainText())
                if nested_commands == 1:
                    return
                self.run_thread(self.amount_of_runs.value(), nested_commands)
            self.activateWindow()
            return
        elif '\u2029' in stripped or '\n' in stripped:
            QtWidgets.QMessageBox.critical(self, 'EssayGen - Error', 'Commands can not contain line breaks.')
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
        

    def _multistrip(self, nstring):
        # strip mutliple characters from the start of a string
        for s in nstring:
            if s in ' \n\t\r,.;:!?\u2029': nstring = nstring[1:]
            else: break
        for s in nstring[::-1]:
            if s in ' \n\t\r\u2029': nstring = nstring[:-1]
            else: break
        return nstring
                

    def _over_charlimit(self, cmd_type, cmd, cmd_text):
        if len(cmd_text) > special_commands[cmd_type]:
            excess_chars = len(cmd_text) - special_commands[cmd_type]
            if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.question(self, 'EssayGen - Input Error', f'The {cmd_type} command cannot exceed {special_commands[cmd_type]} characters. Would you like to highlight the excess {excess_chars} character{"s" if excess_chars != 1 else ""}?'):
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
            cmds = re.findall(f'/{cmd_type}' + '\\ \\[[^\n\u2029]+\\]', content, flags=re.IGNORECASE)
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
                    warning = QtWidgets.QMessageBox.warning(self, 'EssayGen - Error', 'You cannot have multiple instances of the same command. Continuing will ONLY run the first instance in the text.')
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
            QtWidgets.QMessageBox.critical(self, 'EssayGen - Input Error', 'Please enter text in at least one field.')
            self.activateWindow()
            return
        elif len(story_bg) > 500:
            QtWidgets.QMessageBox.critical(self, 'EssayGen - Input Error', 'The content background field cannot exceed 500 characters. Please try again.')
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
        

    def _error_message(self, err_msg):
        QtWidgets.QMessageBox.critical(self, 'EssayGen - Run error', err_msg)
        self.activateWindow()
        self._update_status(f'Error: {err_msg.split(".")[0]}') # first sentence
        self.runs_left = 0
        
    def _update_status(self, status_message):
        self.status_label.setText(status_message)

    def _set_content(self, content, cmd=None):
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

    def _on_done(self):
        self.toggle_text_boxes(True)
        self.stackedWidget.setCurrentIndex(0)
        self.status_label.setText('Preparing...')
        
    def _signal_when_done(func):
        def _func(*args):
            func(*args); args[0].done_signal.emit()
        return _func
    
    
    runs_left   = 0
    token       = None
    starting_tor_instance = Queue()
    
    def _start_instance_async(self):
        t = Thread(target=self.start_instance)
        t.daemon = True
        t.start()
    
    def start_instance(self):
        self.setWindowTitle_signal.emit('Starting session...')
        self.sess = Session()
        self.setWindowTitle_signal.emit('Running Cloudflare Challenge...')
        p = Process(target=cloudflare_solver.run, args=(q := MPQueue(),))
        p.daemon = True
        p.start()
        if not (h := q.get()):
            self.cc_error_msg.emit()
            if self.cc_error_queue.get():
                return self.start_instance()
            os._exit(0)
        headers['User-Agent'] = h
        self.setWindowTitle_signal.emit('Ready')
        self.starting_tor_instance.put(True)
        p.terminate()
        
    
    @_signal_when_done
    def run(self, amount, special_runs=None):
        original_amount = amount

        if self.starting_tor_instance.empty():
            try:
                self.starting_tor_instance.get(timeout=60)
            except Empty:
                self.setWindowTitle_signal('Failed')
                self.err_signal.emit('Failed to start')
                return
            
        while amount > 0:
            # create account
            if self.runs_left == 0:
                self.status_signal.emit('Registering new account...')
                self.sess.cookies.clear()
                passwrd = random_str(15)
                data = {
                    "email":      f"{random_str(randint(8, 12))}{str(randint(0, 999)).rjust(3, '0')}@{random_str(10)}.com",
                    "password1":  passwrd,
                    "password2":  passwrd,
                    "first_name": random_str(randint(8, 15)),
                    "last_name":  random_str(randint(8, 15))
                }
                headers['Content-Length'] = str(len(str(data)))
                create_acc = self.sess.post('https://api.shortlyai.com/auth/register/', data=json.dumps(data), headers=headers).json()
                if create_acc.get('token'):
                    self.runs_left = 4
                    self.token = create_acc['token']
                else:
                    self.err_signal.emit('Could not register account')
                    return

            # generate
            for _ in range(min(amount, 4)):
                self.status_signal.emit('Generating text...'+ (
                    f' ({"command" if special_runs else "run"} {(original_amount - amount) + 1}/{original_amount})'
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
                    resp = self.sess.post('https://api.shortlyai.com/stories/write-for-me/', headers=headers, data=json.dumps(data)).json()
                except Exception as e:
                    self.err_signal.emit(f'Could not generate text. Error details are provided below\n{e}')
                    return

                # error
                if not resp.get('text'):
                    if 'message' in resp:
                        self.err_signal.emit(f'{resp["message"]}')
                    else:
                        self.err_signal.emit('Could not find output')
                    return

                # set text
                if not self.content.toPlainText().strip() or special_runs:
                    resp['text'] = resp['text'].lstrip()
                    
                self.content_signal.emit(
                    resp['text'],
                    special_runs[original_amount-amount][1] if special_runs else ''
                )

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
        for color_role in [QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled]:
            for palette_item in [QtGui.QPalette.Light, QtGui.QPalette.Dark]:
                palette.setBrush(color_role, palette_item, brush)

        for line in lines:
            line.setPalette(palette)


class Highlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(Highlighter, self).__init__(parent)

        self.keywordFormat = QtGui.QTextCharFormat()
        self.keywordFormat.setForeground(QtGui.QColor(200, 255, 200) if dark_mode else QtCore.Qt.darkGreen)
        self._re_obj = re.compile(f'/({"|".join(special_commands.keys())})'+'\\ \\[([^\n\u2029]+)?\\]', flags=re.IGNORECASE)
        
    def highlightBlock(self, text):
        for match in re.finditer(self._re_obj, text):
            i, j = match.span()
            self.setFormat(i, j-i, self.keywordFormat)


if __name__ == "__main__":
    # initialize app
    app = QApplication(sys.argv)

    app.setStyle('Fusion')

    # dark mode palette
    if (dark_mode := darkdetect.isDark()):
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
    QtGui.QFontDatabase.addApplicationFont(resource_path('fonts\\Poppins-Medium.ttf'))
    QtGui.QFontDatabase.addApplicationFont(resource_path('fonts\\Poppins-Regular.ttf'))


    MainWindow = QtWidgets.QMainWindow()

    window = UI()
    app.exec_()
