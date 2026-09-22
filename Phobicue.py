import os
import sys
import time
import random
import cv2
import torch
import numpy as np
import win32gui, win32ui, win32con, win32api
from ctypes import windll
from ultralytics import YOLO
from PyQt6.QtWidgets import (
    QWidget, 
    QApplication, 
    QVBoxLayout, 
    QMainWindow, 
    QLineEdit, 
    QPushButton,
    QMessageBox
)
from PyQt6.QtGui import QImage
from PyQt6.QtCore import pyqtSlot, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent, QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

_width = 0
_height = 0
image_extensions = ('.jpg', '.jpeg', '.png')

if torch.cuda.is_available():
    device = torch.device("cuda")
else:   
    device = torch.device("cpu")

class PreLauncher(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Phobicue Pre-Launcher")

        layout = QVBoxLayout()

        self.window_field = QLineEdit()
        self.window_field.setPlaceholderText("Please Enter Window Name (eg. Google Chrome)")
        self.model_field = QLineEdit()
        self.model_field.setPlaceholderText("Please Enter model Name (eg. yolo26m.pt)")

        self.continue_button = QPushButton("Continue")
        self.exit_button = QPushButton("Exit")
        self.continue_button.clicked.connect(self.launch)
        self.exit_button.clicked.connect(QApplication.quit)

        layout.addWidget(self.window_field)
        layout.addWidget(self.model_field)
        layout.addWidget(self.continue_button)
        layout.addWidget(self.exit_button)

        self.setLayout(layout)

    def launch(self):
        window_name = self.window_field.text().strip()
        model_name = self.model_field.text().strip()

        # Make sure both fields aren't empty
        if not window_name or not model_name:
            QMessageBox.warning(
                self,
                "Missing Input",
                "Please enter both a window name and a model name."
            )
            return

        # Try to find the window
        window_handle = self.find_window(window_name)

        if window_handle is None:
            QMessageBox.critical(
                self,
                "Window Not Found",
                f"Could not find the window:\n\n{window_name}"
            )

            # Clear inputs
            self.window_field.clear()
            self.model_field.clear()
            self.window_field.setFocus()

            return

        if model_name[-3:] != ".pt":
            QMessageBox.critical(
                self,
                "Invalid Model Name",
                "Valid YOLO model name must end with .pt"
            )

            # Clear inputs
            self.window_field.clear()
            self.model_field.clear()
            self.window_field.setFocus()

            return

        # Try to load the model
        try:
            model = YOLO(model_name)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Model Loading Failed",
                f"Could not load the model:\n\n{model_name}\n\n"
                f"Error:\n{e}"
            )

            # Clear inputs
            self.window_field.clear()
            self.model_field.clear()
            self.model_field.setFocus()
            return

        # Everything succeeded
        self.open_main_window(window_handle, model.to(device))

    def find_window(self, window_name):
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd == 0:
            return None
        return hwnd

    def open_main_window(self, window_handle, model):
        self.main_window = MainWindow(window_handle, model)
        self.main_window.resize(1240, 768)
        self.main_window.show()
        self.hide()

class Detections:
    def __init__(self, box, counter):
        self.box = box
        self.counter = counter

