import sys
import os
import time
import ctypes
import threading
from pathlib import Path

# Writing camera errors to a local log file makes debugging easier because this
# helper usually runs as a separate process from the Streamlit page.
LOG_PATH = Path(__file__).parent.parent / "data" / "camera_error.log"
def log_err(msg):
    # Timestamping each line helps connect camera failures to the moment the user
    # tried to scan ingredients.
    with open(LOG_PATH, "a") as f:
        f.write(f"[{time.ctime()}] {msg}\n")

try:
    import objc
    import AVFoundation as AV
    import Quartz
    from Foundation import NSObject, NSRunLoop, NSDate, NSURL
except ImportError as e:
    # These imports are macOS-specific. If they are missing, the camera helper
    # cannot access AVFoundation or save frames from the camera stream.
    log_err(f"Import Error: {e}. Make sure pyobjc-framework-AVFoundation and pyobjc-framework-Quartz are installed.")
    sys.exit(1)

# The Streamlit app passes these paths when starting the helper.
# Flags are used for simple communication between the UI process and this camera process.
OUTPUT_PATH  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("iphone_capture.jpg")
READY_FLAG   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cam_ready")
TRIGGER_FLAG = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".cam_trigger")

# ---------- dispatch queue ----------
# AVFoundation delivers camera frames on a dispatch queue, so this creates one
# from macOS libdispatch and exposes it to PyObjC.
try:
    _libdispatch = ctypes.CDLL("/usr/lib/system/libdispatch.dylib")
    _libdispatch.dispatch_queue_create.restype  = ctypes.c_void_p
    _libdispatch.dispatch_queue_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
except Exception as e:
    log_err(f"Libdispatch error: {e}")

def make_queue(label):
    # Converting the raw dispatch queue pointer into a PyObjC object lets it be
    # passed into setSampleBufferDelegate_queue_.
    ptr = _libdispatch.dispatch_queue_create(label.encode(), None)
    return objc.objc_object(c_void_p=ptr)

# ---------- find Camera (iPhone or Built-in) ----------
# Starting with the built-in wide angle camera type keeps basic Mac camera support.
device_types = [
    AV.AVCaptureDeviceTypeBuiltInWideAngleCamera,
]
# Adding Continuity Camera types only if this macOS/PyObjC version exposes them.
for attr in ("AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera"):
    val = getattr(AV, attr, None)
    if val:
        device_types.append(val)

discovery = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
    device_types, AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified)

camera = None
devices = discovery.devices()

# Priority 1: using Continuity Camera or an iPhone/iPad when available, because
# this gives better ingredient photos than many built-in laptop cameras.
for d in devices:
    dtype = (d.deviceType() or "").lower()
    name  = d.localizedName().lower()
    if "external" in dtype or "continuity" in dtype or "iphone" in name or "ipad" in name:
        camera = d
        log_err(f"Found iPhone/Continuity Camera: {name}")
        break

# Priority 2: falling back to the built-in FaceTime camera if no iPhone camera is found.
if not camera:
    for d in devices:
        if "facetime" in d.localizedName().lower() or "built-in" in d.localizedName().lower():
            camera = d
            log_err(f"iPhone not found, falling back to: {d.localizedName()}")
            break

# Priority 3: using the first available camera as a last resort keeps the scan
# feature usable even when device names do not match the expected patterns.
if not camera and devices:
    camera = devices[0]
    log_err(f"No specific camera matched, using first available: {camera.localizedName()}")

if camera is None:
    # Exiting early avoids building an AVFoundation session without a valid device.
    log_err("No camera devices found at all.")
    sys.exit(1)

# ---------- build session ----------
# The capture session connects the selected camera input to a video output that
# provides frames for saving.
session = AV.AVCaptureSession.alloc().init()
session.setSessionPreset_(AV.AVCaptureSessionPresetPhoto)

device_input, err = AV.AVCaptureDeviceInput.deviceInputWithDevice_error_(camera, None)
if err or not session.canAddInput_(device_input):
    log_err(f"Could not create input: {err}")
    sys.exit(1)
session.addInput_(device_input)

video_output = AV.AVCaptureVideoDataOutput.alloc().init()
# Dropping late frames keeps the helper focused on the newest camera frame instead
# of building up a backlog while waiting for the trigger.
video_output.setAlwaysDiscardsLateVideoFrames_(True)

# Lists are used as small mutable flags because the callback and watcher need to
# update shared state from nested/threaded code.
saved        = []
capture_now  = []

class FrameDelegate(NSObject, protocols=[objc.protocolNamed("AVCaptureVideoDataOutputSampleBufferDelegate")]):
    # AVFoundation calls this delegate method whenever a new video frame arrives.
    @objc.typedSelector(b"v@:@^{opaqueCMSampleBuffer=}@")
    def captureOutput_didOutputSampleBuffer_fromConnection_(self, output, sample_buffer, connection):
        # Ignoring frames until Streamlit creates the trigger flag prevents saving
        # an image before the user actually presses the capture button.
        if saved or not capture_now:
            return
        try:
            pixel_buffer = AV.CMSampleBufferGetImageBuffer(sample_buffer)
            if pixel_buffer is None:
                return
            # Converting the camera frame into a CIImage lets Quartz write it as a JPEG file.
            ci_image = Quartz.CIImage.imageWithCVImageBuffer_(pixel_buffer)
            context  = Quartz.CIContext.context()
            cs       = Quartz.CGColorSpaceCreateDeviceRGB()
            url = NSURL.fileURLWithPath_(str(OUTPUT_PATH.absolute()))
            ok, _ = context.writeJPEGRepresentationOfImage_toURL_colorSpace_options_error_(
                ci_image, url, cs, {}, None)
            if ok:
                # Marking the image as saved stops the run loop below and prevents
                # additional frames from overwriting the capture.
                saved.append(True)
                log_err(f"Successfully saved image to {OUTPUT_PATH}")
        except Exception as e:
            log_err(f"Capture callback error: {e}")
        finally:
            if saved:
                # Stopping the session as soon as the capture succeeds releases the camera.
                session.stopRunning()

delegate = FrameDelegate.alloc().init()
# Connecting the delegate to the output tells AVFoundation where to send frames.
video_output.setSampleBufferDelegate_queue_(delegate, make_queue("camera.queue"))

if not session.canAddOutput_(video_output):
    log_err("Could not add output to session.")
    sys.exit(1)
session.addOutput_(video_output)

# ---------- run ----------
session.startRunning()

# Warming up briefly gives Continuity Camera time to start delivering stable frames.
warmup_end = time.time() + 2.0
while time.time() < warmup_end:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

# Signaling Streamlit that the camera is live and ready for the user to capture.
READY_FLAG.touch()

# Watching for the trigger flag lets the Streamlit page decide exactly when to save a frame.
def watch_trigger():
    deadline = time.time() + 60 # wait up to 60s
    while time.time() < deadline:
        if TRIGGER_FLAG.exists():
            # Setting this flag tells the next camera callback to save one frame.
            capture_now.append(True)
            return
        time.sleep(0.1)

t = threading.Thread(target=watch_trigger, daemon=True)
t.start()

# Running the main loop keeps AVFoundation callbacks alive until a frame is saved
# or the helper times out.
deadline = time.time() + 65
while time.time() < deadline:
    NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    if saved:
        break

# Stopping the session at the end makes sure the camera is released even after timeout.
session.stopRunning()
