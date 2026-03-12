import sys
import time
import cv2
import torch
import numpy as np
import win32gui, win32ui, win32con, win32api
from ctypes import windll
from ultralytics import YOLO
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout, QMainWindow
from PyQt6.QtGui import QImage
from PyQt6.QtCore import pyqtSlot, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent, QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

_width = 0
_height = 0

model = YOLO("yolo26m.pt") 

if torch.cuda.is_available():
    device = torch.device("cuda")
else:   
    device = torch.device("cpu")

model.to(device)
cv2.setNumThreads(0)

def DetectAnimal(frame, conf_threshold = 0.25):
    '''
    Returns a list of bounding boxex on successfully detected animals.
    '''
    source = cv2.resize(frame, (1280, 1280))
    with torch.no_grad():
        results = model.predict(source=source, show=False, save=False, verbose=False)
    detections = []

    for result in results:
        if result.boxes is None:
            continue
        box_list = result.boxes.xyxy.tolist()
        cls_list = result.boxes.cls.int().tolist()
        conf_list = result.boxes.conf.tolist()

        for box, cls, conf in zip(box_list, cls_list, conf_list):
            if cls in ANIMAL_CLASSES and conf >= conf_threshold:
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

def RegionBlur(frame, box):
    '''
    Blurs region based on successful detections.
    '''
    x1, y1, x2, y2 = box
    roi = frame[y1:y2, x1:x2]

    if roi.size == 0:
        return 
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0,0,0), -1)

ANIMAL_CLASSES = {
    14,  # bird
    15,  # cat
    16,  # dog
    17,  # horse
    18,  # sheep
    19,  # cow
    20,  # elephant
    21,  # bear
    22,  # zebra
    23,  # giraffe
}

class Detections:
    def __init__(self, box, counter):
        self.box = box
        self.counter = counter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Phobicue")
        self.move(0, 0)

        self.setMouseTracking(True)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.VBL = QVBoxLayout(central_widget)

        self.video = GLVideoWidget()
        self.VBL.addWidget(self.video)
        
        self.Worker = VideoWorker()

        self.video.mousePressed.connect(self.Worker.MousePress)
        self.video.mouseMoved.connect(self.Worker.MouseMove)
        self.video.mouseReleased.connect(self.Worker.MouseRelease)
        self.video.KeyPressed.connect(self.Worker.MouseScrolled)
        self.video.EnterPressed.connect(self.Worker.EnterPressed)

        self.Worker.ImageUpdate.connect(self.video.UpdateFrame)
        self.Worker.start()
    
        menu_bar = self.menuBar()
        win = menu_bar.addMenu("&Phobicue")
        quit = win.addAction("Quit")
        quit.triggered.connect(self.close)

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
        self.mousePressed.emit(mouse_x / self.width, mouse_y / self.height)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        mouse_x = pos.x()
        mouse_y = pos.y()
        self.mouseMoved.emit(mouse_x / self.width, mouse_y / self.height)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        pos = event.pos()
        mouse_x = pos.x()
        mouse_y = pos.y()
        self.mouseReleased.emit(mouse_x / self.width, mouse_y / self.height)
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

    def __init__(self):
        global _width, _height
        super().__init__()
        self.ThreadActive = True
        self.mouse_down = False
        self.force_detect = False

        # Window title to capture
        self.window_title = "Chrome"

        # Get window information
        self.hwnd = win32gui.FindWindow(None, self.window_title)
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
        frame_count = 0
        detections = []
        while self.ThreadActive:
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

            # reuse detection every 3 frames
            if self.force_detect or frame_count % 1 == 0:
                detections.extend(DetectAnimal(array))
                self.force_detect = False

            for detect in detections:
                RegionBlur(array, detect.box)
                detect.counter -= 1

                if detect.counter == 0:
                    detections.remove(detect)

            self.ImageUpdate.emit(array)

            frame_count += 1

        # clean up
        win32gui.DeleteObject(self.saveBitMap.GetHandle())
        self.saveDC.DeleteDC()
        self.mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, self.hdc)

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
    win = MainWindow()
    win.resize(1240, 768)
    win.show()
    sys.exit(App.exec()) # exit as i click the "x" button 
