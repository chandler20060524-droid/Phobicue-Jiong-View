import sys
import time
from ultralytics import YOLO
import cv2
import numpy as np
import win32gui, win32ui, win32con, win32api
from pynput import mouse, keyboard
from ctypes import windll
import threading 
from ultralytics import YOLO
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout, QMainWindow, QLabel
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QThread, pyqtSignal, Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Test")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.VBL = QVBoxLayout(central_widget)

        self.FeedLabel = QLabel()
        self.FeedLabel.setScaledContents(True)
        self.VBL.addWidget(self.FeedLabel)

        self.Worker1 = Worker1()
        self.Worker1.ImageUpdate.connect(self.ImageUpdateSlot)
        self.Worker1.start()
    
        menu_bar = self.menuBar()
        win = menu_bar.addMenu("&Window")
        quit = win.addAction("Quit")
        
        quit.triggered.connect(self.close)

    def closeEvent(self, event):
        self.Worker1.stop()
        event.accept()

    def ImageUpdateSlot(self, Image):
        self.FeedLabel.setPixmap(QPixmap.fromImage(Image))

class Worker1(QThread):
    ImageUpdate = pyqtSignal(QImage)
    def run(self):
        self.ThreadActive = True

        # Window title to capture
        window_title = "Chrome"

        # Get window information
        hwnd = win32gui.FindWindow(None, window_title)

        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top

        # Get window handle from target window
        hdc = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hdc)
        saveDC = mfcDC.CreateCompatibleDC()

        # Get bitmap as image input buffer
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)

        while self.ThreadActive:
            time.sleep(0.01)
            saveDC.SelectObject(saveBitMap)
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)

            if result != 1:
                continue
            '''
            saveDC.BitBlt(
            (0, 0),
            (width, height),
            mfcDC,
            (0, 0),
            win32con.SRCCOPY
            )
            '''
            bmpstr = saveBitMap.GetBitmapBits(True)

            cv_frame = np.frombuffer(bmpstr, dtype=np.uint8)
            cv_frame = cv_frame.reshape(height, width, 4)
            cv_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGRA2RGB)

            Convert2QtFormat = QImage(
                cv_frame.data,
                width,
                height,
                3 * width, # bytes per line
                QImage.Format.Format_RGB888
            ).copy() # prevent memory corruption

            qt_frame = Convert2QtFormat.scaled(
                1280, 800, Qt.AspectRatioMode.KeepAspectRatio
            )
            self.ImageUpdate.emit(qt_frame)

        # clean up
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)

    def stop(self):
        self.ThreadActive = False
        self.wait()
        self.quit()

if __name__ == "__main__":
    App = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(App.exec()) # exit as i click the "x" button 