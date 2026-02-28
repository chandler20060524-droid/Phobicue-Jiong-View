import cv2
import numpy as np
import win32gui, win32ui, win32con, win32api
from pynput import mouse, keyboard
from ctypes import windll
import threading 
from ultralytics import YOLO

# Load image classification model
model = YOLO("yolov8n.pt")

ANIMAL_CLASSES = {
    15,  # cat
    16,  # dog
    17,  # horse
    18,  # sheep
    19,  # cow
    20,  # elephant
    21,  # bear
    22,  # zebra
    23,  # giraffe
    14,  # bird
}

# Mouse and keyboard events tracking. 
class InputState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mouse_pos = (0, 0)
        self.left_mouse_pressed = False
        self.right_mouse_pressed = False
        self.mouse_scrolled = False
        self.running = True

state = InputState()

def on_move(x, y):
    with state.lock:
        state.mouse_pos = (x, y)

def on_click(x, y, button, pressed):
    with state.lock:
        if button == mouse.Button.left:
            state.left_mouse_pressed = pressed
        if button == mouse.Button.right:
            state.right_mouse_pressed = pressed

def on_key(key):
    if key == keyboard.Key.esc:
        state.running = False
        return False
    
def on_scroll(x, y, dx, dy):
    with state.lock:
        state.mouse_scrolled = dy
    
mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()
keyboard.Listener(on_press=on_key).start()

# Window title to capture
window_title = "Google Chrome"

# Create cv2 window
cv2.namedWindow("Phobicue", cv2.WINDOW_NORMAL)

# Get window information
windll.user32.SetProcessDPIAware()
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

def main():
    frame_count = 0
    safety_counter = 30
    previous_detections = []
    while state.running:
        try:   
            saveDC.SelectObject(saveBitMap)
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
            if result != 1:
                continue

            bmpstr = saveBitMap.GetBitmapBits(True)

            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img = img.reshape((height, width, 4))
            cv_frame = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

            # reuse detection every 3 frames
            if frame_count % 3 == 0:
                detections = DetectAnimal(cv_frame, 0.2)

            # previous detection last at least 30 frames to ensure 
            # no flickerings
            if len(detections) != 0:
                previous_detections = detections.copy()
                safety_counter = 30

            for x1, y1, x2, y2, conf in detections:
                RegionBlur(cv_frame, (x1, y1, x2, y2))

            if safety_counter > 0 and previous_detections:
                for x1, y1, x2, y2, conf in previous_detections:
                    RegionBlur(cv_frame, (x1, y1, x2, y2))

                safety_counter -= 1

            win_x, win_y, win_width, win_height = cv2.getWindowImageRect("Phobicue")

            with state.lock:
                abs_x, abs_y = state.mouse_pos
                left_pressed = state.left_mouse_pressed
                right_pressed = state.right_mouse_pressed
                # scrolled = state.mouse_scrolled

            x = int((abs_x - win_x) / win_width * width)
            y = int((abs_y - win_y) / win_height * height)

            x -= 7
            y -= 200

            if left_pressed:
                click(x, y, 0)
                win32gui.SetForegroundWindow(hwnd)
            if right_pressed:
                click(x, y, 1)

            # if scrolled:
                # scroll(x, y, scrolled * 120)

            cv2.imshow("Phobicue", cv_frame)

            frame_count += 1

            if cv2.waitKey(25) & 0xFF == 27:
                break

        except Exception as e:
            print("Error: ", e)
            break
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc)
    cv2.destroyAllWindows()

def click(x, y, input):
    try:
        lParam = win32api.MAKELONG(x, y)

        hWnd1 = win32gui.FindWindowEx(hwnd, None, None, None)

        match input:
            case 0:
                win32gui.SendMessage(hWnd1, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
                win32gui.SendMessage(hWnd1, win32con.WM_LBUTTONUP, None, lParam)
            case 1:
                win32gui.SendMessage(hWnd1, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lParam)
                win32gui.SendMessage(hWnd1, win32con.WM_RBUTTONUP, None, lParam)

    except Exception as e:
        print(f"Click failed: {e}")

def enum_child_windows(hwnd):
    '''
    Enumerate through window handles to find a child window that acceots
    mouse wheel scroll messsage (currently not implemented).
    '''
    children = []
    def callback(child, param):
        children.append(child)
        return True
    win32gui.EnumChildWindows(hwnd, callback, None)
    return children

def scroll(x, y, delta):
    try:
        children = enum_child_windows(hwnd)
        target_hwnd = children[-1]

        lParam = win32api.MAKELONG(x, y)
        wParam = win32api.MAKELONG(0, delta)

        win32gui.PostMessage(target_hwnd, win32con.WM_MOUSEWHEEL, wParam, lParam)

    except Exception as e:
        print(f"Scroll failed: {e}")

def DetectAnimal(frame, conf_threshold = 0.4):
    '''
    Returns a list of bounding boxex on successfully detected animals.
    '''
    # resized = cv2.resize(frame, (640, 640)) 
    # faster detection since YOLO is trained on 640 x 640 images
    results = model(frame, verbose=False)
    detections = []

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            if cls in ANIMAL_CLASSES and conf >= conf_threshold:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # rescale detected position based on frame size
                # x1 = int(x1 / 640 * width)
                # y1 = int(y1 / 640 * height)
                # x2 = int(x2 / 640 * width)
                # y2 = int(y2 / 640 * height)
                detections.append((x1, y1, x2, y2, conf))
    
    return detections

def RegionBlur(frame, box):
    '''
    Blurs region based on successful detections.
    '''
    x1, x2, y1, y2 = box
    roi = frame[y1:y2, x1:x2]

    if roi.size == 0:
        return 
    
    blurred = cv2.GaussianBlur(roi, (51, 51), 0)
    frame[y1:y2, x1:x2] = blurred


if __name__ == "__main__":
    main()