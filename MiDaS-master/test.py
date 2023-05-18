import cv2

img = cv2.imread('E:\workshop\MiDaS-master\MiDaS-master\input\\test.jpg')
if img.ndim == 2:
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) / 255.0



import os
import glob
import torch
import utils
import argparse
import time

import numpy as np

from imutils.video import VideoStream
from midas.model_loader import default_models, load_model

model_path = 'E:\workshop\MiDaS-master\MiDaS-master\weights\dpt_hybrid_384.pt'
first_execution = True

def process(device, model, model_type, image, input_size, target_size, optimize, use_camera):
    """
    Run the inference and interpolate.

    Args:
        device (torch.device): the torch device used
        model: the model used for inference
        model_type: the type of the model
        image: the image fed into the neural network
        input_size: the size (width, height) of the neural network input (for OpenVINO)
        target_size: the size (width, height) the neural network output is interpolated to
        optimize: optimize the model to half-floats on CUDA?
        use_camera: is the camera used?

    Returns:
        the prediction
    """
    global first_execution

    if "openvino" in model_type:
        if first_execution or not use_camera:
            print(f"    Input resized to {input_size[0]}x{input_size[1]} before entering the encoder")
            first_execution = False

        sample = [np.reshape(image, (1, 3, *input_size))]
        prediction = model(sample)[model.output(0)][0]
        prediction = cv2.resize(prediction, dsize=target_size,
                                interpolation=cv2.INTER_CUBIC)
    else:
        sample = torch.from_numpy(image).to(device).unsqueeze(0)

        if optimize and device == torch.device("cuda"):
            if first_execution:
                print("  Optimization to half-floats activated. Use with caution, because models like Swin require\n"
                      "  float precision to work properly and may yield non-finite depth values to some extent for\n"
                      "  half-floats.")
            sample = sample.to(memory_format=torch.channels_last)
            sample = sample.half()

        if first_execution or not use_camera:
            height, width = sample.shape[2:]
            print(f"    Input resized to {width}x{height} before entering the encoder")
            first_execution = False

        prediction = model.forward(sample)
        prediction = (
            torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=target_size[::-1],
                mode="bicubic",
                align_corners=False,
            )
            .squeeze()
            .cpu()
            .numpy()
        )

    return prediction

def create_side_by_side(image, depth, grayscale):
    """
    Take an RGB image and depth map and place them side by side. This includes a proper normalization of the depth map
    for better visibility.

    Args:
        image: the RGB image
        depth: the depth map
        grayscale: use a grayscale colormap?

    Returns:
        the image and depth map place side by side
    """
    depth_min = depth.min()
    depth_max = depth.max()
    normalized_depth = 255 * (depth - depth_min) / (depth_max - depth_min)
    normalized_depth *= 3

    right_side = np.repeat(np.expand_dims(normalized_depth, 2), 3, axis=2) / 3
    if not grayscale:
        right_side = cv2.applyColorMap(np.uint8(right_side), cv2.COLORMAP_INFERNO)

    if image is None:
        return right_side
    else:
        return np.concatenate((image, right_side), axis=1)

def run(img, model_path, model_type="dpt_hybrid_384", optimize=False, side=False, height=None,
        square=False, grayscale=False):
    """Run MonoDepthNN to compute depth maps.

    Args:
        img (str): path to input folder
        output_path (str): path to output folder
        model_path (str): path to saved model
        model_type (str): the model type
        optimize (bool): optimize the model to half-floats on CUDA?
        side (bool): RGB and depth side by side in output images?
        height (int): inference encoder image height
        square (bool): resize to a square resolution?
        grayscale (bool): use a grayscale colormap?
    """
    print("Initialize")

    # select device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device: %s" % device)

    model, transform, net_w, net_h = load_model(device, model_path, model_type, optimize, height, square)

    # get img
    if img is None:
        print("No input path specified. Grabbing images from camera.")

    print("Start processing")

    if img is not None:
        # input
        original_image_rgb = img  # in [0, 1]
        image = transform({"image": original_image_rgb})["image"]

        # compute
        with torch.no_grad():
            prediction = process(device, model, model_type, image, (net_w, net_h), original_image_rgb.shape[1::-1],
                                     optimize, False)
            print(prediction)
            print(prediction.shape)

    else:
        with torch.no_grad():
            fps = 1
            video = VideoStream(0).start()
            time_start = time.time()
            frame_index = 0
            while True:
                frame = video.read()
                if frame is not None:
                    original_image_rgb = np.flip(frame, 2)  # in [0, 255] (flip required to get RGB)
                    image = transform({"image": original_image_rgb/255})["image"]

                    prediction = process(device, model, model_type, image, (net_w, net_h),
                                         original_image_rgb.shape[1::-1], optimize, True)

                    original_image_bgr = np.flip(original_image_rgb, 2) if side else None
                    content = create_side_by_side(original_image_bgr, prediction, grayscale)
                    cv2.imshow('MiDaS Depth Estimation - Press Escape to close window ', content/255)

                    alpha = 0.1
                    if time.time()-time_start > 0:
                        fps = (1 - alpha) * fps + alpha * 1 / (time.time()-time_start)  # exponential moving average
                        time_start = time.time()
                    print(f"\rFPS: {round(fps,2)}", end="")

                    if cv2.waitKey(1) == 27:  # Escape key
                        break

                    frame_index += 1
        print()

    print("Finished")


run(img, model_path, "dpt_hybrid_384", False, False, None, False, False)