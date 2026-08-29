# 2023-Oct-14:  Tested with CircuitPython 8.2.x
# -------------------------------------------------
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import neopixel
import busio
import digitalio
import adafruit_ssd1306

# All button Pull down from 3.3V
opt0 = digitalio.DigitalInOut(board.GP22)     # Pin 29
opt1 = digitalio.DigitalInOut(board.GP21)     # Pin 27
# Hardware error: when connect either GP20 or GP21, both turn ON.
# So swift one pin over tp GP21 & GP22
opt2 = digitalio.DigitalInOut(board.GP19)     # Pin 25
opt3 = digitalio.DigitalInOut(board.GP18)     # Pin 24

opt0.switch_to_input(pull=digitalio.Pull.DOWN)
opt1.switch_to_input(pull=digitalio.Pull.DOWN)
opt2.switch_to_input(pull=digitalio.Pull.DOWN)
opt3.switch_to_input(pull=digitalio.Pull.DOWN)

option = 0
if opt0.value == True:
    option = option + 1
if opt1.value == True:
    option = option + 2
if opt2.value == True:
    option = option + 4
if opt3.value == True:
    option = option + 8

# 0  = 1    0  0  0  0
# 1  = 2    0  0  0  1
# 2  = 4    0  0  1  0
# 3  = 5    0  0  1  1
# 4  = 7    0  1  0  0
# 5  = 10   0  1  0  1
# 6  = 15   0  1  1  0
# 7  = 20   0  1  1  1
# 8  = 25   1  0  0  0
# 9  = 30   1  0  0  1
# 10 = 35   1  0  1  0
# 11 = 40   1  0  1  1
# 12 = 45   1  1  0  0
# 13 = 50   1  1  0  1
# 14 = 55   1  1  1  0
# 15 = 60   1  1  1  1 

# option        0     1    2    3    4    5    6     7     8     9    10    11    12    13    14    15
defaultTimer = [ 1,   2,   4,   5,   7,  10,  15,   20,   25,   30,   35,   40,   45,   50,   55,   60]  # min
defaultValue = [60, 120, 240, 300, 420, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000, 3300, 3600]  # sec

but7Min  = digitalio.DigitalInOut(board.GP13)     # Pin 17 (Note: pin 18 is ground)
but7Min.switch_to_input(pull=digitalio.Pull.DOWN)

butStop  = digitalio.DigitalInOut(board.GP14)     # Pin 19
butStop.switch_to_input(pull=digitalio.Pull.DOWN)

butAdd   = digitalio.DigitalInOut(board.GP15)     # Pin 20
butAdd.switch_to_input(pull=digitalio.Pull.DOWN)

relSound = digitalio.DigitalInOut(board.GP16)     # Pin 21
relSound.switch_to_output(value=False)    # Control the relay for buzzer

# ------------------------------------
# Create the I2C interface.
# SSD1306_I2C SCL connects to Pin 7 (GP5, I2C0 SCL)
#             SDA connects to Pin 6 (GP4, I2C0 SDA)
# -------------------------------------
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# A reset line may be required if there is no auto-reset circuitry
reset_pin = digitalio.DigitalInOut(board.GP1)

# Create the SSD1306 OLED class.
# The first two parameters are the pixel width and pixel height.  Change these
# to the right size for your display!
# The I2C address for these displays is 0x3d or 0x3c, change to match
# A reset line may be required if there is no auto-reset circuitry
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C, reset=reset_pin)

# On CircuitPlayground Express, and boards with built in status NeoPixel -> board.NEOPIXEL
# Otherwise choose an open pin connected to the Data In of the NeoPixel strip, i.e. board.D1
# pixel_pin = board.NEOPIXEL
pixel_pin = board.GP0

# The number of NeoPixels
num_pixels = 512

# The order of the pixel colors - RGB or GRB. Some NeoPixels have red and green reversed!
# For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(
    pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER
)

# =============================================================

# Global Digit color
d_r   = 0
d_g   = 8
d_b   = 0

