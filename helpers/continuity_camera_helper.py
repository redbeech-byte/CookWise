"""
Continuity Camera helper — spawned as subprocess by Streamlit.
Communicates via flag files instead of stdin/stdout so Streamlit reruns don't kill it.

Args:
    sys.argv[1]  OUTPUT_PATH   where to save the captured JPEG
    sys.argv[2]  READY_FLAG    this file is touched when camera is live
    sys.argv[3]  TRIGGER_FLAG  helper watches for this file; captures when it appears

Requirements:
    pip install pyobjc-framework-AVFoundation pyobjc-framework-Quartz
"""

import sys
import objc
import time
import ctypes
import threading
from pathlib import Path

import AVFoundation as AV
import Quartz
from Foundation import NSObject, NSRunLoop, NSDate

OUTPUT_PATH  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("iphone_capture.jpg")
READY_FLAG   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cam_ready")
TRIGGER_FLAG = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".cam_trigger")

# ---------- dispatch queue ----------
_libdispatch = ctypes.CDLL("/usr/lib/system/libdispatch.dylib")
_libdispatch.dispatch_queue_create.restype  = ctypes.c_void_p
_libdispatch.dispatch_queue_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]

def make_queue(label):
    ptr = _libdispatch.dispatch_queue_create(label.encode(), None)
    return objc.objc_object(c_void_p=ptr)

# ---------- find iPhone ----------
device_types = [AV.AVCaptureDeviceTypeBuiltInWideAngleCamera]
for attr in ("AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera"):
    val = getattr(AV, attr, None)
    if val:
        device_types.append(val)

discovery = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
    device_types, AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified)

iphone = None
for d in discovery.devices():
    dtype = (d.deviceType() or "").lower()
    name  = d.localizedName().lower()
    if "external" in dtype or "continuity" in dtype or "iphone" in name or "ipad" in name:
        iphone = d
        break

if iphone is None:
    sys.exit(1)

# ---------- build session ----------
session = AV.AVCaptureSession.alloc().init()
session.setSessionPreset_(AV.AVCaptureSessionPresetPhoto)

device_input, err = AV.AVCaptureDeviceInput.deviceInputWithDevice_error_(iphone, None)
if err or not session.canAddInput_(device_input):
    sys.exit(1)
session.addInput_(device_input)

video_output = AV.AVCaptureVideoDataOutput.alloc().init()
video_output.setAlwaysDiscardsLateVideoFrames_(True)

saved        = []
capture_now  = []

class FrameDelegate(NSObject, protocols=[objc.protocolNamed("AVCaptureVideoDataOutputSampleBufferDelegate")]):
    @objc.typedSelector(b"v@:@^{opaqueCMSampleBuffer=}@")
    def captureOutput_didOutputSampleBuffer_fromConnection_(self, output, sample_buffer, connection):
        if saved or not capture_now:
            return
        try:
            pixel_buffer = AV.CMSampleBufferGetImageBuffer(sample_buffer)
            if pixel_buffer is None:
                return
            ci_image = Quartz.CIImage.imageWithCVImageBuffer_(pixel_buffer)
            context  = Quartz.CIContext.context()
            cs       = Quartz.CGColorSpaceCreateDeviceRGB()
            from Foundation import NSURL
            url = NSURL.fileURLWithPath_(str(OUTPUT_PATH))
            ok, _ = context.writeJPEGRepresentationOfImage_toURL_colorSpace_options_error_(
                ci_image, url, cs, {}, None)
            if ok:
                saved.append(True)
        except Exception:
            pass
        finally:
            if saved:
                session.stopRunning()

delegate = FrameDelegate.alloc().init()
video_output.setSampleBufferDelegate_queue_(delegate, make_queue("camera.queue"))

if not session.canAddOutput_(video_output):
    sys.exit(1)
session.addOutput_(video_output)

# ---------- run ----------
session.startRunning()

# Warm up 2s for focus/exposure
warmup_end = time.time() + 2.0
while time.time() < warmup_end:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

# Signal Streamlit: camera is live
READY_FLAG.touch()

# Watch for trigger flag in background thread
def watch_trigger():
    deadline = time.time() + 30
    while time.time() < deadline:
        if TRIGGER_FLAG.exists():
            capture_now.append(True)
            return
        time.sleep(0.1)

t = threading.Thread(target=watch_trigger, daemon=True)
t.start()

# Run until frame saved or timeout
deadline = time.time() + 35
while time.time() < deadline:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    if saved:
        break

session.stopRunning()
