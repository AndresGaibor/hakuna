from __future__ import annotations

import sys
import time

# PyObjC helper for running text view updates on the main thread safely
_helper = None

if sys.platform == "darwin":
    from Foundation import NSObject

    class HUDLoggerHelper(NSObject):
        def appendText_(self, info):
            try:
                tv, line = info
                ts = tv.textStorage()
                ts.mutableString().appendString_(line)
                max_lineas = 50
                parrafos = ts.string().count("\n")
                if parrafos > max_lineas:
                    rango = (0, len(ts.string().split("\n", 1)[0]) + 1)
                    ts.deleteCharactersInRange_(rango)
                tv.scrollRangeToVisible_((len(ts.string()), 0))
            except Exception as e:
                sys.stderr.write(f"HUD log error: {e}\n")
                sys.stderr.flush()

    _helper = HUDLoggerHelper.alloc().init()


class _HUD:
    def __init__(self):
        self.ventana = None
        self.texto = None

    def iniciar(self):
        if sys.platform == "darwin":
            self._iniciar_macos()

    def _iniciar_macos(self):
        from Cocoa import (
            NSBackingStoreBuffered,
            NSColor,
            NSMakeRect,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSPanel,
            NSScrollView,
            NSTextView,
            NSWindowSharingNone,
        )
        from Quartz import CGWindowLevelForKey, kCGScreenSaverWindowLevelKey

        rect = NSMakeRect(0, 0, 420, 250)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, 1 << 5, NSBackingStoreBuffered, False
        )
        panel.setTitle_("HAKU Debug")
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, 0.75))
        panel.setHasShadow_(True)
        panel.setSharingType_(NSWindowSharingNone)
        panel.setLevel_(CGWindowLevelForKey(kCGScreenSaverWindowLevelKey))
        panel.setIgnoresMouseEvents_(True)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        from Cocoa import NSScreen
        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - 430
        y = screen.origin.y + screen.size.height - 260
        panel.setFrameOrigin_((x, y))

        scroll = NSScrollView.alloc().initWithFrame_(panel.contentView().bounds())
        scroll.setAutoresizingMask_(15)
        scroll.setHasVerticalScroller_(True)

        tv = NSTextView.alloc().initWithFrame_(((0, 0), (400, 230)))
        tv.setEditable_(False)
        tv.setSelectable_(False)
        tv.setDrawsBackground_(False)
        tv.setTextColor_(NSColor.greenColor())
        tv.setFont_(
            getattr(__import__("AppKit", fromlist=["NSFont"]), "NSFont")
            .userFixedPitchFontOfSize_(11)
        )
        scroll.setDocumentView_(tv)
        panel.setContentView_(scroll)
        panel.orderFrontRegardless()

        self.ventana = panel
        self.texto = tv

    def log(self, msg: str):
        t = time.strftime("%H:%M:%S")
        linea = f"[{t}] {msg}\n"
        # Always output to terminal immediately
        print(linea, end="", flush=True)
        
        # If running on macOS with HUD view, delegate the UI update to the main thread
        if self.texto and _helper:
            _helper.performSelectorOnMainThread_withObject_waitUntilDone_(
                "appendText:", (self.texto, linea), False
            )


_hud = _HUD()


def iniciar_hud():
    _hud.iniciar()


def log_hud(msg: str):
    _hud.log(msg)