blink = True
timer = 0    # the Timer counter (sec)

# -------------------------------------------
# n is the dot within two panels: right is 0-255, left is 256-512 (total 512 LED)
# -------------------------------------------
def dot(n, r = 255, g = 255, b = 255):
    row  = int( n / 16 )
    col  = n % 16
    real_row = 15 - row        # Input start from row 0
    pos      = real_row * 16   # LED real row starting from top
    
    # The dot position increases is Z path
    if real_row % 2 == 1:           # Odd line
        real_pos = pos + 15 - col   #    Inc = Reverse
    else:                           # Even line
        real_pos = pos + col        #    Inc = Normal add
        
    pixels[ real_pos ] = ( r, g, b )   
    # print( "   dot: n = %3d; (%3d, %3d), map-row = %3d -> pos = %3d -> real pos = %3d" % (i, row, col, rrow, pos, rpos ))    

def dotOn2Panel(n, r = 16, g = 16, b = 16):
    row32    = int( n / 32 )
    col32    = n % 32
    r_offset = row32 * 16  # Offset two panel
    l_offset = (row32 + 1) * 16
        
    if col32 < 16:         # Map to right panel minus offset
        dot( n - r_offset, r, g, b )
    else:                  # Map to left panel (256 is the right panel) minus offset
        dot( n + 256 - l_offset, r, g, b )

def drawPos( n, pos ):
    row = int( n / 8 )
    col = n % 8
    pos_offset = 0
    if pos == 1:
        pos_offset = -1
    elif pos == 2:
        pos_offset = 1
    # Map 8 x 16 to 512 + position offset
    # Use the global d_r, d_g, d_b variable
    dotOn2Panel( row * 32 + col + pos * 8 + pos_offset, d_r, d_g, d_b)

def draw0( pos ):
    for i in [11,12,18,19,20,21,25,26,29,30,33,34,37,38,41,42,45,46,49,50,53,54,57,58,61,62,65,66,69,70,73,74,77,78,81,82,85,86,89,90,93,94,98,99,100,101,107,108]:
        drawPos( i, pos )

def draw1( pos ):
    for i in [12,13,19,20,21,27,28,29,34,35,36,37,42,43,44,45,52,53,60,61,68,69,76,77,84,85,92,93,100,101,108,109]:
        drawPos( i, pos )

def draw2( pos ):
    for i in [11,12,18,19,20,21,26,27,28,29,30,33,34,37,38,41,42,45,46,53,54,60,61,68,69,75,76,82,83,89,90,97,98,99,100,101,102,105,106,107,108,109,110]:
        drawPos( i, pos )

def draw3( pos ):
    for i in [11,12,18,19,20,21,25,26,29,30,33,34,37,38,45,46,52,53,54,59,60,61,68,69,70,77,78,81,82,85,86,89,90,93,94,98,99,100,101,107,108]:
        drawPos( i, pos )

def draw4( pos ):
    for i in [12,13,19,20,21,27,28,29,35,36,37,42,43,44,45,50,52,53,57,58,60,61,65,66,68,69,73,74,75,76,77,78,81,82,83,84,85,86,92,93,100,101,108,109]:
        drawPos( i, pos )

def draw5( pos ):
    for i in [9,10,11,12,13,14,17,18,19,20,21,22,25,26,33,34,41,42,49,50,51,52,57,58,59,60,61,68,69,70,77,78,85,86,92,93,94,97,98,99,100,101,105,106,107,108]:
        drawPos( i, pos )

def draw6( pos ):
    for i in [11,12,18,19,20,21,25,26,29,30,33,34,37,38,41,42,49,50,57,58,59,60,61,65,66,67,68,69,70,73,74,77,78,81,82,85,86,89,90,93,94,98,99,100,101,107,108]:
        drawPos( i, pos )
 
def draw7( pos ):
    for i in [9,10,11,12,13,14,17,18,19,20,21,22,29,30,37,38,45,46,52,53,60,61,68,69,76,77,83,84,91,92,99,100,107,108]:
        drawPos( i, pos )
    
