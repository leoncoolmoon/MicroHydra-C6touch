<p align="center">
    <a href="https://github.com/echo-lalia/MicroHydra-Apps" alt="Apps">
        <img src="https://img.shields.io/badge/Apps-d66e28" /></a>
 &nbsp;&nbsp;
    <a href="https://github.com/echo-lalia/microhydra-frozen" alt="MicroHydra Firmware">
        <img src="https://img.shields.io/badge/Firmware-d66e28" /></a>
  &nbsp;&nbsp;
    <a href="https://github.com/echo-lalia/Cardputer-MicroHydra/wiki" alt="Wiki">
        <img src="https://img.shields.io/badge/Wiki-b63532" /></a>
  &nbsp;&nbsp;
    <a href="https://github.com/echo-lalia/Cardputer-MicroHydra?tab=GPL-3.0-1-ov-file" alt="License">
        <img src="https://img.shields.io/github/license/echo-lalia/Cardputer-MicroHydra?labelColor=47102a&color=8d1f52" /></a>
  &nbsp;&nbsp;
    <a href="https://github.com/echo-lalia/Cardputer-MicroHydra" alt="Likes">
        <img src="https://img.shields.io/github/stars/echo-lalia/Cardputer-MicroHydra?style=flat&labelColor=47102a&color=8d1f52" /></a>
  &nbsp;&nbsp;
    <a href="https://discord.gg/6e4KUDpgQC" alt="Discord">
        <img src="https://img.shields.io/discord/1279691612099973151?logo=discord&logoColor=c86744&label=Discord&labelColor=300f2d&color=621e5a" /></a>
  &nbsp;&nbsp;
    <a href="https://ko-fi.com/ethanlacasse" alt="KoFi">
        <img src="https://img.shields.io/badge/Support_MicroHydra-4c1b52?logo=kofi&logoColor=b63532" /></a>
</p>


