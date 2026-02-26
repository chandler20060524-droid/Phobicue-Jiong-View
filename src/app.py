import sys
import dxcam
import cv2
import time

window_name = "Phobicube"

def main():
    # GPU level capture (wtf i thought there would be a security issue)
    camera = dxcam.create(output_idx=0, output_color="BGR")
    time.sleep(0.1) 

    camera.start()

    '''
    # Make window layered + click-through
    hwnd = win32gui.FindWindow(None, window_name)

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(
        hwnd,
        win32con.GWL_EXSTYLE,
        style
        | win32con.WS_EX_LAYERED
        | win32con.WS_EX_TRANSPARENT
        | win32con.WS_EX_TOPMOST
    )
    '''
    while True:
        frame = camera.get_latest_frame()

        if frame is not None:
            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == 27:
                break

    camera.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()