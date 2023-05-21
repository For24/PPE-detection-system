# PPE-Detect
To use our system, you have to have a GPU with at least 8 GB GPU memory.

First, cd to our source folder:

cd source

Install following requirements:

pip install -r requirements.txt

Detect on image or video file or video stream from webcam:

for example, run detect on an image file:

python run.py --weights ppe_yolov5l.pt --conf 0.25 --source img.jpg --use_depth 

if you want to run on your webcam, use 0 as the source (assume the device number of your webcam is 0)