class MainWindow(QMainWindow):
    def __init__(self, window_handle, model):
        super().__init__()

        if os.path.isdir("custom_images"):
            image_available = [os.path.join("custom_images", f) for f in os.listdir("custom_images") if os.path.isfile(os.path.join("custom_images", f)) and f.lower().endswith(image_extensions)]
        else:
            image_available = []

        self.setWindowTitle("Phobicue")
        self.move(0, 0)

        self.setMouseTracking(True)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.VBL = QVBoxLayout(central_widget)

        self.video = GLVideoWidget()
        self.VBL.addWidget(self.video)

        self.censor_mode = "black"
        self.detection_strictness = 0.25
        self.frame_per_detection = 1
        
        self.Worker = VideoWorker(
            window_handle, 
            model, 
            self.censor_mode, 
            image_available, 
            self.detection_strictness,
            self.frame_per_detection)

        self.video.mousePressed.connect(self.Worker.MousePress)
        self.video.mouseMoved.connect(self.Worker.MouseMove)
        self.video.mouseReleased.connect(self.Worker.MouseRelease)
        self.video.KeyPressed.connect(self.Worker.MouseScrolled)
        self.video.EnterPressed.connect(self.Worker.EnterPressed)

        self.Worker.ImageUpdate.connect(self.video.UpdateFrame)
        self.Worker.error.connect(self.handle_worker_error)
        self.Worker.warning.connect(self.handle_worker_warning)
        self.Worker.hint.connect(self.handle_worker_info)
        self.Worker.start()
    
        menu_bar = self.menuBar()
        win = menu_bar.addMenu("&Phobicue")
        quit = win.addAction("Quit")
        quit.triggered.connect(self.close)

        censor_option = menu_bar.addMenu("Mask Options")
        disabled = censor_option.addAction("Disabled")
        black = censor_option.addAction("Black")
        blur = censor_option.addAction("Blurring")
        image = censor_option.addAction("Custom Image")

        disabled.triggered.connect(
            lambda: self.set_censor_mode("disabled")
        )
        black.triggered.connect(
            lambda: self.set_censor_mode("black")
        )
        blur.triggered.connect(
            lambda: self.set_censor_mode("blur")
        )
        image.triggered.connect(
            lambda: self.set_censor_mode("img")
        )

        strictness_option = menu_bar.addMenu("Detection Strictness")
        weak = strictness_option.addAction("Loose")
        normal = strictness_option.addAction("Normal")
        strong = strictness_option.addAction("Strict")
        very_strong = strictness_option.addAction("Very Strict")

        weak.triggered.connect(
            lambda: self.set_detection_strictness(0.15)
        )
        normal.triggered.connect(
            lambda: self.set_detection_strictness(0.25)
        )
        strong.triggered.connect(
            lambda: self.set_detection_strictness(0.45)
        )
        very_strong.triggered.connect(
            lambda: self.set_detection_strictness(0.65)
        )

        frame_per_detection = menu_bar.addMenu("Detection Frequency")
        every_frame = frame_per_detection.addAction("Every Frame (Recommended)")
        once_per_two = frame_per_detection.addAction("Once per 2 Frames")
        once_per_three = frame_per_detection.addAction("Once per 3 Frames")
        once_per_five = frame_per_detection.addAction("Once per 5 Frames")
        every_frame.triggered.connect(
            lambda: self.set_frame_per_detection(1)
        )
        once_per_two.triggered.connect(
            lambda: self.set_frame_per_detection(2)
        )
        once_per_three.triggered.connect(
            lambda: self.set_frame_per_detection(3)
        )
        once_per_five.triggered.connect(
            lambda: self.set_frame_per_detection(5)
        )

        about = menu_bar.addAction("About")
        about.triggered.connect(
            lambda: self.show_description()
        )

    def set_censor_mode(self, mode):
        self.censor_mode = mode 
        self.Worker.set_censor_mode(mode)

    def set_detection_strictness(self, detection_strictness):
        self.detection_strictness = detection_strictness
        self.Worker.set_detection_strictness(detection_strictness)

    def set_frame_per_detection(self, frame_per_detection):
        self.frame_per_detection = frame_per_detection
        self.Worker.set_frame_per_detection(frame_per_detection)

    def handle_worker_warning(self, warning_message):
        QMessageBox.warning(
            self,
            "Warning",
            f"Warning: {warning_message}"
        )

    def handle_worker_error(self, error_message):
        reply = QMessageBox.critical(
            self,
            "Fatal Error",
            f"Error: {error_message}\n\nWould you like to exit the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            print("User requested exit. Shutting down application safely...")
            
            # Clean up the worker thread to prevent memory leaks/hangs on exit
            if self.Worker.isRunning():
                self.Worker.quit()
                self.Worker.wait() 
                
            # 3. Tell the QApplication instance to close everything
            QApplication.quit()

    def handle_worker_info(self, info_message):
        QMessageBox.information(
            self,
            "Information",
            f"Hint: {info_message}"
        )

    def show_description(self):
        QMessageBox.information(
            self,
            "About",
            "Phobicue is a window censoring application designed and developed by Deming Qian."
        )

    def closeEvent(self, event):
        self.Worker.stop()
        event.accept()

class GLVideoWidget(QOpenGLWidget):
    mousePressed = pyqtSignal(float, float)
    mouseMoved = pyqtSignal(float, float)
    mouseReleased = pyqtSignal(float, float)
    KeyPressed = pyqtSignal(int)
    EnterPressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.frame = None
        self.width = 0
        self.height = 0

    @pyqtSlot(np.ndarray)
    def UpdateFrame(self, frame):
        self.frame = frame
        self.update() 

    def paintGL(self):
        if self.frame is None:
            return
        
        h, w, ch = self.frame.shape
        bytes_per_line = ch * w

        frame = self.frame.copy()

        img = QImage(
            frame.data,
            w, 
            h, 
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        rect = self.rect()
        self.width = rect.width()
        self.height = rect.height()

        painter = QPainter(self)
        painter.drawImage(rect, img)

    def mousePressEvent(self, event: QMouseEvent):
        pos = event.pos()
        mouse_x = pos.x()
        mouse_y = pos.y()
        try:
            self.mousePressed.emit(mouse_x / self.width, mouse_y / self.height)
        except ZeroDivisionError:
            return
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        mouse_x = pos.x()
        mouse_y = pos.y()
        try:
            self.mouseMoved.emit(mouse_x / self.width, mouse_y / self.height)
        except ZeroDivisionError:
            return
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        pos = event.pos()
        mouse_x = pos.x()
        mouse_y = pos.y()
        try:
            self.mouseReleased.emit(mouse_x / self.width, mouse_y / self.height)
        except ZeroDivisionError:
            return
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up:
            self.KeyPressed.emit(1)
        elif key == Qt.Key.Key_Down:
            self.KeyPressed.emit(-1)
        elif key == Qt.Key.Key_Enter:
            self.EnterPressed.emit()
        event.accept()

class VideoWorker(QThread):
    ImageUpdate = pyqtSignal(np.ndarray)
    warning = pyqtSignal(str)
    error = pyqtSignal(str)
    hint = pyqtSignal(str)

    def __init__(self, window_handle, model, mode, image_available, detection_strictness, frame_per_detection):
        global _width, _height
        super().__init__()
        self.hwnd = window_handle
        self.model = model
        self.censor_mode = mode
        self.image_available = image_available
        self.detection_strictness = detection_strictness
        self.frame_per_detection = frame_per_detection

        self.ThreadActive = True
        self.mouse_down = False
        self.force_detect = False

        
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        _width = right - left
        _height = bottom - top

        # Get window handle from target window
        self.hdc = win32gui.GetWindowDC(self.hwnd)
        self.mfcDC  = win32ui.CreateDCFromHandle(self.hdc)
        self.saveDC = self.mfcDC.CreateCompatibleDC()

        # Get bitmap as image input buffer
        self.saveBitMap = win32ui.CreateBitmap()
        self.saveBitMap.CreateCompatibleBitmap(self.mfcDC, _width, _height)

    def run(self):
        global _height, _width

        if self.image_available != []:
            self.image_available = [cv2.imread(img_path) for img_path in self.image_available]

        frame_count = 0
        detections = []
        while self.ThreadActive:

            try:
                time.sleep(0.01)

                left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
                _width = right - left
                _height = bottom - top
                self.saveDC.SelectObject(self.saveBitMap)
                result = windll.user32.PrintWindow(self.hwnd, self.saveDC.GetSafeHdc(), 2)

                if result != 1:
                    continue

                bmpstr = self.saveBitMap.GetBitmapBits(True)
                cv_frame = np.frombuffer(bmpstr, dtype=np.uint8)

                array = cv_frame.reshape(_height, _width, 4).copy()
                array = np.ascontiguousarray(array[:, :, :3][:, :, ::-1])

                if self.force_detect or frame_count % self.frame_per_detection == 0:
                    detections.extend(self.DetectAnimal(array, self.detection_strictness))
                    self.force_detect = False

                for detect in detections:
                    array = self.RegionMask(array, detect.box)
                    detect.counter -= 1

                    if detect.counter == 0:
                        detections.remove(detect)

                self.ImageUpdate.emit(array)

                frame_count += 1

            except Exception as e:
                self.error.emit(str(e))
                self.ThreadActive = False

        # clean up
        win32gui.DeleteObject(self.saveBitMap.GetHandle())
        self.saveDC.DeleteDC()
        self.mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, self.hdc)

    def DetectAnimal(self, frame, conf_threshold):
        '''
        Returns a list of bounding boxex on successfully detected animals.
        '''
        source = cv2.resize(frame, (1280, 1280))
        with torch.no_grad():
            results = self.model.predict(source=source, show=False, save=False, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue
            box_list = result.boxes.xyxy.tolist()
            conf_list = result.boxes.conf.tolist()

            for box, conf in zip(box_list, conf_list):
                if conf >= conf_threshold:
                    x1, y1, x2, y2 = map(int, box)
                    x1 = int(x1 / 1280 * _width)
                    y1 = int(y1 / 1280 * _height)
                    x2 = int(x2 / 1280 * _width)
                    y2 = int(y2 / 1280 * _height)
                    if conf > 0.5:
                        counter = 10
                    else:
                        counter = 5
                    detections.append(Detections((x1, y1, x2, y2), counter))

        return detections

    def RegionMask(self, frame, box):
        '''
        Maskss region based on successful detections.
        '''
        x1, y1, x2, y2 = box
        roi = frame[y1:y2, x1:x2]
        width = x2 - x1
        height = y2 - y1

        if roi.size == 0:
            return 

        match self.censor_mode:
            case "disabled":
                return frame
            case "black":
                frame[y1:y2, x1:x2] = 0
                return frame
            case "blur":
                small_img = cv2.resize(frame[y1:y2, x1:x2], (int(width * 0.25), int(height * 0.25)), interpolation=cv2.INTER_LINEAR)
                blurred_small = cv2.GaussianBlur(small_img, (5, 5), 0)
                final_heavy_blur = cv2.resize(blurred_small, (int(width), int(height)), interpolation=cv2.INTER_CUBIC)
                frame[y1:y2, x1:x2] = final_heavy_blur
                return frame
            case "img":
                img = random.choice(self.image_available)
                img = cv2.resize(img, (int(width), int(height)))
                frame[y1:y2, x1:x2] = img
                return frame

    def set_censor_mode(self, mode):
        if mode == "img":
            if self.image_available == []:
                self.warning.emit("No image found in '/custom_images' folder! (only file extensions .jpg, .jpeg, .png allowed)" )
            else:
                self.warning.emit("Setting censor mode to custom images may results in wrong image color!")
                self.censor_mode = mode
        else:
            self.censor_mode = mode

    def set_detection_strictness(self, strictness):
        strinctness_text = ""
        match strictness:
            case 0.15:
                strinctness_text = "Loose"
            case 0.25:
                strinctness_text = "Normal"
            case 0.45:
                strinctness_text = "Strict"
            case 0.65:
                strinctness_text = "Very Strict"
        self.hint.emit(f"Detection strictness set to {strinctness_text}.")
        self.detection_strictness = strictness

    def set_frame_per_detection(self, frame_per_detection):
        self.frame_per_detection = frame_per_detection
        match frame_per_detection:
            case 1:
                self.hint.emit("The app now detects every frame.")
            case 2:
                self.warning.emit("The app now detects once per 2 frames.\n\nLess frequent detection can improve performance, but may also results in ineffective censoring!")
            case 3:
                self.warning.emit("The app now detects once per 3 frames.\n\nLess frequent detection can improve performance, but may also results in ineffective censoring!")
            case 5:
                self.warning.emit("The app now detects once per 5 frames.\n\nLess frequent detection can improve performance, but may also results in ineffective censoring!")

    def stop(self):
        self.ThreadActive = False
        self.wait()
        self.quit()

    @pyqtSlot(float, float)
    def MousePress(self, x, y):
        win32gui.SetForegroundWindow(self.hwnd)
        self.force_detect = True
        """Send LMB down at x, y"""
        x = int(x * _width)
        y = int(y * _height)
        lParam = win32api.MAKELONG(x, y)
        win32gui.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        self.mouse_down = True

    @pyqtSlot(float, float)
    def MouseMove(self, x, y):
        """Send mouse move; only moves if pressed"""
        if self.mouse_down:
            x = int(x * _width)
            y = int(y * _height)
            lParam = win32api.MAKELONG(x, y)
            win32gui.SendMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lParam)

    @pyqtSlot(float, float)
    def MouseRelease(self, x, y):
        """Send LMB up"""
        x = int(x * _width)
        y = int(y * _height)
        lParam = win32api.MAKELONG(x, y)
        win32gui.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        self.mouse_down = False

    @pyqtSlot(int)
    def MouseScrolled(self, delta_y):
        self.force_detect = True
        x = int(_width / 2)
        y = int(_height / 2)
        lParam = win32api.MAKELONG(x, y)
        wParam = win32api.MAKELONG(0, delta_y * 120)
        win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEWHEEL, wParam, lParam)

    @pyqtSlot()
    def EnterPressed(self):
        self.force_detect = True

if __name__ == "__main__":
    App = QApplication(sys.argv)
    pre_launcher = PreLauncher()
    pre_launcher.show()
    sys.exit(App.exec())