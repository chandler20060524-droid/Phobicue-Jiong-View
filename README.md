# Phobicue-Jiong-View Visual Censor

A Windows desktop application that detects objects using object detection model
in video and automatically obscures them in real time on another window.

### Description
## Features

- Real-time object detection
- Automatic visual censorship
- Customizable detection strictness, detection frequency and censoring methods
- Image and video processing
- Desktop GUI
- GPU acceleration if available

## How It Works

The application captures the bitmap image on the original screen, converts into numpy array, processes it
by detecting desired objects using a YOLO object detection model and censoring the desired regions, 
before transferring it onto an interactive PyQt6 window for viewing & interactions. 

## Technologies

- Python
- PyQt6
- OpenCV
- Ultralytics YOLO
- NumPy
- Windows APIs

### Setup
## Requirements

 - Windows 10/11
 - Python 3.x
 - Conda or pip

## Recommendation

 - A compatible GPU is recommended for real-time performance, but the application can also run on CPU.

## Installation

Clone the repository and install the required Python packages:

git clone [<repository-url>](https://github.com/chandler20060524-droid/Phobicue-Jiong-View.git)
cd Phobicue-Jiong-View
pip install -r requirements.txt

### Pre-Launching

On running the Phobicue.py, the application will first launch a pre-launcher window which asks for the desired window name and the YOLO model file name. 

## Window Name

    For example, to use it on Google Chrome: 
     - Open Google Chrome and name it "Chrome".
     - Switch to window mode from full screen if applicable (do not minimize).
     - Adjust the window to a desirable size.
     - Drag the window down until the content area that potentially contains items you want to censor
       submerges under your screen (so you don't see it).
     - Enter "Chrome" in the first text field.

## YOLO Model

    The application detects objects based on the model used. For example, entering "yolo26m.pt" in the 
    second text field will make the application use the default Ultralytics yolo26m.pt model for detection.

    For customized object censoring, it is recommended to download or train the desired type of model, and
    then place the ".pt" file in the root directory before running the application. Then enter the name 
    of the model file. 

    On the first launch, the default YOLO model will be downloaded automatically by the Ultralytics package given that the model exists and is not already present locally. 

After entering the required text field, click continue. If no error presents, the pre-launcher will hide 
it self and launch the main application window. 

### Main Application

The main window is a one-to-one replication of the window you want to censor, while your actual, original 
window stays below your viewable screen. The menu bar allows you to customize censoring features.

## Interaction

The main window can be interacted with the cursor, which allows you to perform click and drag actions.
When clicking on the text field of the original window, you can type on your keyboard to enter texts.

## Mask Options

The mask option tab allows you to decide what goes on the censored area. 
 - "Disable" will disable the censorship.
 - "Black" will cover the detected region with black rectangles.
 - "Blur" will apply a blurring effect on the detected region.
 - "Custom Image" will check the "custom_image" folder, and cover the detected region with random images
   from the folder if the image file is applicable.

Note: custom images may be shown with wrong colors due to color channel order mismatches. 

## Detection Strictness:

The detection strictness tab allows you to decide how strict should the censorships should be.
- "Loose": the app will report a lot of detections, which may include incorrectly detected objects.
- "Normal": the recommended option. The app will report a normal amount of detections.
- "Strict": the app will report fewer detections with greater accuracy.
- "Very Strict": the app will report detections only if it is very confident, which may result in 
  ineffective censorships. 

## Detection Frequency:

The detection frequency tab allows you to decide how many frames should be between each two detections. 

The recommended option is "Every Frame", which guarantees that every frame will be examined by the model. 
However, too frequent detection may impose performance issues. Therefore, you can choose that the application
detects less frequently, though it may also results in ineffective censorships.

Note: with force detection mechanism, the application will be forced to do a detection on a frame whenever
your mouse interacts with the window, regardless your choice of frequency. 

## Exiting the Application

You can exit the application by clicking "Quit" option in the "Phobicue" menu tab; or alternatively, click
the x button on the window. 

### GPU Acceleration

GPU acceleration is optional. The application can run using either CPU or CUDA-enabled GPU inference.

For NVIDIA GPU users, install a CUDA-enabled version of PyTorch rather than the CPU-only version. Use the official PyTorch installation selector to choose the appropriate CUDA build for your system.

After installation, you can verify CUDA availability with:

<import torch>

<print(torch.cuda.is_available())>

If this returns True, the application can use the NVIDIA GPU for inference.

### Error Handling

The application handles error by showing error message in a PyQt QMessageBox before exiting safely. 

### Warnings

The application will show warnings after certain user actions. They are not errors. 

### Additonal Note

It is recommended to adjust the target window to a desired size before launching the main application, as
changing original window size when the application is running is prone to cause an error. 