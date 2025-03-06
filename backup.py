import customtkinter as ctk
import threading
import time
import os
import requests
import zipfile

# Global variables to manage the ESP thread and its running state.
esp_thread = None
esp_running = False

def run_esp():
    """
    Runs the ESP overlay. This function loads the MobileNet SSD model
    from the AppData folder, captures a specified screen region, runs object detection,
    and creates a transparent overlay using pygame. The overlay updates continuously
    until esp_running is set to False.
    Only 'person' class detections (class index 15) are drawn.
    """
    global esp_running
    import win32api
    import win32con
    import win32gui
    import pygame
    from PIL import ImageGrab
    import numpy as np
    import cv2
    import pyautogui

    # Set a very low confidence threshold (adjust as needed).
    CONFIDENCE = 0.000000000000000000001

    # Get the model folder from AppData\EzAim\Models.
    appdata = os.getenv("LOCALAPPDATA")
    model_folder = os.path.join(appdata, "EzAim", "Models")
    prott1 = os.path.join(model_folder, "MobileNet_deploy.prototxt")
    prott2 = os.path.join(model_folder, "MobileNetSSD_deploy.caffemodel")

    print("[INFO] loading model from:", prott1, "and", prott2)
    net = cv2.dnn.readNetFromCaffe(prott1, prott2)

    # Standard MobileNetSSD class labels (index 15 is "person")
    CLASSES = [
        "background", "aeroplane", "bicycle", "bird", "boat",
        "bottle", "bus", "car", "cat", "chair", "cow",
        "diningtable", "dog", "horse", "motorbike", "person",
        "pottedplant", "sheep", "sofa", "train", "tvmonitor"
    ]
    # Define random colors for each class.
    COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

    # Define the screen capture region (remains the same)
    capture_bbox = (710, 290, 1210, 790)
    frame_width = capture_bbox[2] - capture_bbox[0]   # 500
    frame_height = capture_bbox[3] - capture_bbox[1]    # 500

    # New window dimensions (twice the capture box size)
    window_width = frame_width * 2    # 1000
    window_height = frame_height * 2  # 1000

    # Initialize pygame and create an overlay window with the new dimensions.
    pygame.init()
    screen = pygame.display.set_mode((window_width, window_height), pygame.NOFRAME)
    hwnd = pygame.display.get_wm_info()["window"]
    exStyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    exStyle |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exStyle)
    win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)

    # Position the overlay on the secondary monitor if available.
    monitors = win32api.EnumDisplayMonitors()
    if len(monitors) > 1:
        secondary_monitor_rect = monitors[1][2]
    else:
        secondary_monitor_rect = monitors[0][2]
    mon_x, mon_y, mon_right, mon_bottom = secondary_monitor_rect
    mon_width = mon_right - mon_x
    mon_height = mon_bottom - mon_y
    window_x = mon_x + (mon_width - window_width) // 2
    window_y = mon_y + (mon_height - window_height) // 2
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        window_x, window_y, window_width, window_height,
        win32con.SWP_SHOWWINDOW
    )

    # (Optional) Hide the mouse cursor on the overlay.
    pygame.mouse.set_visible(False)

    print("[INFO] starting overlay...")
    while esp_running:
        # Capture the screen region.
        frame = np.array(ImageGrab.grab(bbox=capture_bbox))
        (h, w) = frame.shape[:2]

        # Prepare input blob and run detection.
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        net.setInput(blob)
        detections = net.forward()

        # Clear screen each loop.
        screen.fill((0, 0, 0))

        # Only draw bounding boxes for "person" (class index 15).
        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            idx = int(detections[0, 0, i, 1])
            if idx != 15:
                continue
            if confidence < CONFIDENCE:
                continue

            # Compute the bounding box.
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            label_text = "person: {:.2f}%".format(confidence * 100)
            color = COLORS[idx]
            cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
            y_text = startY - 15 if (startY - 15) > 15 else startY + 15
            cv2.putText(frame, label_text, (startX, y_text),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Convert to RGB and create a pygame surface from the frame.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_surface = pygame.surfarray.make_surface(
            np.transpose(frame_rgb, (1, 0, 2))
        )
        # Scale the captured frame to the new window size.
        frame_surface = pygame.transform.scale(frame_surface, (window_width, window_height))
        screen.blit(frame_surface, (0, 0))
        pygame.display.update()

        # Handle pygame events.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                esp_running = False
                pygame.quit()
                cv2.destroyAllWindows()
                return

        # Allow pressing 'Q' to close overlay.
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            esp_running = False
            pygame.quit()
            print("[INFO] overlay closed...")
            cv2.destroyAllWindows()
            return

        # Small delay for stable FPS.
        pygame.time.delay(30)

    # When esp_running becomes False, close everything.
    pygame.quit()
    cv2.destroyAllWindows()
    print("[INFO] overlay stopped...")

class CheatEngineUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("EzAim Cheat Engine")
        self.geometry("400x600")
        
        # Create a segmented button to switch between "Cheats", "Info", and "Download" tabs.
        self.segmented_button = ctk.CTkSegmentedButton(
            self, 
            values=["Cheats", "Info", "Download"], 
            command=self.switch_tab
        )
        self.segmented_button.pack(pady=10)
        self.segmented_button.set("Cheats")
        
        # Container frame for the tab frames.
        self.container = ctk.CTkFrame(self)
        self.container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Create the three tab frames.
        self.cheats_frame = ctk.CTkFrame(self.container)
        self.info_frame = ctk.CTkFrame(self.container)
        self.download_frame = ctk.CTkFrame(self.container)
        self.cheats_frame.grid(row=0, column=0, sticky="nsew")
        self.info_frame.grid(row=0, column=0, sticky="nsew")
        self.download_frame.grid(row=0, column=0, sticky="nsew")
        
        # Setup each tab.
        self.setup_cheats_frame()
        self.setup_info_frame()
        self.setup_download_frame()
        self.show_frame("Cheats")
        
    def switch_tab(self, choice):
        self.show_frame(choice)
    
    def show_frame(self, name):
        if name == "Cheats":
            self.cheats_frame.tkraise()
        elif name == "Info":
            self.info_frame.tkraise()
        elif name == "Download":
            self.download_frame.tkraise()
            
    def setup_cheats_frame(self):
        # Title label.
        title = ctk.CTkLabel(
            self.cheats_frame, text="Cheat Options", font=("Roboto", 20)
        )
        title.pack(pady=20)
        
        # Cheat options.
        self.esp_var = ctk.BooleanVar()
        self.aimbot_var = ctk.BooleanVar()
        esp_checkbox = ctk.CTkCheckBox(
            self.cheats_frame, text="ESP", variable=self.esp_var
        )
        esp_checkbox.pack(pady=10, padx=20)
        aimbot_checkbox = ctk.CTkCheckBox(
            self.cheats_frame, text="Aimbot", variable=self.aimbot_var
        )
        aimbot_checkbox.pack(pady=10, padx=20)
        
        # Apply / Reset buttons.
        apply_button = ctk.CTkButton(
            self.cheats_frame, text="Apply Cheat", command=self.apply_cheat
        )
        apply_button.pack(pady=20)
        reset_button = ctk.CTkButton(
            self.cheats_frame, text="Reset Options", command=self.reset_options
        )
        reset_button.pack(pady=10)
        
        # Label to display cheat status.
        self.cheat_result_label = ctk.CTkLabel(
            self.cheats_frame, text="Select cheats above", font=("Roboto", 16)
        )
        self.cheat_result_label.pack(pady=20)
        
    def setup_info_frame(self):
        info_text = (
            "EzAim Cheat Engine\n"
            "Version: Beta\n"
            "Developer: Aydin\n\n"
            "This is the beta version of EzAim Cheat Engine.\n"
            "It includes options for ESP and Aimbot.\n"
            "Note: May be buggy.\n"
            "More features soon!"
        )
        info_label = ctk.CTkLabel(
            self.info_frame, text=info_text, font=("Roboto", 16)
        )
        info_label.pack(pady=20, padx=20)
        
    def setup_download_frame(self):
        # Title for download section.
        title = ctk.CTkLabel(
            self.download_frame, text="Download AI Models", font=("Roboto", 20)
        )
        title.pack(pady=20)
        
        # Download button.
        download_button = ctk.CTkButton(
            self.download_frame, text="Download AI Models", command=self.start_download_thread
        )
        download_button.pack(pady=10, padx=20)
        
        # Progress bar.
        self.download_progress = ctk.CTkProgressBar(self.download_frame)
        self.download_progress.set(0)
        self.download_progress.pack(pady=10, padx=20, fill="x")
        
        # Label to show percentage.
        self.download_percent_label = ctk.CTkLabel(
            self.download_frame, text="0%", font=("Roboto", 16)
        )
        self.download_percent_label.pack(pady=10, padx=20)
        
    def start_download_thread(self):
        # Start the download in a separate thread.
        threading.Thread(target=self.download_models, daemon=True).start()
        
    def download_models(self):
        """
        Downloads the AI model ZIP from a specified URL.
        Creates a folder in AppData\EzAim\Models and extracts the ZIP there.
        Updates the progress bar and percentage label as the download proceeds.
        """
        # Replace this URL with your actual download link.
        url = "https://github.com/Sparky7980/EzAim/raw/refs/heads/main/DownloadAI.zip"
        # Create the folder in AppData.
        appdata = os.getenv("LOCALAPPDATA")
        dest_folder = os.path.join(appdata, "EzAim", "Models")
        if not os.path.exists(dest_folder):
            try:
                os.makedirs(dest_folder)
            except Exception as e:
                print("Error creating folder:", e)
                return
        # Destination ZIP path.
        dest_zip = os.path.join(dest_folder, "mobilenet_models.zip")
        
        try:
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')
            if total_length is None:
                with open(dest_zip, 'wb') as f:
                    f.write(response.content)
                self.after(0, lambda: self.download_progress.set(1.0))
                self.after(0, lambda: self.download_percent_label.configure(text="100%"))
            else:
                dl = 0
                total_length = int(total_length)
                with open(dest_zip, 'wb') as f:
                    for data in response.iter_content(chunk_size=4096):
                        dl += len(data)
                        f.write(data)
                        progress = int(100 * dl / total_length)
                        self.after(0, lambda p=progress: self.download_progress.set(p/100.0))
                        self.after(0, lambda p=progress: self.download_percent_label.configure(text=f"{p}%"))
            print("Download complete! Extracting files...")
            # Extract the ZIP into dest_folder.
            with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
                zip_ref.extractall(dest_folder)
            # Optionally, remove the zip file after extraction.
            os.remove(dest_zip)
            print("Extraction complete!")
        except Exception as e:
            print("Download failed:", e)
        
    def apply_cheat(self):
        """
        Called when the user clicks "Apply Cheat".
        Starts or stops the ESP thread based on the checkbox states.
        """
        global esp_thread, esp_running
        result_text = "Cheats applied:\n"

        # If ESP is checked, start the overlay if not already running.
        if self.esp_var.get():
            result_text += "- ESP enabled\n"
            if esp_thread is None or not esp_thread.is_alive():
                esp_running = True
                esp_thread = threading.Thread(target=run_esp, daemon=True)
                esp_thread.start()
        else:
            # If unchecked, stop the overlay.
            esp_running = False

        # Aimbot is just a placeholder in this demo.
        if self.aimbot_var.get():
            result_text += "- Aimbot enabled (not implemented)\n"

        if result_text == "Cheats applied:\n":
            result_text += "None selected!"

        self.cheat_result_label.configure(text=result_text)
        
    def reset_options(self):
        """
        Called when the user clicks "Reset Options".
        Unchecks all cheat boxes and stops the ESP overlay if running.
        """
        global esp_running
        self.esp_var.set(False)
        self.aimbot_var.set(False)
        esp_running = False
        self.cheat_result_label.configure(text="Options reset.\nSelect cheats above.")

if __name__ == "__main__":
    app = CheatEngineUI()
    app.mainloop()
