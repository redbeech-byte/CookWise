import sys
import os
import time
import ctypes
import threading
from pathlib import Path

# Setup error logging
LOG_PATH = Path(__file__).parent.parent / "data" / "camera_error.log"
def log_err(msg):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{time.ctime()}] {msg}\n")

try:
    import objc
    import AVFoundation as AV
    import Quartz
    from Foundation import NSObject, NSRunLoop, NSDate, NSURL
except ImportError as e:
    log_err(f"Import Error: {e}. Make sure pyobjc-framework-AVFoundation and pyobjc-framework-Quartz are installed.")
    sys.exit(1)

OUTPUT_PATH  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("iphone_capture.jpg")
READY_FLAG   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cam_ready")
TRIGGER_FLAG = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".cam_trigger")

# ---------- dispatch queue ----------
try:
    _libdispatch = ctypes.CDLL("/usr/lib/system/libdispatch.dylib")
    _libdispatch.dispatch_queue_create.restype  = ctypes.c_void_p
    _libdispatch.dispatch_queue_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
except Exception as e:
    log_err(f"Libdispatch error: {e}")

def make_queue(label):
    ptr = _libdispatch.dispatch_queue_create(label.encode(), None)
    return objc.objc_object(c_void_p=ptr)

# ---------- find Camera (iPhone or Built-in) ----------
device_types = [
    AV.AVCaptureDeviceTypeBuiltInWideAngleCamera,
]
# Try to add professional/continuity types if available
for attr in ("AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera"):
    val = getattr(AV, attr, None)
    if val:
        device_types.append(val)

discovery = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
    device_types, AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified)

camera = None
devices = discovery.devices()

# Priority 1: Continuity / iPhone
for d in devices:
    dtype = (d.deviceType() or "").lower()
    name  = d.localizedName().lower()
    if "external" in dtype or "continuity" in dtype or "iphone" in name or "ipad" in name:
        camera = d
        log_err(f"Found iPhone/Continuity Camera: {name}")
        break

# Priority 2: Built-in FaceTime camera
if not camera:
    for d in devices:
        if "facetime" in d.localizedName().lower() or "built-in" in d.localizedName().lower():
            camera = d
            log_err(f"iPhone not found, falling back to: {d.localizedName()}")
            break

# Priority 3: Just take the first camera found
if not camera and devices:
    camera = devices[0]
    log_err(f"No specific camera matched, using first available: {camera.localizedName()}")

if camera is None:
    log_err("No camera devices found at all.")
    sys.exit(1)

# ---------- build session ----------
session = AV.AVCaptureSession.alloc().init()
session.setSessionPreset_(AV.AVCaptureSessionPresetPhoto)

device_input, err = AV.AVCaptureDeviceInput.deviceInputWithDevice_error_(camera, None)
if err or not session.canAddInput_(device_input):
    log_err(f"Could not create input: {err}")
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
            url = NSURL.fileURLWithPath_(str(OUTPUT_PATH.absolute()))
            ok, _ = context.writeJPEGRepresentationOfImage_toURL_colorSpace_options_error_(
                ci_image, url, cs, {}, None)
            if ok:
                saved.append(True)
                log_err(f"Successfully saved image to {OUTPUT_PATH}")
        except Exception as e:
            log_err(f"Capture callback error: {e}")
        finally:
            if saved:
                session.stopRunning()

delegate = FrameDelegate.alloc().init()
video_output.setSampleBufferDelegate_queue_(delegate, make_queue("camera.queue"))

if not session.canAddOutput_(video_output):
    log_err("Could not add output to session.")
    sys.exit(1)
session.addOutput_(video_output)

# ---------- run ----------
session.startRunning()

# Warm up 2s
warmup_end = time.time() + 2.0
while time.time() < warmup_end:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

# Signal Streamlit: camera is live
READY_FLAG.touch()

# Watch for trigger flag
def watch_trigger():
    deadline = time.time() + 60 # wait up to 60s
    while time.time() < deadline:
        if TRIGGER_FLAG.exists():
            capture_now.append(True)
            return
        time.sleep(0.1)

t = threading.Thread(target=watch_trigger, daemon=True)
t.start()

# Run until frame saved or timeout
deadline = time.time() + 65
while time.time() < deadline:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    if saved:
        break

session.stopRunning()
