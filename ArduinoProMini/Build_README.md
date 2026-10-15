Build version and automated upload
=================================

This sketch embeds a 16-bit BUILD_VERSION value in the firmware. The value is defined in build_version.h as a 16-bit hex macro:

    #define BUILD_VERSION 0x0000

The firmware exposes this value as a constant named BUILD_VERSION_VAR (see ArduinoProMini.ino). BUILD_VERSION_VAR is a uint16_t and is embedded in flash so firmware can show or report it at runtime.

Automated bumping and upload script
----------------------------------

Use the PowerShell helper upload_with_increment.ps1 to increment the BUILD_VERSION and then compile and upload the sketch.

Usage (from the ArduinoProMini folder):

    .\upload_with_increment.ps1 -Port COM4

What the script does
- Reads build_version.h and parses the BUILD_VERSION macro.
- Increments the value by 1 for each run. If the value is 0xFFFF, the script resets it to 0x0000 on the next run (rollover behavior for 16-bit values).
- Writes the new value back into build_version.h.
- Runs arduino-cli compile and then arduino-cli upload to the target port (default COM4).
- Does NOT automatically commit the header change to git.

Notes and recommendations
- The script increments the build version before compiling so the compiled hex contains the new build number.
- If you prefer the bump to occur only after a successful upload, modify the script accordingly (it can be changed to increment after upload).
- To distribute a prebuilt .hex, copy the desired hex out of build/ (for example build/ArduinoProMini.ino.hex) into a release artifact.

Version display (runtime)
-------------------------

A runtime feature displays the embedded BUILD_VERSION_VAR on the 4-digit LED display when the user presses START and RESET together.

Behavior details:
- Trigger: press and hold START + RESET simultaneously.
- Latch: the display is guaranteed to remain visible for at least 10 seconds even if the buttons are released briefly. If the buttons remain held longer, the display will continue until they are released and the minimum 10s has elapsed.
- Format: BUILD_VERSION_VAR is shown as a 4-digit uppercase hexadecimal value (nibbles across the four physical digits, left-to-right: MS nibble -> LSN).
- Dots: the two middle dots are turned OFF while the version is displayed.

Color and brightness effect:
- The version display cycles through the following colors in order:
  AliceBlue, Azure, Brown, Cyan, Gold, Honeydew, LawnGreen, Orange, Navy, Pink, Tomato, Violet
- Each color is shown for 1000 ms.
- For each color interval the brightness follows a triangle envelope: it ramps from 1/3 of runBrightness up to runBrightness, then back to 1/3 of runBrightness over the 750 ms.
- The envelope produces a smooth pulsing per color; after the cycle the next color begins.

Implementation notes
--------------------
- The display update loop polls buttons frequently and redraws the version display, so the UI remains responsive.
- The version display does not change timer state (running, currentSeconds) or relay output; it only overrides the visual output while active.
- The color/brightness list and timings are defined in ArduinoProMini.ino; you can tweak the constants there if you want different colors, per-color duration, or the latch time.

Reference in code
-----------------
- build_version.h: defines BUILD_VERSION macro (16-bit).
- upload_with_increment.ps1: increments BUILD_VERSION and compiles/uploads the sketch.
- ArduinoProMini.ino: includes build_version.h, defines BUILD_VERSION_VAR, and implements the version display with color/brightness envelope.

Example: printing the version to Serial
--------------------------------------

If you prefer to print the embedded version to Serial in addition to the LED display, add this to setup():

    Serial.begin(115200);
    Serial.print("Build version: 0x");
    if (BUILD_VERSION_VAR <= 0x000F) Serial.print("000");
    else if (BUILD_VERSION_VAR <= 0x00FF) Serial.print("00");
    else if (BUILD_VERSION_VAR <= 0x0FFF) Serial.print("0");
    Serial.println(BUILD_VERSION_VAR, HEX);

