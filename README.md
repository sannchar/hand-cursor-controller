# Hand Cursor & Joystick

A Python application for controlling your mouse and keyboard (for gaming and desktop use) via hand gestures using a webcam and MediaPipe.

## Features
*   **Right Hand (Mouse):** Cursor control, left/right clicks, scrolling, and dragging.
*   **Left Hand (Joystick):** Movement control (WASD) and action keys (Space, E, 1, 2, 3).
*   Camera selection on startup (supports multiple webcams).
*   Toggleable keyboard/joystick mode.
*   Standalone `.exe` build available.

## Gestures Guide

### Right Hand (Mouse)
*   🖐️ **Open Palm:** Cursor follows your palm.
*   🤏 **Pinch (Thumb + Index):** Left Click / Hold to Drag.
*   🤏 **Pinch (Thumb + Middle):** Right Click / Camera movement in games.
*   🤏 **Pinch (Thumb + Ring):** Scroll up/down (move hand vertically while pinching).
*   ✊ **Fist:** Pause mouse tracking.

### Left Hand (Joystick)
*   **Move hand UP from center:** W (Hold)
*   **Move hand DOWN from center:** S (Hold)
*   **Move hand LEFT from center:** A (Hold)
*   **Move hand RIGHT from center:** D (Hold)
*   ✊ **Fist:** Recalibrate the center of the joystick.
*   🤏 **Pinch (Thumb + Index):** Space (Tap)
*   🤏 **Pinch (Thumb + Middle):** 1 (Tap)
*   🤏 **Pinch (Thumb + Ring):** 2 (Tap)
*   🤏 **Pinch (Thumb + Pinky):** 3 (Tap)
*   🤙 **Pinky Up (Other fingers down):** E (Tap)

## How to Run
You can run the project using Python:
```bash
pip install -r requirements.txt
python hand_cursor.py
```
Or simply download the ready-to-use `hand_cursor.exe` from the **[Releases](https://github.com/)** section (on the right side of the GitHub repository page).
