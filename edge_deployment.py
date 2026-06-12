# edge_deployment/optimized_detector.py
import cv2
import numpy as np
from threading import Thread, Lock
from queue import Queue
import time
from collections import deque
import os

class EdgeOptimizedDetector:
    """Optimized for Raspberry Pi 4 / Jetson Nano"""
    
    def __init__(self, platform="raspberry_pi"):
        self.platform = platform
        self.frame_queue = Queue(maxsize=2)
        self.result_queue = Queue(maxsize=2)
        self.processing_lock = Lock()
        self.running = True
        
        # Platform-specific configurations
        self.configs = {
            "raspberry_pi": {
                "input_size": (320, 320),  # Smaller input for RPi
                "precision": "int8",        # Quantized model
                "fps_target": 15,
                "use_neon": True,
                "threads": 2
            },
            "jetson_nano": {
                "input_size": (416, 416),
                "precision": "fp16",         # TensorRT half precision
                "fps_target": 25,
                "use_tensorrt": True,
                "threads": 4
            }
        }
        
        self.cfg = self.configs[platform]
        
        # Frame skipping for processing
        self.process_every_n_frames = 2
        self.frame_counter = 0
        
        # Performance monitoring
        self.fps_buffer = deque(maxlen=30)
        self.inference_times = deque(maxlen=30)
        
    def load_optimized_model(self):
        """Load platform-optimized model"""
        if self.platform == "raspberry_pi":
            return self._load_tflite_model()
        elif self.platform == "jetson_nano":
            return self._load_tensorrt_model()
        else:
            return self._load_standard_model()
    
    def _load_tflite_model(self):
        """Load TensorFlow Lite model for Raspberry Pi"""
        import tflite_runtime.interpreter as tflite
        
        # Use quantized model for 3-4x speedup
        model_path = "models/yolov8n_pose_int8.tflite"
        
        interpreter = tflite.Interpreter(
            model_path=model_path,
            num_threads=self.cfg["threads"]
        )
        interpreter.allocate_tensors()
        
        # Get input/output details
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # Enable XNNPACK for faster CPU inference
        interpreter.set_num_threads(self.cfg["threads"])
        
        return interpreter, input_details, output_details
    
    def _load_tensorrt_model(self):
        """Load TensorRT model for Jetson Nano"""
        import tensorrt as trt
        
        # Load optimized TensorRT engine
        engine_path = "models/yolov8n_pose_fp16.trt"
        
        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
            engine = runtime.deserialize_cuda_engine(f.read())
        
        context = engine.create_execution_context()
        
        # Allocate GPU memory
        inputs = []
        outputs = []
        bindings = []
        
        for binding in engine:
            size = trt.volume(engine.get_binding_shape(binding))
            dtype = trt.nptype(engine.get_binding_dtype(binding))
            host_mem = cv2.cuda.HostMem.alloc(size, dtype)
            device_mem = cv2.cuda.DeviceMem.alloc(size * dtype.itemsize)
            bindings.append(int(device_mem))
            
            if engine.binding_is_input(binding):
                inputs.append((host_mem, device_mem))
            else:
                outputs.append((host_mem, device_mem))
        
        return context, bindings, inputs, outputs
    
    def process_frame_optimized(self, frame):
        """Process frame with optimizations"""
        # Skip frames to maintain FPS
        self.frame_counter += 1
        if self.frame_counter % self.process_every_n_frames != 0:
            return None
        
        # Resize to model input size
        h, w = frame.shape[:2]
        resized = cv2.resize(frame, self.cfg["input_size"])
        
        # Normalize and prepare input
        input_data = resized.astype(np.float32) / 255.0
        input_data = np.expand_dims(input_data, axis=0)
        
        # Run inference with timing
        start_time = time.time()
        
        if self.platform == "raspberry_pi":
            results = self._inference_tflite(input_data)
        elif self.platform == "jetson_nano":
            results = self._inference_tensorrt(input_data)
        else:
            results = self._inference_standard(input_data)
        
        inference_time = (time.time() - start_time) * 1000
        self.inference_times.append(inference_time)
        
        return results
    
    def adaptive_frame_skip(self):
        """Dynamically adjust frame skipping based on performance"""
        avg_fps = np.mean(self.fps_buffer) if self.fps_buffer else 0
        avg_inference = np.mean(self.inference_times) if self.inference_times else 0
        
        target_inference_ms = 1000 / self.cfg["fps_target"]
        
        if avg_inference > target_inference_ms * 1.5:
            # Too slow, skip more frames
            self.process_every_n_frames = min(4, self.process_every_n_frames + 1)
        elif avg_inference < target_inference_ms * 0.7:
            # Fast enough, process more frames
            self.process_every_n_frames = max(1, self.process_every_n_frames - 1)
        
        return self.process_every_n_frames