def draw8( pos ):    
    for i in [11,12,18,19,20,21,25,26,29,30,33,34,37,38,41,42,45,46,50,51,52,53,58,59,60,61,66,67,68,69,70,73,74,77,78,81,82,85,86,89,90,93,94,98,99,100,101,107,108]:
        drawPos( i, pos )

def draw9( pos ):    
    for i in [11,12,18,19,20,21,25,26,29,30,33,34,37,38,41,42,45,46,49,50,51,52,53,54,62,58,59,60,61,69,70,77,78,85,86,93,94,98,99,100,101,107,108]:
        drawPos( i, pos )
        

def drawDigit( pos, n ):
    if n == 0:
        draw0( pos )
    elif n == 1:
        draw1( pos )
    elif n == 2:
        draw2( pos )
    elif n == 3:
        draw3( pos )
    elif n == 4:
        draw4( pos )
    elif n == 5:
        draw5( pos )
    elif n == 6:
        draw6( pos )
    elif n == 7:
        draw7( pos )
    elif n == 8:
        draw8( pos )
    elif n == 9:
        draw9( pos )

# ===============================================
def blinking():
    global blink
    if blink == True:
        for i in [207, 208, 239, 240, 303, 304, 335, 336]:
            dotOn2Panel( i, d_g, d_r, d_b )     # Rever the dot colors
        blink = False
    else:
        blink = True

def chkButton():
    global timer
    if but7Min.value == True:
        timer = defaultValue[ option ]
    if butStop.value == True:
        timer = 0
    if butAdd.value == True:
        timer += 60

def displayClock( minVar, secVar ):
    min_d = int( minVar / 10 )
    if min_d > 0:
       drawDigit( 0, min_d )
    drawDigit( 1, minVar % 10 )
    drawDigit( 2, int( secVar / 10 ) )
    drawDigit( 3, secVar % 10 )

# ================================================

display.fill(0)
display.show()
bSound = False

while True:

    chkButton()
    
    # --------------------------------------------
    # For the 32x16 pixel display
    # --------------------------------------------
    # Clear the pixel, set the color schema
    pixels.fill((0, 0, 0))
    if timer < 60 and timer > 0:
        d_r = 8
        d_g = 0
    else:
        d_r = 0
        d_g = 8

    # ---------------------
    # alwaus blinking
    blinking()

    # -------------------
    # Display counter in pixels
    min  = int( timer / 60 )
    hour = int( min / 60 )
    sec  = timer % 60
    
    displayClock( min, sec )
    pixels.show()
    
    # -------------------------------------------
    # Display message in OLED
    # ------------------------------------------
    display.fill(0)
    
    if timer == 0:

       dispstr = "Pin: %d %d %d %d" % (opt3.value, opt2.value, opt1.value, opt0.value)
       print( dispstr )
       #display.text( dispstr, 0, 0, 1 )
       
       display.text( "Time up", 0, 0, 1 )
       display.text( "Press button", 0, 15, 1 )
       timerMsg = "White  = %d min" % defaultTimer[ option ]
       display.text( timerMsg, 0, 25, 1 )
       display.text( "Black  = Reset", 0, 35, 1 )
       display.text( "Yellow = add 1 min", 0, 45, 1 )
       display.show()
       
       if bSound == True:
          #print( "Bazzer ON" )
          relSound.value = True
          time.sleep( 2 )
          #print( "Buzzer OFF" )
          relSound.value = False
          bSound = False
    else:   
       time_str = "%d Min %02d Sec" % (min, sec) 
       #print( time_str )

       display.text("Count down timer", 0, 0 , 1 )
       display.text(time_str, 0, 15, 1)
       display.show()
       
    time.sleep(1)
    timer = timer - 1
    
    if timer == 0:
        bSound = True
    elif timer < 0:
        timer = 0

# ================================
display.fill(0)
display.text("The END of this program", 0, 30, 1)
display.show()