# MicroHydra-C6touch
MicroHydra-C6touch based on MicroHydra, a simple MicroPython based app launcher with some OS-like features. 
Support for [ESP32-C6-Touch-LCD-1.47](https://docs.waveshare.com/ESP32-C6-Touch-LCD-1.47)（original 240x135 res）the blank space is used for a special touch slid keybroad 
improve the menu in launcher and file

<p align="center">
  <img src="https://github.com/echo-lalia/Cardputer-MicroHydra/assets/108598670/15b78e4b-64fc-433a-86d3-979362abd9ab" alt="Microhydra Banner"/>
</p>

This code was built with MicroPython v1.23, for the ESP32-S3.

The main function of MicroHydra is to provide an interface to easily switch between MicroPython apps.   
And to help lower the barriers to entry for anyone wanting to develop apps for their Cardputer (or other supported device!). 
Python scripts can be placed in your device's /apps folder (on the flash), or in a /apps folder on a micro sd card. The launcher scans these two locations on startup.   

<br />

Take a look at the [wiki](https://github.com/echo-lalia/MicroHydra/wiki) for some basic guides to get you started with a MicroPython app.

And for a repository of community-made MicroHydra apps, see [here](https://github.com/echo-lalia/MicroHydra-Apps).

<br /><br /><br />




# how it works:

MicroHydra runs only a single "app" at a time, and switches between them by storing data in the RTC memory, and resetting MicroPython.

The launcher, `main.py`, and other built-in apps, import a `hydra.loader` module, to store or load strings in the RTC memory.  
MicroPython automatically runs `main.py` when it starts, and `main.py` looks for a stored app path, and imports it if it exists. Otherwise, it starts the launcher app.

This approach was chosen to help to prevent issues with memory managment or import conflicts between apps. Resetting the entire device means that the only thing thing loaded before the app, is the lightweight `hydra.loader` and `main.py` modules.  
When MicroHydra is pre-compiled into .mpy files (and therefore doesn't need to compile anything before starting), this reset is fairly quick. And, when it's frozen into a MicroPython firmware, the reset is almost instantaneous.

Apps that need to pass information to eachother can use the same `hydra.loader` module to read/store additional arguments in the RTC.  
For example, when you use the Files app to open a file in the text editor, the Files app adds both the path to the text editor, and the path to the text file into the RTC memory.

<br /><br /><br />

# how the touch keybroad works:

## Overview

A touchscreen virtual keyboard that uses **edge-sliding from both left and right sides** to select keys. Supports both left-handed and right-handed operation.

---

## Screen Layout (320×172)

```
(0,0)                                              (320,0)
  ┌────────┬──────────────────────────────┬────────┐
  │  Left  │                              │ Right  │
  │  Edge  │    ESC / Candidate Preview   │  Edge  │
  │ Touch  │   (Full Row Key Preview)     │ Touch  │
  │  Zone  ├──────────────────────────────┤  Zone  │
  │        │                              │        │
  │  Left  │  Canvas(MicroHydro) Area     │ Right  │
  │Preview │     Gesture Main Zone        │Preview │
  │        │                              │        │
  └────────┴──────────────────────────────┴────────┘
(0,172)                                            (320,172)
```

| Area | Function |
|------|----------|
| **Left/Right Edge** | Touch here to start key selection (30px wide) |
| **Canvas** | Main area for selecting columns and gestures |
| **ESC/Preview** | Shows current row's 14 keys |
| **Lock Badge** | Displays locked keys (F/S/C/A/O) |
| **Preview** | Shows currently selected key |

---

## Core Input: Edge-Slide to Select

### Left/Right Symmetry

| Hand | Start | Slide Direction |
|------|-------|-----------------|
| **Right-handed** | Right edge | **Left** into Canvas |
| **Left-handed** | Left edge | **Right** into Canvas |

### Three Steps

```
Step 1: Touch edge → select ROW (vertical position)
              ↓
Step 2: Slide inward → select COLUMN (horizontal distance)
              ↓
Step 3: Release in Canvas → confirm input
```

### Step 1: Select Row (Vertical Position)

| Position | Row | Keys |
|----------|-----|------|
| Top (0~28px) | Row 0 | `` ` 1 2 3 4 5 6 7 8 9 0 - = BSPC `` |
| Mid (28~86px) | Row 1 | `TAB q w e r t y u i o p [ ] \` |
| Mid-low (86~143px) | Row 2 | `FN SHIFT a s d f g h j k l ; ' ENT` |
| Bottom (143~172px) | Row 3 | `CTL OPT ALT z x c v b n m , . / SPC` |

**Feedback**: Preview area instantly shows all 14 keys in that row.

### Step 2: Select Column (Horizontal Distance)

- **20 pixels per column**
- **14 columns** (0–13)
- Slide left/right to adjust selection

**Feedback**:
- Large character shown in left/right preview areas
- Semi-transparent blue highlight on selected column

### Step 3: Confirm or Cancel

| Action | Result |
|--------|--------|
| Release **inside** Canvas | ✅ Input selected key |
| Release **outside** Canvas | ❌ Cancel (no output) |
| Slide **out of** Canvas | ❌ Cancel (no output) |

---

## Quick Gestures

### Canvas Area Gestures

| Gesture | Condition | Output |
|---------|-----------|--------|
| **Tap** | Movement < 20px | `['ENT']` |
| **Swipe Right** | ≥20px right | `['LEFT']` |
| **Swipe Left** | ≥20px left | `['RIGHT']` |
| **Swipe Up** | ≥20px up | `['UP']` |
| **Swipe Down** | ≥20px down | `['DOWN']` |

### ESC Area

| Action | Output |
|--------|--------|
| Tap in ESC area | `['ESC']` |
| Swipe in ESC area | (no output) |

### G0 Menu Button (GPIO9)

| Action | Output | Purpose |
|--------|--------|---------|
| Press G0 | `['G0']` | Open/trigger menu |

- Physical button, independent of touch
- Always responsive

---

## Lock Key Mechanism

### Display

Lock badge shows currently locked keys:

| Locked | Display |
|--------|---------|
| FN | `F` |
| SHIFT | `S` |
| CTL+ALT | `CA` |
| None | (blank) |

### Key Types

| Type | Keys | Behavior |
|------|------|----------|
| **Exclusive** | FN, SHIFT | Only one can be locked at a time |
| **Accumulative** | CTL, ALT, OPT | Multiple can be locked; auto-unlock after output |

### Examples

| Lock State | Select | Output |
|------------|--------|--------|
| None | `a` | `['a']` |
| FN locked | `F1` | `['F1']` |
| SHIFT locked | `1` | `['!']` |
| CTL locked | `c` | `['CTL', 'c']` |
| CTL+ALT locked | `x` | `['CTL', 'ALT', 'x']` |

---

## Key Maps

### Normal (No Lock)

| Row | Keys |
|-----|------|
| 0 | `` ` 1 2 3 4 5 6 7 8 9 0 - = BSPC `` |
| 1 | `TAB q w e r t y u i o p [ ] \` |
| 2 | `FN SHIFT a s d f g h j k l ; ' ENT` |
| 3 | `CTL OPT ALT z x c v b n m , . / SPC` |

### Shift Layer

| Row | Keys |
|-----|------|
| 0 | `~ ! @ # $ % ^ & * ( ) _ + BSPC` |
| 1 | `TAB Q W E R T Y U I O P { } \|` |
| 2 | `FN SHIFT A S D F G H J K L : " ENT` |
| 3 | `CTL OPT ALT Z X C V B N M < > ? SPC` |

### FN Layer

| Row | Keys |
|-----|------|
| 0 | `ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 _ = DEL` |
| 1 | `TAB q w e r t y u i o p [ ] \` |
| 2 | `FN SHIFT a s d f g h j k l UP ' ENT` |
| 3 | `CTL OPT ALT z x c v b n m LEFT DOWN RIGHT SPC` |

---

## Complete Examples

### Right-handed: Input "h"

```
1. Touch right edge at mid-height → Row 2 selected
2. Slide left to column 7 → Preview shows "h"
3. Release → Output ['h']
```

### Left-handed: Input "h"

```
1. Touch left edge at mid-height → Row 2 selected
2. Slide right to column 7 → Preview shows "h"
3. Release → Output ['h']
```

### Input "Ctrl+C"

```
1. Touch right edge bottom → Row 3
2. Slide to column 0 (CTL) → Release → Lock CTL (shows C)
3. Touch right edge mid → Row 2
4. Slide to column 3 (c) → Preview shows "c"
5. Release → Output ['CTL', 'c'], CTL auto-unlocks
```

### Use G0 Menu

```
1. Press G0 button → Output ['G0']
2. App opens menu
3. Use touch to navigate
4. Press G0 again → Close menu
```

---

## Summary

| Method | Trigger | Output | Use Case |
|--------|---------|--------|----------|
| **Edge-slide** | Left/right edge | Keys/characters | Primary text input |
| **Canvas gesture** | Canvas area | ENT/direction keys | Quick actions/gaming |
| **ESC tap** | ESC area | ESC | Cancel/exit |
| **G0 button** | GPIO9 physical | G0 | Menu operations |

---

## Advantages

| Feature | Benefit |
|---------|---------|
| **Left/right symmetric** | Works for both hands |
| **One-handed** | Thumb operation from either side |
| **Step-by-step** | Row first, then column → fewer errors |
| **Real-time preview** | See selection before committing |
| **Quick gestures** | Fast access to common actions |
| **Physical G0** | Reliable menu trigger |
| **Lock keys** | FN/SHIFT/CTL/ALT/OPT persistent states |


# Installing Apps:
Apps are designed to work very simply in this launcher. Any Python file placed in the "apps" folder on the flash, or the SD card, will be found and can be launched as an app. This works with .mpy files too, meaning machine code written in other languages can also be linked and run as an app (though I have not tested this yet)

MicroHydra apps can be simple single-file scripts, or be contained in a folder with an `__init__.py`, just like a standard Python module. You can learn more about these specifics on the [app format](https://github.com/echo-lalia/MicroHydra/wiki/App-Format) section of the wiki.

Some community-made apps for MH can be found [here](https://github.com/echo-lalia/MicroHydra-Apps) (and this is where the "GetApps" built-in app find apps to download).

<br /><br /><br />




# Installing MicroHydra:

You can install MicroHydra a few different ways. 

 - [*Install on top of a normal MicroPython installation:*](#In-MicroPython)   
   Flash Micropython to your Cardputer, and copy the contents of the `DEVICENAME_compiled.zip` (or `DEVICENAME_raw.zip`) file from the "releases" section to the flash on your device.   
    > This is the most convenient way to install for development, because you can simply open up the MicroHydra files to see what's goin on. However, the `raw` (as in, ending with ".py") form of the software is much more susceptible to memory issues than the other installation methods, so it's reccomended that you use the compiled (`.mpy`) version for any files that you aren't specifically working inside of.



 - [*Flash MH as a compiled firmware:*](#As-a-complete-firmware)   
   You can flash MicroHydra (along with MicroPython) directly to your device using the `DEVICENAME.bin` file from the "Releases" section. (You can also usually find the most recent builds on M5Burner). This is the fastest and easiest to use form of MH!   
   > In this installation, the MicroHydra files have been 'frozen' into the MicroPython firmware. This makes the built-in files load *much* faster, and makes them all use less memory.  
   *Make sure you erase the flash before installing, and put your device in download mode by holding G0 when plugging it in.*

> **Note for developers:** *The contents of `src/` must be processed in order to output device-specific MicroHydra builds. To learn more, take a look at [this](https://github.com/echo-lalia/MicroHydra/wiki/multi-platform) page in the wiki.*

-----

<br /><br />
<br /><br />
<br /><br />
<br /><br />
<br /><br />
<br /><br />







# In MicroPython

*This is a detailed guide for installing MicroHydra on a regular MicroPython installation, using Thonny.*

<br /> 
<br />

## Install Thonny

Thonny is a tool that provides a very easy way to flash MicroPython, edit code, and view/edit the files on the device.

You can follow the instructions here to install it: https://thonny.org/   
> *Make sure to use a new version; older versions might fail to flash the ESP32-S3*
>
> *Some sources of Thonny (such as with certain built-in package managers) can result in strange issues with permissions or missing dependencies. If you encounter an issue with thonny when setting it up, and there is no other clear solution to your problem, it might be a good idea to try installing from another source.*

<br /> 
<br />
<br />

## Flash MicroPython
Next we need to flash MicroPython on your device 

Open Thonny, click this button in the bottom right, and click "Configure interpreter":   
<p>
  <img src="misc\images\thonnyhamburgermenu.png" height="300" hspace="10"/><img src="misc\images\thonnyconfigureinterpreter.png" height="300" hspace="10"/>
</p>

<br />

It should open this menu:   
<img src="misc\images\thonnyinterpreteroptions.png" width="500"/>


<br />

click "install or update micropython", and you should see another window:   
<p>
  <img src="misc\images\thonnyinstallmicropython.png" height="300" hspace="10"/><img src="misc\images\thonnyinstallmicropythonwindow.png" height="300" hspace="10"/>
</p>

<br />
<br />




Now you need to put your device into bootloader mode, and connect it to your computer. To do this, simply hold the `G0` button as you connect it to your PC.

<img src="misc\images\cardputerg0.jpg" width="200"/>

> *You can also hold `G0` and tap the reset button to get to bootloader mode.*  
> *If you are using a device like the TDeck, which doesn't power on when plugged in, you must hold `g0` and then flip the power switch on.*

<br />
<br />

In "target port" you should now see a device with a name like "USB JTAG". Set the options as shown, and click "Install":  
<img src="misc\images\thonnyflashsettings.png" width="400"/>
> *For a device with Octal-SPIRAM (like the TDeck), you will have to download a specific Octal-SPIRAM variant from the [MicroPython website.](https://micropython.org/download/ESP32_GENERIC_S3/)*

> *If installing didn't start, check that the correct device is selected, and it's in bootloader mode.*   

<br />

Once It has been flashed with MicroPython, unplug the device and plug it back in.   
Thonny might not automatically detect it right away. If it doesn't, you can select it from the bottom right here:   
![image](https://github.com/echo-lalia/Cardputer-MicroHydra/assets/108598670/7835950b-d773-4de7-9d2b-5de1663b2070)   
And you might also need to click the red "stop/restart" button at the top to get it to appear. 

<br />

If you see something like this in the bottom terminal, you've flashed it successfully!   
![image](https://github.com/echo-lalia/Cardputer-MicroHydra/assets/108598670/6c4079eb-3921-4f1c-a269-f503a7ccab40)   

<br />
<br />
<br />

## Install MicroHydra

Now you can download and install MicroHydra.  
To get the apropriate files for your device, you should head to the "Releases" section of the GitHub page, and look for a `DEVICENAME_compiled.zip` or `DEVICENAME_raw.zip` file.

<p>
  <img src="misc\images\releases.png" height="300" hspace="10"/><img src="misc\images\releasecompiled.png" height="300" hspace="20"/>
</p>

Extract the .zip file, and head back over to Thonny.

We need to use Thonnys file browser. If you don't see it to your left, you can bring it up by clicking view>Files in the top left.
<img width="400" src="misc\images\thonnyfiles.png"> 

<br />

On the top half of the file browser, navigate to the folder where you extracted the MicroHydra zip file.  
Then, select all of the contents, and hit `Upload to /`   
<img height="260" src="misc\images\thonnyuploadfiles.png"> <img height="260" src="misc\images\thonnyuploadfiles2.png"> 

<br />

Once the files are transferred over, you can test it out by disconnecting it, and powering it on. If everything is working, you should see the main launcher open up!

If you have any issues, feel free to reach out. MH is still growing, and I'm interested to hear of any trouble it might be giving you. 

----

<br /><br />
<br /><br />
<br /><br />
<br /><br />
<br /><br />
<br /><br />







# As a complete firmware

*This is a detailed guide for flashing the MicroHydra firmware on your device, using Thonny.*

<br /> 
<br />

## Install Thonny

Thonny is a tool that provides a very easy way to flash MicroPython, edit code, and view/edit the files on the device.

You can follow the instructions here to install it: https://thonny.org/   
> *Make sure to use a new version; older versions might fail to flash the ESP32-S3*
>
> *Some sources of Thonny (such as with certain built-in package managers) can result in strange issues with permissions or missing dependencies. If you encounter an issue with thonny when setting it up, and there is no other clear solution to your problem, it might be a good idea to try installing from another source.*

<br /> 
<br />
<br />


## Flash MicroHydra

Now you can download and install MicroHydra.  
To get the apropriate firmware for your device, you should head to the "Releases" section of the GitHub page, look for a `DEVICENAME.bin` file, and download it.

<p>
  <img src="misc\images\releases.png" height="300" hspace="10"/><img src="misc\images\releasebin.png" height="300" hspace="20"/>
</p>

Open Thonny, click this button in the bottom right, and click "Configure interpreter":   
<p>
  <img src="misc\images\thonnyhamburgermenu.png" height="300" hspace="10"/><img src="misc\images\thonnyconfigureinterpreter.png" height="300" hspace="10"/>
</p>

<br />

It should open this menu:   
<img src="misc\images\thonnyinterpreteroptions.png" width="500"/>


<br />

click "install or update micropython", and you should see another window:   
<p>
  <img src="misc\images\thonnyinstallmicropython.png" height="300" hspace="10"/><img src="misc\images\thonnyinstallmicropythonwindow.png" height="300" hspace="10"/>
</p>

<br />
<br />




Now you need to put your device into bootloader mode, and connect it to your computer. To do this, simply hold the `G0` button as you connect it to your PC.

<img src="misc\images\cardputerg0.jpg" width="200"/>

> *You can also hold `G0` and tap the reset button to get to bootloader mode.*  
> *If you are using a device like the TDeck, which doesn't power on when plugged in, you must hold `g0` and then flip the power switch on.*


<br />
<br />

Next we will select the firmware .bin file we downloaded.  
Click the little menu button and click `Select local MicroPython image ...`  
<img src="misc\images\thonnylocalmicropython.png" width="400"/>  
Navigate to the .bin file you downloaded, and select it.  
Make sure you also select your device in the "Target port" dropdown (it should have a name like "USB JTAG").

Your window should look something like this:  
<img src="misc\images\thonnyflashbin.png" width="400"/>  

Click "Install", and let it do its thing!

> *If installing didn't start, check that the correct device is selected, and it's in bootloader mode.*   

Once it's flashed, you can test it out by disconnecting it, and powering it on. If everything is working, you should see the main launcher open up!

If you have any issues, feel free to reach out. MH is still growing, and I'm interested to hear of any trouble it might be giving you. 

----

<br />
<br />
<br />


<img src="https://github.com/echo-lalia/Cardputer-MicroHydra/assets/108598670/a0782c5d-5633-489a-a5eb-f6b4e83803ef" alt="Demo GIF"/>
